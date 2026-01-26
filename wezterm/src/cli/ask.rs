//! CX Terminal: AI-powered ask command
//!
//! Provides natural language interface to system operations.
//! Example: cx ask "install cuda drivers for my nvidia gpu"
//! Example: cx ask --do "optimize my system for gaming"

use anyhow::Result;
use clap::Parser;
use std::io::{self, Read, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;

/// AI-powered command interface
#[derive(Debug, Parser, Clone)]
pub struct AskCommand {
    /// The question or task description
    #[arg(trailing_var_arg = true)]
    pub query: Vec<String>,

    /// Execute the suggested commands (with confirmation)
    #[arg(long = "do", short = 'd')]
    pub execute: bool,

    /// Skip confirmation prompts (use with caution)
    #[arg(long = "yes", short = 'y')]
    pub auto_confirm: bool,

    /// Use local AI only (no cloud)
    #[arg(long = "local")]
    pub local_only: bool,

    /// Output format: text, json, commands
    #[arg(long = "format", short = 'f', default_value = "text")]
    pub format: String,

    /// Verbose output
    #[arg(long = "verbose", short = 'v')]
    pub verbose: bool,
}

const CX_DAEMON_SOCKET: &str = "/var/run/cx/daemon.sock";
const CX_USER_SOCKET_TEMPLATE: &str = "/run/user/{}/cx/daemon.sock";

impl AskCommand {
    pub fn run(&self) -> Result<()> {
        let query = self.query.join(" ");

        if query.is_empty() {
            // Interactive mode - read from stdin
            return self.run_interactive();
        }

        if self.verbose {
            eprintln!("cx ask: {}", query);
        }

        // Try to connect to daemon
        let response = self.query_daemon(&query)?;

        // Output response
        match self.format.as_str() {
            "json" => println!("{}", response),
            "commands" => self.print_commands_only(&response),
            _ => self.print_formatted(&response),
        }

        // Execute if --do flag
        if self.execute {
            self.execute_commands(&response)?;
        }

        Ok(())
    }

    fn run_interactive(&self) -> Result<()> {
        eprintln!("cx ask: Enter your question (Ctrl+D to finish):");
        let mut input = String::new();
        io::stdin().read_to_string(&mut input)?;

        let query = input.trim();
        if query.is_empty() {
            anyhow::bail!("No query provided");
        }

        let response = self.query_daemon(query)?;
        self.print_formatted(&response);

        if self.execute {
            self.execute_commands(&response)?;
        }

        Ok(())
    }

    fn query_daemon(&self, query: &str) -> Result<String> {
        // Try user socket first, then system socket
        let uid = unsafe { libc::getuid() };
        let user_socket = CX_USER_SOCKET_TEMPLATE.replace("{}", &uid.to_string());

        let socket_path = if Path::new(&user_socket).exists() {
            user_socket
        } else if Path::new(CX_DAEMON_SOCKET).exists() {
            CX_DAEMON_SOCKET.to_string()
        } else {
            // Daemon not running - use fallback
            return self.query_fallback(query);
        };

        match UnixStream::connect(&socket_path) {
            Ok(mut stream) => {
                // Send request
                let request = serde_json::json!({
                    "type": "ask",
                    "query": query,
                    "execute": self.execute,
                    "local_only": self.local_only,
                });

                let request_bytes = serde_json::to_vec(&request)?;
                stream.write_all(&request_bytes)?;
                stream.shutdown(std::net::Shutdown::Write)?;

                // Read response
                let mut response = String::new();
                stream.read_to_string(&mut response)?;
                Ok(response)
            }
            Err(e) => {
                if self.verbose {
                    eprintln!("cx ask: daemon connection failed: {}", e);
                }
                self.query_fallback(query)
            }
        }
    }

    fn query_fallback(&self, query: &str) -> Result<String> {
        // Direct AI query without daemon
        // This is a simplified fallback that suggests using the daemon

        let response = serde_json::json!({
            "status": "fallback",
            "message": "CX daemon not running. Using limited fallback mode.",
            "query": query,
            "suggestion": self.generate_fallback_suggestion(query),
            "hint": "Start the CX daemon for full AI capabilities: systemctl --user start cx-daemon"
        });

        Ok(serde_json::to_string_pretty(&response)?)
    }

    fn generate_fallback_suggestion(&self, query: &str) -> String {
        // Basic pattern matching for common queries
        let query_lower = query.to_lowercase();

        if query_lower.contains("install") && query_lower.contains("cuda") {
            return "sudo apt install nvidia-cuda-toolkit".to_string();
        }
        if query_lower.contains("install") && query_lower.contains("nvidia") {
            return "sudo apt install nvidia-driver-535".to_string();
        }
        if query_lower.contains("lamp") || (query_lower.contains("apache") && query_lower.contains("mysql") && query_lower.contains("php")) {
            return "sudo apt install apache2 mysql-server php libapache2-mod-php php-mysql".to_string();
        }
        if query_lower.contains("disk") && query_lower.contains("space") {
            return "du -h --max-depth=1 / 2>/dev/null | sort -hr | head -20".to_string();
        }
        if query_lower.contains("package") && query_lower.contains("disk") {
            return "dpkg-query -Wf '${Installed-Size}\\t${Package}\\n' | sort -nr | head -20".to_string();
        }

        // Default
        format!("Unable to process offline. Query: {}", query)
    }

    fn print_formatted(&self, response: &str) {
        // Try to parse as JSON and pretty print
        if let Ok(json) = serde_json::from_str::<serde_json::Value>(response) {
            if let Some(message) = json.get("message").and_then(|m| m.as_str()) {
                println!("{}", message);
            }
            if let Some(suggestion) = json.get("suggestion").and_then(|s| s.as_str()) {
                println!("\n  {}", suggestion);
            }
            if let Some(commands) = json.get("commands").and_then(|c| c.as_array()) {
                println!("\nSuggested commands:");
                for cmd in commands {
                    if let Some(cmd_str) = cmd.as_str() {
                        println!("  $ {}", cmd_str);
                    }
                }
            }
            if let Some(hint) = json.get("hint").and_then(|h| h.as_str()) {
                eprintln!("\nHint: {}", hint);
            }
        } else {
            println!("{}", response);
        }
    }

    fn print_commands_only(&self, response: &str) {
        if let Ok(json) = serde_json::from_str::<serde_json::Value>(response) {
            if let Some(commands) = json.get("commands").and_then(|c| c.as_array()) {
                for cmd in commands {
                    if let Some(cmd_str) = cmd.as_str() {
                        println!("{}", cmd_str);
                    }
                }
            } else if let Some(suggestion) = json.get("suggestion").and_then(|s| s.as_str()) {
                println!("{}", suggestion);
            }
        }
    }

    fn execute_commands(&self, response: &str) -> Result<()> {
        let json: serde_json::Value = serde_json::from_str(response)?;

        let commands: Vec<&str> = if let Some(cmds) = json.get("commands").and_then(|c| c.as_array()) {
            cmds.iter().filter_map(|c| c.as_str()).collect()
        } else if let Some(suggestion) = json.get("suggestion").and_then(|s| s.as_str()) {
            vec![suggestion]
        } else {
            return Ok(());
        };

        if commands.is_empty() {
            return Ok(());
        }

        if !self.auto_confirm {
            eprintln!("\nCommands to execute:");
            for cmd in &commands {
                eprintln!("  $ {}", cmd);
            }
            eprint!("\nProceed? [y/N] ");
            io::stderr().flush()?;

            let mut input = String::new();
            io::stdin().read_line(&mut input)?;

            if !input.trim().eq_ignore_ascii_case("y") {
                eprintln!("Aborted.");
                return Ok(());
            }
        }

        for cmd in commands {
            eprintln!("$ {}", cmd);
            let status = std::process::Command::new("sh")
                .arg("-c")
                .arg(cmd)
                .status()?;

            if !status.success() {
                eprintln!("Command failed with exit code: {:?}", status.code());
                if !self.auto_confirm {
                    eprint!("Continue with remaining commands? [y/N] ");
                    io::stderr().flush()?;

                    let mut input = String::new();
                    io::stdin().read_line(&mut input)?;

                    if !input.trim().eq_ignore_ascii_case("y") {
                        anyhow::bail!("Execution aborted by user");
                    }
                }
            }
        }

        Ok(())
    }
}

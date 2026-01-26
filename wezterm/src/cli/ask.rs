//! CX Terminal: Agentic AI command interface
//!
//! True agent behavior - automatically executes safe commands and returns results.
//! Not just a command suggester, but an AI that DOES things.
//!
//! Example: cx ask "what time is it" → "Sun Jan 26 15:47:32 IST 2026"
//! Example: cx ask "create a python project" → Creates and shows the result

use anyhow::Result;
use clap::Parser;
use std::env;
use std::io::{self, Read, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::process::Command;

use super::ask_agent::{classify_command, execute_and_capture, CommandSafety};
use super::ask_context::ProjectContext;
use super::ask_executor::extract_commands;
use super::ask_patterns::PatternMatcher;
use super::branding::{colors, print_error, print_info, print_success};
use super::plan::{Plan, PlanAction};

/// AI-powered agentic command interface
///
/// By default, safe commands are auto-executed and results shown.
/// Use --no-exec to get suggestions instead of execution.
#[derive(Debug, Parser, Clone)]
pub struct AskCommand {
    /// Don't auto-execute, just show suggestions
    #[arg(long = "no-exec", short = 'n')]
    pub no_execute: bool,

    /// Skip confirmation prompts for moderate-risk commands
    #[arg(long = "yes", short = 'y')]
    pub auto_confirm: bool,

    /// Use local AI only (no cloud)
    #[arg(long = "local")]
    pub local_only: bool,

    /// Output format: text, json, commands
    #[arg(long = "format", short = 'f', default_value = "text")]
    pub format: String,

    /// Verbose output (show commands being run)
    #[arg(long = "verbose", short = 'v')]
    pub verbose: bool,

    /// The question or task description
    #[arg(trailing_var_arg = true)]
    pub query: Vec<String>,
}

const CX_DAEMON_SOCKET: &str = "/var/run/cx/daemon.sock";
const CX_USER_SOCKET_TEMPLATE: &str = "/run/user/{}/cx/daemon.sock";

impl AskCommand {
    pub fn run(&self) -> Result<()> {
        let query = self.query.join(" ");

        if query.is_empty() {
            return self.run_interactive();
        }

        if self.verbose {
            eprintln!("cx ask: {}", query);
        }

        // Step 1: Try CX command patterns (new, save, restore, etc.)
        if let Some(_) = self.try_cx_command(&query)? {
            return Ok(());
        }

        // Step 2: Query AI and handle response agentically
        let response = self.query_ai(&query)?;
        self.handle_agentic_response(&query, &response)
    }

    /// Handle response with true agent behavior
    fn handle_agentic_response(&self, _original_query: &str, response: &str) -> Result<()> {
        // Extract commands from AI response
        let extraction = extract_commands(response);

        // If no-exec mode, just show the response
        if self.no_execute {
            return self.show_suggestion(response, &extraction);
        }

        // If we extracted commands, decide how to handle them
        if !extraction.commands.is_empty() {
            let plan = Plan::from_commands(&extraction.commands);

            // Check if any command is dangerous or blocked
            let needs_confirmation = plan.has_dangerous() || plan.has_blocked() || plan.requires_sudo;

            if needs_confirmation {
                // Dangerous/sudo commands → show Plan UI for confirmation
                return self.execute_with_plan(plan);
            } else {
                // Safe/moderate commands → execute immediately (autonomous agent!)
                return self.execute_plan_immediately(&plan);
            }
        }

        // No commands found - show the text response
        self.print_ai_response(response);
        Ok(())
    }

    /// Execute plan immediately without prompting (autonomous agent mode)
    fn execute_plan_immediately(&self, plan: &Plan) -> Result<()> {
        use colors::*;

        for step in &plan.commands {
            if self.verbose {
                eprintln!("{DIM}${RESET} {}", step.command);
            }

            let output = execute_and_capture(&step.command)?;

            if output.success {
                let out = output.primary_output();
                print!("{}", out);
                if !out.ends_with('\n') && !out.is_empty() {
                    println!();
                }
            } else {
                print_error(&format!("Command failed: {}", step.command));
                let out = output.primary_output();
                if !out.trim().is_empty() {
                    eprintln!("{}", out);
                }
                // Stop on first failure
                return Ok(());
            }
        }
        Ok(())
    }

    /// Execute with Plan UI - shows plan, prompts user, then executes
    fn execute_with_plan(&self, plan: Plan) -> Result<()> {
        // Display the plan
        plan.display();

        // Multi-step plans ALWAYS prompt (this is the "Prompt-to-Plan" feature)
        // The whole point is to show what will happen and let user decide
        let action = plan.prompt_action()?;

        match action {
            PlanAction::Execute => plan.execute(false),
            PlanAction::DryRun => plan.execute(true),
            PlanAction::Cancel => {
                print_info("Cancelled");
                Ok(())
            }
        }
    }

    /// Confirm before executing a command
    fn confirm_execution(&self, command: &str, is_dangerous: bool) -> Result<bool> {
        use colors::*;

        eprintln!("\n{DIM}Command:{RESET} {BOLD}{}{RESET}", command);

        if is_dangerous {
            eprint!("{RED}[DANGEROUS]{RESET} Execute? Type 'yes' to confirm: ");
        } else {
            eprint!("{CX_PURPLE}▶{RESET} Execute? [Y/n] ");
        }
        io::stderr().flush()?;

        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        let input = input.trim().to_lowercase();

        let confirmed = if is_dangerous {
            input == "yes"
        } else {
            input.is_empty() || input == "y" || input == "yes"
        };

        if !confirmed {
            print_info("Skipped");
        }
        Ok(confirmed)
    }

    /// Show suggestion without executing (--no-exec mode)
    fn show_suggestion(
        &self,
        response: &str,
        extraction: &super::ask_executor::ExtractionResult,
    ) -> Result<()> {
        match self.format.as_str() {
            "json" => println!("{}", response),
            "commands" => {
                for cmd in &extraction.commands {
                    println!("{}", cmd.command);
                }
            }
            _ => self.print_ai_response(response),
        }
        Ok(())
    }

    /// Print AI response text
    fn print_ai_response(&self, response: &str) {
        use colors::*;

        if let Ok(json) = serde_json::from_str::<serde_json::Value>(response) {
            if json.get("status").and_then(|s| s.as_str()) == Some("no_ai") {
                if let Some(msg) = json.get("message").and_then(|m| m.as_str()) {
                    eprintln!("{YELLOW}{msg}{RESET}");
                }
                if let Some(hint) = json.get("hint").and_then(|h| h.as_str()) {
                    eprintln!("\n{DIM}Hint:{RESET} {hint}");
                }
                return;
            }
            if let Some(ai_response) = json.get("response").and_then(|r| r.as_str()) {
                println!("{}", ai_response);
                return;
            }
        }
        println!("{}", response);
    }

    /// Try to match query against CX command patterns
    fn try_cx_command(&self, query: &str) -> Result<Option<()>> {
        let matcher = PatternMatcher::new();
        let context = ProjectContext::detect();

        if let Some(pattern_match) = matcher.match_query(query) {
            if pattern_match.confidence >= 0.7 {
                let mut command = pattern_match.command.clone();

                if pattern_match.needs_name {
                    let name = matcher
                        .extract_name(query)
                        .unwrap_or_else(|| context.smart_snapshot_name());
                    command = command.replace("{name}", &name);
                }

                if self.verbose {
                    eprintln!("{}", pattern_match.description);
                }

                // Execute the CX command
                if self.verbose {
                    eprintln!("$ {}", command);
                }
                let status = Command::new("sh").arg("-c").arg(&command).status()?;
                if !status.success() {
                    eprintln!("Command failed with exit code: {:?}", status.code());
                }
                return Ok(Some(()));
            }
        }
        Ok(None)
    }

    fn run_interactive(&self) -> Result<()> {
        use colors::*;
        eprintln!("{CX_PURPLE}▶{RESET} Enter your question (Ctrl+D to finish):");
        let mut input = String::new();
        io::stdin().read_to_string(&mut input)?;

        let query = input.trim();
        if query.is_empty() {
            anyhow::bail!("No query provided");
        }

        if let Some(_) = self.try_cx_command(query)? {
            return Ok(());
        }

        let response = self.query_ai(query)?;
        self.handle_agentic_response(query, &response)
    }

    fn query_ai(&self, query: &str) -> Result<String> {
        // Try daemon first
        if let Some(response) = self.try_daemon(query)? {
            return Ok(response);
        }

        // Try Claude API
        if !self.local_only {
            if let Ok(api_key) = env::var("ANTHROPIC_API_KEY") {
                if !api_key.is_empty() && api_key.starts_with("sk-") {
                    if let Ok(response) = self.query_claude(query, &api_key) {
                        return Ok(response);
                    }
                }
            }
        }

        // Try Ollama (auto-detect at localhost:11434 if OLLAMA_HOST not set)
        let ollama_host = env::var("OLLAMA_HOST")
            .unwrap_or_else(|_| "http://localhost:11434".to_string());
        if let Ok(response) = self.query_ollama(query, &ollama_host) {
            return Ok(response);
        }

        // No AI available
        let response = serde_json::json!({
            "status": "no_ai",
            "message": "No AI backend available.",
            "hint": "Set ANTHROPIC_API_KEY or OLLAMA_HOST"
        });
        Ok(serde_json::to_string_pretty(&response)?)
    }

    fn try_daemon(&self, query: &str) -> Result<Option<String>> {
        let uid = unsafe { libc::getuid() };
        let user_socket = CX_USER_SOCKET_TEMPLATE.replace("{}", &uid.to_string());

        let socket_path = if Path::new(&user_socket).exists() {
            user_socket
        } else if Path::new(CX_DAEMON_SOCKET).exists() {
            CX_DAEMON_SOCKET.to_string()
        } else {
            return Ok(None);
        };

        match UnixStream::connect(&socket_path) {
            Ok(mut stream) => {
                let request = serde_json::json!({
                    "type": "ask",
                    "query": query,
                    "local_only": self.local_only,
                });
                stream.write_all(&serde_json::to_vec(&request)?)?;
                stream.shutdown(std::net::Shutdown::Write)?;

                let mut response = String::new();
                stream.read_to_string(&mut response)?;
                Ok(Some(response))
            }
            Err(_) => Ok(None),
        }
    }

    fn query_claude(&self, query: &str, api_key: &str) -> Result<String> {
        let context = ProjectContext::detect();
        let system_prompt = build_agent_prompt(&context);

        let payload = serde_json::json!({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": query}]
        });

        let output = Command::new("curl")
            .args([
                "-s", "-X", "POST",
                "https://api.anthropic.com/v1/messages",
                "-H", &format!("x-api-key: {}", api_key),
                "-H", "anthropic-version: 2023-06-01",
                "-H", "content-type: application/json",
                "-d", &payload.to_string(),
            ])
            .output()?;

        if output.status.success() {
            let response: serde_json::Value = serde_json::from_slice(&output.stdout)?;
            if let Some(content) = response["content"][0]["text"].as_str() {
                return Ok(serde_json::json!({
                    "status": "success",
                    "source": "claude",
                    "response": content,
                }).to_string());
            }
        }
        anyhow::bail!("Claude API request failed")
    }

    fn query_ollama(&self, query: &str, host: &str) -> Result<String> {
        // Get model from env, or auto-detect best available model
        let model = env::var("OLLAMA_MODEL").unwrap_or_else(|_| {
            // Try to get best available model (prefer larger models)
            if let Ok(output) = Command::new("curl")
                .args(["-s", &format!("{}/api/tags", host)])
                .output()
            {
                if let Ok(tags) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                    if let Some(models) = tags["models"].as_array() {
                        // Prefer 7b+ models over smaller ones
                        for model in models {
                            if let Some(name) = model["name"].as_str() {
                                if name.contains("7b") || name.contains("8b") || name.contains("13b") {
                                    return name.to_string();
                                }
                            }
                        }
                        // Fallback to first model
                        if let Some(first) = models.first() {
                            if let Some(name) = first["name"].as_str() {
                                return name.to_string();
                            }
                        }
                    }
                }
            }
            "llama3".to_string() // fallback
        });

        let context = ProjectContext::detect();
        let system_prompt = build_agent_prompt(&context);

        let payload = serde_json::json!({
            "model": model,
            "system": system_prompt,
            "prompt": query,
            "stream": false
        });

        let output = Command::new("curl")
            .args([
                "-s", "-X", "POST",
                &format!("{}/api/generate", host),
                "-H", "content-type: application/json",
                "-d", &payload.to_string(),
            ])
            .output()?;

        if output.status.success() {
            let response: serde_json::Value = serde_json::from_slice(&output.stdout)?;
            if let Some(text) = response["response"].as_str() {
                return Ok(serde_json::json!({
                    "status": "success",
                    "source": "ollama",
                    "response": text,
                }).to_string());
            }
        }
        anyhow::bail!("Ollama request failed")
    }
}

/// Detect OS for appropriate commands
fn detect_os() -> &'static str {
    if cfg!(target_os = "macos") {
        "macOS - USE MACOS COMMANDS ONLY: brew (not apt), top/vm_stat (not free), ifconfig (not ip), diskutil (not fdisk), launchctl (not systemctl), pbcopy/pbpaste"
    } else if cfg!(target_os = "linux") {
        "CX Linux / Debian-based - use apt, systemctl, ip addr, free, etc."
    } else {
        "Linux"
    }
}

/// Build the agent-focused system prompt
fn build_agent_prompt(context: &ProjectContext) -> String {
    let is_macos = cfg!(target_os = "macos");

    format!(
        r#"You are CX, an AI terminal assistant.

OS: {os}
Directory: {cwd}

If the user wants to DO something on their computer (check files, install software, see system info, run programs), give a shell command in ```bash block.

If the user is just TALKING to you (greetings, questions about you, chitchat), respond naturally with text - no commands.

Keep commands simple. One command when possible. No explanations unless asked."#,
        os = if is_macos { "macOS (use brew, not apt)" } else { "Linux" },
        cwd = context.cwd.display(),
    )
}

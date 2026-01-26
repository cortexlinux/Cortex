//! CX Terminal: Agentic AI execution
//!
//! True agent behavior - executes commands and returns results,
//! not just suggestions. Safe queries run automatically.

use anyhow::Result;
use std::process::Command;

/// Categories of commands by safety level
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum CommandSafety {
    /// Read-only, safe to auto-execute (ls, pwd, date, cat, etc.)
    Safe,
    /// Modifies state but recoverable (mkdir, touch, git add)
    Moderate,
    /// Potentially destructive (rm, mv, dd, chmod)
    Dangerous,
    /// Never auto-execute (rm -rf /, format, etc.)
    Blocked,
}

/// Patterns for safe read-only commands that can auto-execute
const SAFE_PATTERNS: &[&str] = &[
    "ls", "pwd", "date", "whoami", "hostname", "uname",
    "cat", "head", "tail", "less", "more", "wc",
    "df", "du", "free", "top", "ps", "uptime",
    "which", "whereis", "type", "file", "stat",
    "echo", "printf", "env", "printenv",
    "git status", "git log", "git diff", "git branch",
    "docker ps", "docker images", "docker logs",
    "npm list", "pip list", "cargo --version",
    "curl -I", "ping -c", "dig", "nslookup", "host",
    "id", "groups", "last", "w", "who",
    "find", "grep", "awk", "sed -n", "sort", "uniq",
    "ip addr", "ifconfig", "netstat", "ss",
];

/// Patterns for moderate-risk commands (need confirmation)
const MODERATE_PATTERNS: &[&str] = &[
    "mkdir", "touch", "cp", "git add", "git commit",
    "npm install", "pip install", "cargo build",
    "docker run", "docker start", "docker stop",
    "brew install", "apt install", "dnf install",
];

/// Patterns for dangerous commands (explicit confirmation required)
const DANGEROUS_PATTERNS: &[&str] = &[
    "rm", "mv", "dd", "chmod", "chown",
    "git reset", "git rebase", "git push --force",
    "docker rm", "docker rmi", "docker system prune",
    "kill", "pkill", "killall",
    "systemctl stop", "systemctl disable",
];

/// Patterns that should never be auto-executed
const BLOCKED_PATTERNS: &[&str] = &[
    "rm -rf /",
    "rm -rf /*",
    "dd if=/dev/zero of=/dev/sd",
    "mkfs",
    ":(){:|:&};:",
    "> /dev/sda",
    "chmod -R 777 /",
];

/// Classify a command's safety level
pub fn classify_command(cmd: &str) -> CommandSafety {
    let cmd_lower = cmd.to_lowercase();
    let cmd_trimmed = cmd_lower.trim();

    // Check blocked first
    for pattern in BLOCKED_PATTERNS {
        if cmd_trimmed.contains(pattern) {
            return CommandSafety::Blocked;
        }
    }

    // SUDO = ALWAYS requires confirmation (Mike's "No Silent Sudo" rule)
    if cmd_trimmed.starts_with("sudo ") {
        // Check if the sudo command is dangerous
        for pattern in DANGEROUS_PATTERNS {
            if cmd_trimmed.contains(pattern) {
                return CommandSafety::Dangerous;
            }
        }
        // Sudo commands are at minimum Moderate (require confirmation)
        return CommandSafety::Moderate;
    }

    // Check dangerous
    for pattern in DANGEROUS_PATTERNS {
        if cmd_trimmed.starts_with(pattern) || cmd_trimmed.contains(&format!(" {}", pattern)) {
            return CommandSafety::Dangerous;
        }
    }

    // Check moderate
    for pattern in MODERATE_PATTERNS {
        if cmd_trimmed.starts_with(pattern) || cmd_trimmed.contains(&format!(" {}", pattern)) {
            return CommandSafety::Moderate;
        }
    }

    // Check safe
    for pattern in SAFE_PATTERNS {
        if cmd_trimmed.starts_with(pattern) {
            return CommandSafety::Safe;
        }
    }

    // Unknown commands default to moderate (need confirmation)
    CommandSafety::Moderate
}

/// Execute a command and capture its output
pub fn execute_and_capture(cmd: &str) -> Result<CommandOutput> {
    let output = Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()?;

    Ok(CommandOutput {
        stdout: String::from_utf8_lossy(&output.stdout).to_string(),
        stderr: String::from_utf8_lossy(&output.stderr).to_string(),
        success: output.status.success(),
        exit_code: output.status.code(),
    })
}

/// Result of command execution
#[derive(Debug)]
pub struct CommandOutput {
    pub stdout: String,
    pub stderr: String,
    pub success: bool,
    pub exit_code: Option<i32>,
}

impl CommandOutput {
    /// Get the primary output (stdout if available, stderr otherwise)
    pub fn primary_output(&self) -> &str {
        if !self.stdout.trim().is_empty() {
            &self.stdout
        } else {
            &self.stderr
        }
    }
}

/// Agent execution mode
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AgentMode {
    /// Auto-execute safe commands, confirm others
    Auto,
    /// Always confirm before executing
    Confirm,
    /// Never execute, just suggest
    Suggest,
}

impl Default for AgentMode {
    fn default() -> Self {
        AgentMode::Auto
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_safe_commands() {
        assert_eq!(classify_command("ls -la"), CommandSafety::Safe);
        assert_eq!(classify_command("pwd"), CommandSafety::Safe);
        assert_eq!(classify_command("date"), CommandSafety::Safe);
        assert_eq!(classify_command("git status"), CommandSafety::Safe);
    }

    #[test]
    fn test_moderate_commands() {
        assert_eq!(classify_command("mkdir test"), CommandSafety::Moderate);
        assert_eq!(classify_command("npm install express"), CommandSafety::Moderate);
    }

    #[test]
    fn test_dangerous_commands() {
        assert_eq!(classify_command("rm file.txt"), CommandSafety::Dangerous);
        assert_eq!(classify_command("chmod 777 file"), CommandSafety::Dangerous);
    }

    #[test]
    fn test_blocked_commands() {
        assert_eq!(classify_command("rm -rf /"), CommandSafety::Blocked);
    }
}

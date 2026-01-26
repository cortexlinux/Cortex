//! CX Terminal: Command extraction and safe execution
//!
//! Extracts executable commands from AI responses and handles safe execution
//! with user confirmation and dangerous command detection.

use anyhow::Result;
use std::io::{self, Write};
use std::process::Command;

/// Commands that require extra confirmation due to potential damage
const DANGEROUS_PATTERNS: &[&str] = &[
    "rm -rf",
    "rm -r /",
    "dd if=",
    "mkfs",
    "> /dev/",
    "chmod 777",
    "chmod -R 777",
    ":(){:|:&};:",  // Fork bomb
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
];

/// Commands that should never be executed automatically
const BLOCKED_PATTERNS: &[&str] = &[
    "rm -rf /",
    "rm -rf /*",
    "dd if=/dev/zero of=/dev/sd",
    ":(){:|:&};:",
];

/// Extracted command with metadata
#[derive(Debug, Clone)]
pub struct ExtractedCommand {
    pub command: String,
    pub language: String,
    pub is_dangerous: bool,
    pub is_blocked: bool,
    pub description: Option<String>,
}

impl ExtractedCommand {
    fn new(command: String, language: String) -> Self {
        let is_dangerous = DANGEROUS_PATTERNS
            .iter()
            .any(|p| command.contains(p));

        let is_blocked = BLOCKED_PATTERNS
            .iter()
            .any(|p| command.contains(p));

        Self {
            command,
            language,
            is_dangerous,
            is_blocked,
            description: None,
        }
    }

    fn with_description(mut self, desc: String) -> Self {
        self.description = Some(desc);
        self
    }
}

/// Result of command extraction
#[derive(Debug)]
pub struct ExtractionResult {
    pub commands: Vec<ExtractedCommand>,
    pub explanation: Option<String>,
}

/// Extract commands from AI response text
///
/// Supports multiple formats:
/// - Markdown code blocks (```bash ... ```)
/// - JSON with "command" or "commands" field
/// - Plain text with $ prefix
pub fn extract_commands(response: &str) -> ExtractionResult {
    let mut commands = Vec::new();
    let mut explanation = None;

    // Try JSON extraction first
    if let Ok(json) = serde_json::from_str::<serde_json::Value>(response) {
        if let Some(cmds) = extract_from_json(&json) {
            commands.extend(cmds);
        }
        if let Some(exp) = json.get("explanation").and_then(|e| e.as_str()) {
            explanation = Some(exp.to_string());
        }
        if let Some(resp) = json.get("response").and_then(|r| r.as_str()) {
            // AI response may contain markdown code blocks
            let inner_cmds = extract_from_markdown(resp);
            commands.extend(inner_cmds);
            if explanation.is_none() {
                explanation = Some(extract_explanation(resp));
            }
        }
    } else {
        // Plain text - try markdown extraction
        commands.extend(extract_from_markdown(response));
        explanation = Some(extract_explanation(response));
    }

    ExtractionResult { commands, explanation }
}

/// Extract commands from JSON structure
fn extract_from_json(json: &serde_json::Value) -> Option<Vec<ExtractedCommand>> {
    let mut commands = Vec::new();

    // Single command field
    if let Some(cmd) = json.get("command").and_then(|c| c.as_str()) {
        let desc = json.get("description").and_then(|d| d.as_str());
        let mut extracted = ExtractedCommand::new(cmd.to_string(), "bash".to_string());
        if let Some(d) = desc {
            extracted = extracted.with_description(d.to_string());
        }
        commands.push(extracted);
    }

    // Multiple commands array
    if let Some(cmds) = json.get("commands").and_then(|c| c.as_array()) {
        for cmd_val in cmds {
            if let Some(cmd) = cmd_val.as_str() {
                commands.push(ExtractedCommand::new(cmd.to_string(), "bash".to_string()));
            } else if let Some(obj) = cmd_val.as_object() {
                if let Some(cmd) = obj.get("command").and_then(|c| c.as_str()) {
                    let mut extracted = ExtractedCommand::new(cmd.to_string(), "bash".to_string());
                    if let Some(desc) = obj.get("description").and_then(|d| d.as_str()) {
                        extracted = extracted.with_description(desc.to_string());
                    }
                    commands.push(extracted);
                }
            }
        }
    }

    if commands.is_empty() {
        None
    } else {
        Some(commands)
    }
}

/// Extract commands from markdown code blocks
fn extract_from_markdown(text: &str) -> Vec<ExtractedCommand> {
    let mut commands = Vec::new();
    let mut in_code_block = false;
    let mut current_lang = String::new();
    let mut current_code = String::new();

    for line in text.lines() {
        if line.starts_with("```") {
            if in_code_block {
                // End of code block
                let code = current_code.trim();
                if !code.is_empty() && is_executable_language(&current_lang) {
                    // Split multi-line commands
                    for cmd_line in code.lines() {
                        let cmd = cmd_line.trim();
                        if !cmd.is_empty() && !cmd.starts_with('#') && looks_like_command(cmd) {
                            commands.push(ExtractedCommand::new(
                                cmd.to_string(),
                                current_lang.clone(),
                            ));
                        }
                    }
                }
                current_code.clear();
                in_code_block = false;
            } else {
                // Start of code block
                current_lang = line.trim_start_matches('`').trim().to_string();
                if current_lang.is_empty() {
                    current_lang = "bash".to_string();
                }
                in_code_block = true;
            }
        } else if in_code_block {
            current_code.push_str(line);
            current_code.push('\n');
        }
    }

    // Also extract $ prefixed commands outside code blocks
    if commands.is_empty() {
        for line in text.lines() {
            let trimmed = line.trim();
            if trimmed.starts_with("$ ") {
                let cmd = trimmed.trim_start_matches("$ ");
                if !cmd.is_empty() && looks_like_command(cmd) {
                    commands.push(ExtractedCommand::new(cmd.to_string(), "bash".to_string()));
                }
            }
        }
    }

    commands
}

/// Check if text looks like an actual shell command (not just random text)
fn looks_like_command(text: &str) -> bool {
    let text = text.trim();

    // Empty or too short
    if text.len() < 2 {
        return false;
    }

    // Starts with common command patterns
    let first_word = text.split_whitespace().next().unwrap_or("");

    // Must start with a valid command character (letter, dot, slash, or $)
    let first_char = first_word.chars().next().unwrap_or(' ');
    if !first_char.is_ascii_alphabetic() && first_char != '.' && first_char != '/' && first_char != '$' {
        return false;
    }

    // Reject if it looks like a sentence (contains question mark, starts with capital + has spaces)
    if text.contains('?') {
        return false;
    }

    // Reject if first word is a common English word that's not a command
    let non_commands = [
        "why", "what", "how", "when", "where", "who", "which", "because",
        "the", "a", "an", "is", "are", "was", "were", "been", "being",
        "i", "you", "he", "she", "it", "we", "they", "my", "your", "our",
        "this", "that", "these", "those", "here", "there",
        "yes", "no", "maybe", "perhaps", "probably",
        "hello", "hi", "hey", "goodbye", "bye",
        "please", "thanks", "thank", "sorry",
    ];

    let first_lower = first_word.to_lowercase();
    if non_commands.contains(&first_lower.as_str()) {
        return false;
    }

    // Looks reasonable
    true
}

/// Check if a code block language is executable
fn is_executable_language(lang: &str) -> bool {
    matches!(
        lang.to_lowercase().as_str(),
        "bash" | "sh" | "shell" | "zsh" | "fish" | ""
    )
}

/// Extract explanation text (non-code content)
fn extract_explanation(text: &str) -> String {
    let mut explanation = String::new();
    let mut in_code_block = false;

    for line in text.lines() {
        if line.starts_with("```") {
            in_code_block = !in_code_block;
        } else if !in_code_block {
            let trimmed = line.trim();
            if !trimmed.is_empty() && !trimmed.starts_with('$') {
                if !explanation.is_empty() {
                    explanation.push(' ');
                }
                explanation.push_str(trimmed);
            }
        }
    }

    explanation
}

/// Execute commands with proper safety checks
pub struct CommandExecutor {
    auto_confirm: bool,
    verbose: bool,
}

impl CommandExecutor {
    pub fn new(auto_confirm: bool, verbose: bool) -> Self {
        Self { auto_confirm, verbose }
    }

    /// Execute a list of extracted commands
    pub fn execute(&self, commands: &[ExtractedCommand]) -> Result<()> {
        if commands.is_empty() {
            if self.verbose {
                eprintln!("No executable commands found in response.");
            }
            return Ok(());
        }

        for (i, cmd) in commands.iter().enumerate() {
            if cmd.is_blocked {
                eprintln!("\n[BLOCKED] Dangerous command rejected: {}", cmd.command);
                continue;
            }

            self.execute_single(cmd, i + 1, commands.len())?;
        }

        Ok(())
    }

    fn execute_single(&self, cmd: &ExtractedCommand, index: usize, total: usize) -> Result<()> {
        // Show command info
        if total > 1 {
            eprintln!("\n[{}/{}] Command:", index, total);
        } else {
            eprintln!("\nCommand to execute:");
        }

        if let Some(desc) = &cmd.description {
            eprintln!("  # {}", desc);
        }
        eprintln!("  $ {}", cmd.command);

        // Extra warning for dangerous commands
        if cmd.is_dangerous {
            eprintln!("\n  [WARNING] This command may be destructive!");
        }

        // Get confirmation unless auto-confirm is enabled
        if !self.auto_confirm {
            let prompt = if cmd.is_dangerous {
                "Execute this DANGEROUS command? [yes/NO] "
            } else {
                "Execute? [Y/n] "
            };
            eprint!("\n{}", prompt);
            io::stderr().flush()?;

            let mut input = String::new();
            io::stdin().read_line(&mut input)?;
            let input = input.trim().to_lowercase();

            let confirmed = if cmd.is_dangerous {
                input == "yes"  // Require full "yes" for dangerous commands
            } else {
                input.is_empty() || input == "y" || input == "yes"
            };

            if !confirmed {
                eprintln!("Skipped.");
                return Ok(());
            }
        }

        // Execute the command
        if self.verbose {
            eprintln!("Executing: {}", cmd.command);
        }

        let status = Command::new("sh")
            .arg("-c")
            .arg(&cmd.command)
            .status()?;

        if status.success() {
            eprintln!("[OK]");
        } else {
            eprintln!("[FAILED] Exit code: {:?}", status.code());
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_from_markdown() {
        let response = "To list files:\n```bash\nls -la\n```";
        let result = extract_commands(response);
        assert_eq!(result.commands.len(), 1);
        assert_eq!(result.commands[0].command, "ls -la");
    }

    #[test]
    fn test_extract_multiple_commands() {
        let response = "```bash\necho hello\necho world\n```";
        let result = extract_commands(response);
        assert_eq!(result.commands.len(), 2);
    }

    #[test]
    fn test_dangerous_detection() {
        // "dd if=" is dangerous but not blocked
        let cmd = ExtractedCommand::new("dd if=/dev/zero of=test.img bs=1M count=100".to_string(), "bash".to_string());
        assert!(cmd.is_dangerous);
        assert!(!cmd.is_blocked);
    }

    #[test]
    fn test_blocked_detection() {
        let cmd = ExtractedCommand::new("rm -rf /".to_string(), "bash".to_string());
        assert!(cmd.is_blocked);
    }

    #[test]
    fn test_extract_from_json() {
        let response = r#"{"command": "ls -la", "description": "List files"}"#;
        let result = extract_commands(response);
        assert_eq!(result.commands.len(), 1);
        assert_eq!(result.commands[0].description, Some("List files".to_string()));
    }
}

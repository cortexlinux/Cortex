//! CX Terminal: Prompt-to-Plan UI
//!
//! Shows a numbered plan of commands before execution.
//! User can Execute, Dry-run, or Cancel.

use std::io::{self, Write};

use super::ask_agent::{classify_command, execute_and_capture, CommandSafety};
use super::ask_executor::ExtractedCommand;
use super::branding::colors;

/// A plan of commands to execute
#[derive(Debug)]
pub struct Plan {
    pub commands: Vec<PlanStep>,
    pub requires_sudo: bool,
    pub sudo_count: usize,
}

/// A single step in the plan
#[derive(Debug)]
pub struct PlanStep {
    pub number: usize,
    pub command: String,
    pub safety: CommandSafety,
    pub is_sudo: bool,
}

impl Plan {
    /// Create a plan from extracted commands
    pub fn from_commands(commands: &[ExtractedCommand]) -> Self {
        let steps: Vec<PlanStep> = commands
            .iter()
            .enumerate()
            .map(|(i, cmd)| {
                let is_sudo = cmd.command.trim().to_lowercase().starts_with("sudo ");
                PlanStep {
                    number: i + 1,
                    command: cmd.command.clone(),
                    safety: classify_command(&cmd.command),
                    is_sudo,
                }
            })
            .collect();

        let sudo_count = steps.iter().filter(|s| s.is_sudo).count();
        let requires_sudo = sudo_count > 0;

        Plan {
            commands: steps,
            requires_sudo,
            sudo_count,
        }
    }

    /// Check if plan has any blocked commands
    pub fn has_blocked(&self) -> bool {
        self.commands.iter().any(|s| s.safety == CommandSafety::Blocked)
    }

    /// Check if plan has any dangerous commands
    pub fn has_dangerous(&self) -> bool {
        self.commands.iter().any(|s| s.safety == CommandSafety::Dangerous)
    }

    /// Display the plan to the user
    pub fn display(&self) {
        use colors::*;

        println!("\n{CX_PURPLE}📋 Plan:{RESET}");

        for step in &self.commands {
            let safety_indicator = match step.safety {
                CommandSafety::Safe => format!("{GREEN}"),
                CommandSafety::Moderate => format!("{YELLOW}"),
                CommandSafety::Dangerous => format!("{RED}"),
                CommandSafety::Blocked => format!("{RED}[BLOCKED] "),
            };

            println!("  {DIM}{}.{RESET} {safety_indicator}{}{RESET}",
                step.number,
                step.command
            );
        }

        println!();

        // Show warnings
        if self.requires_sudo {
            println!("{YELLOW}⚠️  Requires sudo{RESET} ({} command{})",
                self.sudo_count,
                if self.sudo_count > 1 { "s" } else { "" }
            );
        }

        if self.has_dangerous() {
            println!("{RED}⚠️  Contains dangerous commands - review carefully{RESET}");
        }

        if self.has_blocked() {
            println!("{RED}🚫 Contains blocked commands that will not execute{RESET}");
        }

        println!();
    }

    /// Prompt user for action and return choice
    pub fn prompt_action(&self) -> io::Result<PlanAction> {
        use colors::*;

        if self.has_blocked() {
            println!("{RED}Cannot execute: plan contains blocked commands{RESET}");
            return Ok(PlanAction::Cancel);
        }

        // Different prompt based on danger level
        if self.has_dangerous() || self.requires_sudo {
            eprint!("{CX_PURPLE}▶{RESET} [{BOLD}E{RESET}]xecute  [{BOLD}D{RESET}]ry-run  [{BOLD}C{RESET}]ancel > ");
        } else {
            eprint!("{CX_PURPLE}▶{RESET} [{BOLD}E{RESET}]xecute  [{BOLD}D{RESET}]ry-run  [{BOLD}C{RESET}]ancel (or Enter to execute) > ");
        }
        io::stderr().flush()?;

        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        let input = input.trim().to_lowercase();

        let action = match input.as_str() {
            "e" | "execute" => PlanAction::Execute,
            "d" | "dry-run" | "dry" => PlanAction::DryRun,
            "c" | "cancel" | "q" | "quit" => PlanAction::Cancel,
            "" => {
                // Enter = execute only if safe
                if self.has_dangerous() || self.requires_sudo {
                    println!("{YELLOW}Please type 'e' to execute or 'c' to cancel{RESET}");
                    return self.prompt_action(); // Ask again
                }
                PlanAction::Execute
            }
            _ => {
                println!("{DIM}Unknown option. Use E/D/C{RESET}");
                return self.prompt_action(); // Ask again
            }
        };

        Ok(action)
    }

    /// Execute the plan
    pub fn execute(&self, dry_run: bool) -> anyhow::Result<()> {
        use colors::*;

        if dry_run {
            println!("\n{CYAN}🔍 Dry-run mode - showing what would execute:{RESET}\n");
            for step in &self.commands {
                if step.safety == CommandSafety::Blocked {
                    println!("  {RED}[SKIP]{RESET} {} {DIM}(blocked){RESET}", step.command);
                } else {
                    println!("  {DIM}${RESET} {}", step.command);
                }
            }
            println!("\n{DIM}No commands were executed.{RESET}");
            return Ok(());
        }

        // Actually execute
        println!();
        for step in &self.commands {
            if step.safety == CommandSafety::Blocked {
                println!("{RED}[SKIP]{RESET} {} {DIM}(blocked){RESET}", step.command);
                continue;
            }

            println!("{DIM}${RESET} {}", step.command);

            let output = execute_and_capture(&step.command)?;

            if output.success {
                let out = output.primary_output();
                if !out.trim().is_empty() {
                    print!("{}", out);
                    if !out.ends_with('\n') {
                        println!();
                    }
                }
            } else {
                println!("{RED}✗ Command failed{RESET}");
                let out = output.primary_output();
                if !out.trim().is_empty() {
                    eprintln!("{}", out);
                }
                // Stop on first failure
                println!("{YELLOW}Stopping execution due to error{RESET}");
                return Ok(());
            }
        }

        println!("\n{GREEN}✓ Plan executed successfully{RESET}");
        Ok(())
    }
}

/// User's chosen action for the plan
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum PlanAction {
    Execute,
    DryRun,
    Cancel,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_plan_creation() {
        let commands = vec![
            ExtractedCommand {
                command: "ls -la".to_string(),
                language: "bash".to_string(),
                is_dangerous: false,
                is_blocked: false,
                description: None,
            },
            ExtractedCommand {
                command: "sudo apt update".to_string(),
                language: "bash".to_string(),
                is_dangerous: false,
                is_blocked: false,
                description: None,
            },
        ];

        let plan = Plan::from_commands(&commands);
        assert_eq!(plan.commands.len(), 2);
        assert!(plan.requires_sudo);
        assert_eq!(plan.sudo_count, 1);
    }
}

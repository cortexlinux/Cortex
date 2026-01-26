//! CX Terminal: Branding and styling
//!
//! ASCII art logo and branded output for CX Terminal.

/// CX Terminal ASCII art logo (compact)
pub const CX_LOGO: &str = r#"
   ██████╗██╗  ██╗
  ██╔════╝╚██╗██╔╝
  ██║      ╚███╔╝
  ██║      ██╔██╗
  ╚██████╗██╔╝ ██╗
   ╚═════╝╚═╝  ╚═╝
"#;

/// CX Terminal ASCII art logo (mini)
pub const CX_LOGO_MINI: &str = r#"▄▀▀ ▀▄▀
▀▄▄ █ █"#;

/// ANSI color codes for CX purple theme
pub mod colors {
    pub const RESET: &str = "\x1b[0m";
    pub const BOLD: &str = "\x1b[1m";
    pub const DIM: &str = "\x1b[2m";

    // CX Purple theme
    pub const CX_PURPLE: &str = "\x1b[38;5;135m";  // Light purple
    pub const CX_DARK: &str = "\x1b[38;5;99m";    // Darker purple
    pub const CX_ACCENT: &str = "\x1b[38;5;219m"; // Pink accent

    // Standard colors
    pub const GREEN: &str = "\x1b[32m";
    pub const YELLOW: &str = "\x1b[33m";
    pub const RED: &str = "\x1b[31m";
    pub const CYAN: &str = "\x1b[36m";
    pub const WHITE: &str = "\x1b[37m";
}

/// Print the branded version info
pub fn print_version(version: &str) {
    use colors::*;

    println!("{CX_PURPLE}{CX_LOGO}{RESET}");
    println!("{BOLD}{CX_PURPLE}CX Terminal{RESET} {DIM}v{version}{RESET}");
    println!("{DIM}AI-Native Terminal for CX Linux{RESET}");
    println!();
    println!("{CX_DARK}  Website:{RESET}  https://cxlinux.ai");
    println!("{CX_DARK}  GitHub:{RESET}   https://github.com/cxlinux-ai/cx");
    println!("{CX_DARK}  Support:{RESET}  support@cxlinux.com");
    println!();
}

/// Print a compact version line
pub fn print_version_line(version: &str) {
    use colors::*;
    println!("{CX_PURPLE}▶{RESET} {BOLD}CX{RESET} v{version}");
}

/// Print a branded header for agent output
pub fn print_agent_header() {
    use colors::*;
    print!("{CX_PURPLE}▶{RESET} ");
}

/// Print success message
pub fn print_success(msg: &str) {
    use colors::*;
    eprintln!("{GREEN}✓{RESET} {msg}");
}

/// Print error message
pub fn print_error(msg: &str) {
    use colors::*;
    eprintln!("{RED}✗{RESET} {msg}");
}

/// Print warning message
pub fn print_warning(msg: &str) {
    use colors::*;
    eprintln!("{YELLOW}!{RESET} {msg}");
}

/// Print info message
pub fn print_info(msg: &str) {
    use colors::*;
    eprintln!("{CYAN}→{RESET} {msg}");
}

/// Format a command for display
pub fn format_command(cmd: &str) -> String {
    use colors::*;
    format!("{DIM}${RESET} {BOLD}{cmd}{RESET}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_logo_not_empty() {
        assert!(!CX_LOGO.is_empty());
        assert!(!CX_LOGO_MINI.is_empty());
    }
}

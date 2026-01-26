//! CX Terminal: Project scaffolding command
//!
//! Creates new projects from templates.
//! Example: cx new python my-project
//! Example: cx new react my-app
//! Example: cx new api my-backend

use anyhow::{Context, Result};
use clap::Parser;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use super::templates;

/// Create a new project from a template
#[derive(Debug, Parser, Clone)]
pub struct NewCommand {
    /// Template to use (python, node, react, api, docker, db, nextjs, fastapi)
    #[arg(value_parser, required_unless_present = "list")]
    pub template: Option<String>,

    /// Project name (will create directory with this name)
    #[arg(value_parser, required_unless_present = "list")]
    pub name: Option<String>,

    /// Directory to create project in (defaults to current directory)
    #[arg(long, short = 'd')]
    pub directory: Option<PathBuf>,

    /// Initialize git repository
    #[arg(long, default_value = "true")]
    pub git: bool,

    /// Install dependencies after scaffolding
    #[arg(long)]
    pub install: bool,

    /// List available templates
    #[arg(long, short = 'l')]
    pub list: bool,

    /// Verbose output
    #[arg(long, short = 'v')]
    pub verbose: bool,
}

impl NewCommand {
    pub fn run(&self) -> Result<()> {
        if self.list {
            return self.list_templates();
        }

        let template = self
            .template
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Template is required"))?;
        let name = self
            .name
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Project name is required"))?;

        let base_dir = self.directory.clone().unwrap_or_else(|| PathBuf::from("."));
        let project_dir = base_dir.join(name);

        if project_dir.exists() {
            anyhow::bail!("Directory '{}' already exists", project_dir.display());
        }

        println!("Creating {} project '{}'...", template, name);

        // Create project directory
        fs::create_dir_all(&project_dir)
            .with_context(|| format!("Failed to create directory: {}", project_dir.display()))?;

        // Generate template based on type
        self.create_template(&project_dir, template, name)?;

        // Initialize git if requested
        if self.git {
            self.init_git(&project_dir)?;
        }

        // Install dependencies if requested
        if self.install {
            self.install_deps(&project_dir)?;
        }

        println!("\n✅ Project '{}' created successfully!", name);
        println!("   cd {}", project_dir.display());

        Ok(())
    }

    fn create_template(&self, dir: &Path, template: &str, name: &str) -> Result<()> {
        match template.to_lowercase().as_str() {
            "python" | "py" => templates::create_python_project(dir, name, self.verbose),
            "node" | "nodejs" | "js" => templates::create_node_project(dir, name, self.verbose),
            "react" => templates::create_react_project(dir, name, self.verbose),
            "nextjs" | "next" => templates::create_nextjs_project(dir, name, self.verbose),
            "api" | "fastapi" => templates::create_fastapi_project(dir, name, self.verbose),
            "express" => templates::create_express_project(dir, name, self.verbose),
            "docker" => templates::create_docker_project(dir, name, self.verbose),
            "db" | "sqlite" => templates::create_db_project(dir, name, self.verbose),
            "rust" | "rs" => templates::create_rust_project(dir, name, self.verbose),
            "go" | "golang" => templates::create_go_project(dir, name, self.verbose),
            _ => anyhow::bail!(
                "Unknown template '{}'. Use --list to see available templates.",
                template
            ),
        }
    }

    fn list_templates(&self) -> Result<()> {
        println!("Available templates:\n");
        println!("  python, py       - Python project with uv/pip");
        println!("  node, nodejs, js - Node.js project with package.json");
        println!("  react            - React app with Vite");
        println!("  nextjs, next     - Next.js app");
        println!("  api, fastapi     - FastAPI backend");
        println!("  express          - Express.js backend");
        println!("  docker           - Docker project with Dockerfile + compose");
        println!("  db, sqlite       - SQLite database project");
        println!("  rust, rs         - Rust project with Cargo");
        println!("  go, golang       - Go project with go.mod");
        println!("\nExample: cx new python my-project");
        Ok(())
    }

    fn init_git(&self, dir: &Path) -> Result<()> {
        if self.verbose {
            println!("Initializing git repository...");
        }

        let output = Command::new("git")
            .args(["init"])
            .current_dir(dir)
            .output()
            .context("Failed to run git init")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            eprintln!("Warning: git init failed: {}", stderr);
        }

        Ok(())
    }

    fn install_deps(&self, dir: &Path) -> Result<()> {
        if self.verbose {
            println!("Installing dependencies...");
        }

        // Detect package manager and install
        if dir.join("package.json").exists() {
            self.install_node_deps(dir)?;
        } else if dir.join("pyproject.toml").exists() {
            self.install_python_deps(dir)?;
        } else if dir.join("Cargo.toml").exists() {
            self.install_cargo_deps(dir)?;
        } else if dir.join("go.mod").exists() {
            self.install_go_deps(dir)?;
        }

        Ok(())
    }

    fn install_node_deps(&self, dir: &Path) -> Result<()> {
        // Try bun first, then npm
        let bun_result = Command::new("bun").args(["install"]).current_dir(dir).status();

        if bun_result.is_err() || !bun_result.unwrap().success() {
            Command::new("npm")
                .args(["install"])
                .current_dir(dir)
                .status()
                .context("Failed to install npm dependencies")?;
        }
        Ok(())
    }

    fn install_python_deps(&self, dir: &Path) -> Result<()> {
        // Try uv first, then pip
        let uv_result = Command::new("uv").args(["sync"]).current_dir(dir).status();

        if uv_result.is_err() || !uv_result.unwrap().success() {
            Command::new("pip")
                .args(["install", "-e", "."])
                .current_dir(dir)
                .status()
                .context("Failed to install pip dependencies")?;
        }
        Ok(())
    }

    fn install_cargo_deps(&self, dir: &Path) -> Result<()> {
        Command::new("cargo")
            .args(["build"])
            .current_dir(dir)
            .status()
            .context("Failed to build Cargo project")?;
        Ok(())
    }

    fn install_go_deps(&self, dir: &Path) -> Result<()> {
        Command::new("go")
            .args(["mod", "tidy"])
            .current_dir(dir)
            .status()
            .context("Failed to run go mod tidy")?;
        Ok(())
    }
}

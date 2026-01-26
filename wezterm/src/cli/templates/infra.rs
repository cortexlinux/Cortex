//! CX Terminal: Infrastructure project templates
//!
//! Templates for Docker, SQLite, Rust, and Go projects.

use anyhow::{Context, Result};
use std::fs;
use std::path::Path;
use std::process::Command;

/// Create a Docker project with Dockerfile and compose
pub fn create_docker_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
        println!("Creating Docker project...");
    }

    // Dockerfile
    let dockerfile = r#"FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY . .

EXPOSE 3000

CMD ["node", "src/index.js"]
"#;
    fs::write(dir.join("Dockerfile"), dockerfile)?;

    // docker-compose.yml
    let compose = format!(
        r#"services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    volumes:
      - .:/app
      - /app/node_modules
    restart: unless-stopped

  # Uncomment to add a database
  # db:
  #   image: postgres:16-alpine
  #   environment:
  #     POSTGRES_USER: user
  #     POSTGRES_PASSWORD: password
  #     POSTGRES_DB: {name}
  #   volumes:
  #     - pgdata:/var/lib/postgresql/data
  #   ports:
  #     - "5432:5432"

# volumes:
#   pgdata:
"#,
        name = name
    );
    fs::write(dir.join("docker-compose.yml"), compose)?;

    // .dockerignore
    let dockerignore = r#"node_modules
npm-debug.log
.git
.gitignore
.env
README.md
"#;
    fs::write(dir.join(".dockerignore"), dockerignore)?;

    // README
    let readme = format!(
        "# {}\n\nA Docker project.\n\n## Build\n\n```bash\ndocker compose build\n```\n\n## Run\n\n```bash\ndocker compose up\n```\n\n## Stop\n\n```bash\ndocker compose down\n```\n",
        name
    );
    fs::write(dir.join("README.md"), readme)?;

    // .gitignore
    let gitignore = ".env\n";
    fs::write(dir.join(".gitignore"), gitignore)?;

    Ok(())
}

/// Create a SQLite database project
pub fn create_db_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
        println!("Creating SQLite database project...");
    }

    // Create directories
    fs::create_dir_all(dir.join("migrations"))?;

    // pyproject.toml
    let pyproject = format!(
        r#"[project]
name = "{name}"
version = "0.1.0"
description = "A SQLite database project"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"#,
        name = name
    );
    fs::write(dir.join("pyproject.toml"), pyproject)?;

    // db.py
    let db_py = format!(
        r#"#!/usr/bin/env python3
"""
{name} - SQLite database operations
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print(f"Database initialized at {{DB_PATH}}")


def add_item(name: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute("INSERT INTO items (name) VALUES (?)", (name,))
        return cursor.lastrowid


def get_items() -> list:
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM items")
        return cursor.fetchall()


if __name__ == "__main__":
    init_db()
    add_item("Example Item")
    print("Items:", get_items())
"#,
        name = name
    );
    fs::write(dir.join("db.py"), db_py)?;

    // migrations/001_init.sql
    let migration = r#"-- Initial migration
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"#;
    fs::write(dir.join("migrations/001_init.sql"), migration)?;

    // README
    let readme = format!(
        "# {}\n\nA SQLite database project.\n\n## Setup\n\n```bash\npython db.py\n```\n\n## Usage\n\nThe database will be created at `data.db`.\n",
        name
    );
    fs::write(dir.join("README.md"), readme)?;

    // .gitignore
    let gitignore = "*.db\n*.sqlite\n*.sqlite3\n__pycache__/\n.venv/\n";
    fs::write(dir.join(".gitignore"), gitignore)?;

    Ok(())
}

/// Create a Rust project using cargo
pub fn create_rust_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
        println!("Creating Rust project...");
    }

    // Use cargo init
    let output = Command::new("cargo")
        .args(["init", "--name", name])
        .current_dir(dir)
        .output()
        .context("Failed to run cargo init")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        anyhow::bail!("cargo init failed: {}", stderr);
    }

    // Add README
    let readme = format!(
        "# {}\n\nA Rust project.\n\n## Build\n\n```bash\ncargo build\n```\n\n## Run\n\n```bash\ncargo run\n```\n\n## Test\n\n```bash\ncargo test\n```\n",
        name
    );
    fs::write(dir.join("README.md"), readme)?;

    Ok(())
}

/// Create a Go project
pub fn create_go_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
        println!("Creating Go project...");
    }

    // go.mod
    let go_mod = format!(
        r#"module {}

go 1.22
"#,
        name
    );
    fs::write(dir.join("go.mod"), go_mod)?;

    // main.go
    let main_go = format!(
        r#"package main

import "fmt"

func main() {{
	fmt.Println("Hello from {}!")
}}
"#,
        name
    );
    fs::write(dir.join("main.go"), main_go)?;

    // README
    let readme = format!(
        "# {}\n\nA Go project.\n\n## Run\n\n```bash\ngo run .\n```\n\n## Build\n\n```bash\ngo build\n```\n\n## Test\n\n```bash\ngo test ./...\n```\n",
        name
    );
    fs::write(dir.join("README.md"), readme)?;

    // .gitignore
    let gitignore = format!("{}\n*.exe\n", name);
    fs::write(dir.join(".gitignore"), gitignore)?;

    Ok(())
}

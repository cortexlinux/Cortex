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

        let template = self.template.as_ref().ok_or_else(|| anyhow::anyhow!("Template is required"))?;
        let name = self.name.as_ref().ok_or_else(|| anyhow::anyhow!("Project name is required"))?;

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
        match template.to_lowercase().as_str() {
            "python" | "py" => self.create_python_project(&project_dir, name)?,
            "node" | "nodejs" | "js" => self.create_node_project(&project_dir, name)?,
            "react" => self.create_react_project(&project_dir, name)?,
            "nextjs" | "next" => self.create_nextjs_project(&project_dir, name)?,
            "api" | "fastapi" => self.create_fastapi_project(&project_dir, name)?,
            "express" => self.create_express_project(&project_dir, name)?,
            "docker" => self.create_docker_project(&project_dir, name)?,
            "db" | "sqlite" => self.create_db_project(&project_dir, name)?,
            "rust" | "rs" => self.create_rust_project(&project_dir, name)?,
            "go" | "golang" => self.create_go_project(&project_dir, name)?,
            _ => anyhow::bail!(
                "Unknown template '{}'. Use --list to see available templates.",
                template
            ),
        }

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

    fn create_python_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
            println!("Creating Python project structure...");
        }

        // Create directories
        fs::create_dir_all(dir.join("src"))?;
        fs::create_dir_all(dir.join("tests"))?;

        // pyproject.toml
        let pyproject = format!(
            r#"[project]
name = "{name}"
version = "0.1.0"
description = "A Python project"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
"#,
            name = name
        );
        fs::write(dir.join("pyproject.toml"), pyproject)?;

        // Main module
        let main_py = format!(
            r#"#!/usr/bin/env python3
"""
{name} - Main entry point
"""


def main() -> None:
    print("Hello from {name}!")


if __name__ == "__main__":
    main()
"#,
            name = name
        );
        fs::write(dir.join("src/main.py"), main_py)?;

        // __init__.py
        fs::write(dir.join("src/__init__.py"), "")?;

        // Test file
        let test_main = r#""""Tests for main module."""


def test_example():
    assert True
"#;
        fs::write(dir.join("tests/test_main.py"), test_main)?;

        // README
        let readme = format!(
            "# {}\n\nA Python project.\n\n## Setup\n\n```bash\nuv venv\nuv sync\n```\n\n## Run\n\n```bash\nuv run python src/main.py\n```\n",
            name
        );
        fs::write(dir.join("README.md"), readme)?;

        // .gitignore
        let gitignore = r#"__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
.env
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
"#;
        fs::write(dir.join(".gitignore"), gitignore)?;

        Ok(())
    }

    fn create_node_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
            println!("Creating Node.js project structure...");
        }

        // package.json
        let package_json = format!(
            r#"{{
  "name": "{name}",
  "version": "0.1.0",
  "description": "A Node.js project",
  "main": "src/index.js",
  "type": "module",
  "scripts": {{
    "start": "node src/index.js",
    "dev": "node --watch src/index.js",
    "test": "node --test tests/"
  }},
  "keywords": [],
  "author": "",
  "license": "MIT"
}}
"#,
            name = name
        );
        fs::write(dir.join("package.json"), package_json)?;

        // Create directories
        fs::create_dir_all(dir.join("src"))?;
        fs::create_dir_all(dir.join("tests"))?;

        // Main file
        let index_js = format!(
            r#"/**
 * {name} - Main entry point
 */

console.log("Hello from {name}!");
"#,
            name = name
        );
        fs::write(dir.join("src/index.js"), index_js)?;

        // Test file
        let test_js = r#"import { test } from 'node:test';
import assert from 'node:assert';

test('example test', () => {
  assert.strictEqual(1 + 1, 2);
});
"#;
        fs::write(dir.join("tests/index.test.js"), test_js)?;

        // README
        let readme = format!(
            "# {}\n\nA Node.js project.\n\n## Setup\n\n```bash\nbun install\n```\n\n## Run\n\n```bash\nbun run start\n```\n",
            name
        );
        fs::write(dir.join("README.md"), readme)?;

        // .gitignore
        let gitignore = "node_modules/\n.env\ndist/\n*.log\n";
        fs::write(dir.join(".gitignore"), gitignore)?;

        Ok(())
    }

    fn create_react_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
            println!("Creating React project with Vite...");
        }

        // package.json
        let package_json = format!(
            r#"{{
  "name": "{name}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.2"
  }}
}}
"#,
            name = name
        );
        fs::write(dir.join("package.json"), package_json)?;

        // Create directories
        fs::create_dir_all(dir.join("src"))?;
        fs::create_dir_all(dir.join("public"))?;

        // vite.config.js
        let vite_config = r#"import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
"#;
        fs::write(dir.join("vite.config.js"), vite_config)?;

        // index.html
        let index_html = format!(
            r#"<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"#,
            name = name
        );
        fs::write(dir.join("index.html"), index_html)?;

        // src/main.jsx
        let main_jsx = r#"import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"#;
        fs::write(dir.join("src/main.jsx"), main_jsx)?;

        // src/App.jsx
        let app_jsx = format!(
            r#"function App() {{
  return (
    <div>
      <h1>Welcome to {name}</h1>
      <p>Edit src/App.jsx to get started.</p>
    </div>
  )
}}

export default App
"#,
            name = name
        );
        fs::write(dir.join("src/App.jsx"), app_jsx)?;

        // src/index.css
        let index_css = r#"* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.6;
  padding: 2rem;
}

h1 {
  margin-bottom: 1rem;
}
"#;
        fs::write(dir.join("src/index.css"), index_css)?;

        // README
        let readme = format!(
            "# {}\n\nA React project built with Vite.\n\n## Setup\n\n```bash\nbun install\n```\n\n## Development\n\n```bash\nbun run dev\n```\n\n## Build\n\n```bash\nbun run build\n```\n",
            name
        );
        fs::write(dir.join("README.md"), readme)?;

        // .gitignore
        let gitignore = "node_modules/\ndist/\n.env\n*.local\n";
        fs::write(dir.join(".gitignore"), gitignore)?;

        Ok(())
    }

    fn create_nextjs_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
            println!("Creating Next.js project...");
        }

        // package.json
        let package_json = format!(
            r#"{{
  "name": "{name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "next dev --turbopack",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }},
  "dependencies": {{
    "next": "15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  }},
  "devDependencies": {{
    "@types/node": "^20",
    "@types/react": "^19",
    "typescript": "^5"
  }}
}}
"#,
            name = name
        );
        fs::write(dir.join("package.json"), package_json)?;

        // Create directories
        fs::create_dir_all(dir.join("app"))?;
        fs::create_dir_all(dir.join("public"))?;

        // next.config.ts
        let next_config = r#"import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
"#;
        fs::write(dir.join("next.config.ts"), next_config)?;

        // tsconfig.json
        let tsconfig = r#"{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"#;
        fs::write(dir.join("tsconfig.json"), tsconfig)?;

        // app/layout.tsx
        let layout = format!(
            r#"export const metadata = {{
  title: '{name}',
  description: 'A Next.js application',
}}

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode
}}) {{
  return (
    <html lang="en">
      <body>{{children}}</body>
    </html>
  )
}}
"#,
            name = name
        );
        fs::write(dir.join("app/layout.tsx"), layout)?;

        // app/page.tsx
        let page = format!(
            r#"export default function Home() {{
  return (
    <main style={{ padding: '2rem' }}>
      <h1>Welcome to {name}</h1>
      <p>Edit app/page.tsx to get started.</p>
    </main>
  )
}}
"#,
            name = name
        );
        fs::write(dir.join("app/page.tsx"), page)?;

        // README
        let readme = format!(
            "# {}\n\nA Next.js project.\n\n## Setup\n\n```bash\nbun install\n```\n\n## Development\n\n```bash\nbun run dev\n```\n\n## Build\n\n```bash\nbun run build\n```\n",
            name
        );
        fs::write(dir.join("README.md"), readme)?;

        // .gitignore
        let gitignore = "node_modules/\n.next/\nout/\n.env*.local\n";
        fs::write(dir.join(".gitignore"), gitignore)?;

        Ok(())
    }

    fn create_fastapi_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
            println!("Creating FastAPI project...");
        }

        // Create directories
        fs::create_dir_all(dir.join("app"))?;
        fs::create_dir_all(dir.join("tests"))?;

        // pyproject.toml
        let pyproject = format!(
            r#"[project]
name = "{name}"
version = "0.1.0"
description = "A FastAPI backend"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
    "ruff>=0.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"#,
            name = name
        );
        fs::write(dir.join("pyproject.toml"), pyproject)?;

        // app/main.py
        let main_py = format!(
            r#"from fastapi import FastAPI

app = FastAPI(title="{name}", version="0.1.0")


@app.get("/")
async def root():
    return {{"message": "Hello from {name}!"}}


@app.get("/health")
async def health():
    return {{"status": "healthy"}}
"#,
            name = name
        );
        fs::write(dir.join("app/main.py"), main_py)?;

        // app/__init__.py
        fs::write(dir.join("app/__init__.py"), "")?;

        // tests/test_main.py
        let test_main = r#"from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
"#;
        fs::write(dir.join("tests/test_main.py"), test_main)?;

        // README
        let readme = format!(
            "# {}\n\nA FastAPI backend.\n\n## Setup\n\n```bash\nuv venv\nuv sync\n```\n\n## Run\n\n```bash\nuv run uvicorn app.main:app --reload\n```\n\n## Test\n\n```bash\nuv run pytest\n```\n",
            name
        );
        fs::write(dir.join("README.md"), readme)?;

        // .gitignore
        let gitignore = r#"__pycache__/
*.py[cod]
.venv/
venv/
.env
*.egg-info/
"#;
        fs::write(dir.join(".gitignore"), gitignore)?;

        Ok(())
    }

    fn create_express_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
            println!("Creating Express.js project...");
        }

        // package.json
        let package_json = format!(
            r#"{{
  "name": "{name}",
  "version": "0.1.0",
  "description": "An Express.js backend",
  "main": "src/index.js",
  "type": "module",
  "scripts": {{
    "start": "node src/index.js",
    "dev": "node --watch src/index.js",
    "test": "node --test tests/"
  }},
  "dependencies": {{
    "express": "^4.21.0"
  }},
  "devDependencies": {{}}
}}
"#,
            name = name
        );
        fs::write(dir.join("package.json"), package_json)?;

        // Create directories
        fs::create_dir_all(dir.join("src"))?;
        fs::create_dir_all(dir.join("tests"))?;

        // src/index.js
        let index_js = format!(
            r#"import express from 'express';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {{
  res.json({{ message: 'Hello from {name}!' }});
}});

app.get('/health', (req, res) => {{
  res.json({{ status: 'healthy' }});
}});

app.listen(PORT, () => {{
  console.log(`Server running on http://localhost:${{PORT}}`);
}});
"#,
            name = name
        );
        fs::write(dir.join("src/index.js"), index_js)?;

        // README
        let readme = format!(
            "# {}\n\nAn Express.js backend.\n\n## Setup\n\n```bash\nbun install\n```\n\n## Run\n\n```bash\nbun run dev\n```\n",
            name
        );
        fs::write(dir.join("README.md"), readme)?;

        // .gitignore
        let gitignore = "node_modules/\n.env\n";
        fs::write(dir.join(".gitignore"), gitignore)?;

        Ok(())
    }

    fn create_docker_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
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

    fn create_db_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
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

    fn create_rust_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
            println!("Creating Rust project...");
        }

        // Use cargo init
        let output = Command::new("cargo")
            .args(["init", "--name", &name])
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

    fn create_go_project(&self, dir: &Path, name: &str) -> Result<()> {
        if self.verbose {
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
            // Try bun first, then npm
            let bun_result = Command::new("bun")
                .args(["install"])
                .current_dir(dir)
                .status();

            if bun_result.is_err() || !bun_result.unwrap().success() {
                Command::new("npm")
                    .args(["install"])
                    .current_dir(dir)
                    .status()
                    .context("Failed to install npm dependencies")?;
            }
        } else if dir.join("pyproject.toml").exists() {
            // Try uv first, then pip
            let uv_result = Command::new("uv")
                .args(["sync"])
                .current_dir(dir)
                .status();

            if uv_result.is_err() || !uv_result.unwrap().success() {
                Command::new("pip")
                    .args(["install", "-e", "."])
                    .current_dir(dir)
                    .status()
                    .context("Failed to install pip dependencies")?;
            }
        } else if dir.join("Cargo.toml").exists() {
            Command::new("cargo")
                .args(["build"])
                .current_dir(dir)
                .status()
                .context("Failed to build Cargo project")?;
        } else if dir.join("go.mod").exists() {
            Command::new("go")
                .args(["mod", "tidy"])
                .current_dir(dir)
                .status()
                .context("Failed to run go mod tidy")?;
        }

        Ok(())
    }
}

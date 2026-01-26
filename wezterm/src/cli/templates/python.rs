//! CX Terminal: Python project templates
//!
//! Templates for Python and FastAPI projects.

use anyhow::Result;
use std::fs;
use std::path::Path;

/// Create a Python project with uv/pip
pub fn create_python_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
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

/// Create a FastAPI backend project
pub fn create_fastapi_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
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

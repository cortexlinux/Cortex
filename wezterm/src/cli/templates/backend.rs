//! CX Terminal: Backend project templates
//!
//! Templates for Node.js and Express.js projects.

use anyhow::Result;
use std::fs;
use std::path::Path;

/// Create a Node.js project
pub fn create_node_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
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

/// Create an Express.js backend project
pub fn create_express_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
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

//! CX Terminal: Frontend project templates
//!
//! Templates for React and Next.js projects.

use anyhow::Result;
use std::fs;
use std::path::Path;

/// Create a React project with Vite
pub fn create_react_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
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

/// Create a Next.js project
pub fn create_nextjs_project(dir: &Path, name: &str, verbose: bool) -> Result<()> {
    if verbose {
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

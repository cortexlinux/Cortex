# CX Linux Ecosystem Architecture

## Overview

CX Linux is built as a modular system with clear boundaries between components. This document explains how all the pieces fit together.

## Why Modular?

| Benefit | Explanation |
|---------|-------------|
| **Independent releases** | Can update CLI without rebuilding terminal |
| **Language-appropriate** | Rust for performance, Python for flexibility |
| **Smaller codebases** | Easier to understand, test, and contribute |
| **Clear ownership** | Teams can work independently |
| **Selective installation** | Users install only what they need |

## Component Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CX Linux Distribution                             │
│                          (cx-distro)                                    │
│                   ISO builder, base system, branding                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  USER-FACING APPLICATIONS                                               │
│  ════════════════════════                                               │
│                                                                         │
│  ┌─────────────────────┐     ┌─────────────────────┐                   │
│  │    CX Terminal      │     │      CX CLI         │                   │
│  │       (Rust)        │     │     (Python)        │                   │
│  │                     │     │                     │                   │
│  │  GUI terminal app   │     │  Shell replacement  │                   │
│  │  with AI features   │     │  Natural language   │                   │
│  │                     │     │  to commands        │                   │
│  │  cx-terminal-gui    │     │  cx, cx-shell       │                   │
│  └──────────┬──────────┘     └──────────┬──────────┘                   │
│             │                           │                               │
│             │         ┌─────────────────┤                               │
│             │         │                 │                               │
│  ───────────┼─────────┼─────────────────┼───────────────────────────── │
│             │         │                 │                               │
│  SYSTEM SERVICES      │                 │                               │
│  ═══════════════      │                 │                               │
│             │         │                 │                               │
│  ┌──────────┴─────────┴──┐   ┌─────────┴───────────┐                   │
│  │       CX Ops          │   │     CX Stacks       │                   │
│  │      (Python)         │   │      (Python)       │                   │
│  │                       │   │                     │                   │
│  │  System diagnostics   │   │  Application stacks │                   │
│  │  Auto-repair          │   │  LAMP, Docker, etc  │                   │
│  │  Doctor mode          │   │  One-click deploy   │                   │
│  │  Plugin system        │   │                     │                   │
│  └───────────────────────┘   └─────────────────────┘                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Repository Details

### cx (Terminal) - Rust
**GitHub:** `cxlinux-ai/cx`

The GUI terminal emulator. Forked from WezTerm with AI extensions.

```
Primary binary: cx-terminal-gui
Quick CLI:      cx fix, cx ask, cx explain
```

**Features:**
- GPU-accelerated terminal rendering
- AI panel (sidebar) for chat and suggestions
- Command blocks with context
- Error capture for `cx fix`
- Voice input support

**When to use:** You want a modern terminal with AI assistance built-in.

---

### cx-cli - Python
**GitHub:** `cxlinux-ai/cx-cli`

Natural language shell that translates English to Linux commands.

```
Primary binary: cx (Python entry point)
Shell mode:     cx-shell (interactive)
```

**Features:**
- "setup lamp stack" → actual apt commands
- Prompt-to-plan pipeline with user confirmation
- Firejail sandboxing for untrusted commands
- Hardware detection and optimization

**When to use:** You want to describe what you want in plain English.

---

### cx-ops - Python
**GitHub:** `cxlinux-ai/cx-ops`

System diagnostics, monitoring, and auto-repair daemon.

```
Primary binary: cx-ops
Commands:       cx doctor, cx diagnose, cx repair
```

**Features:**
- System health checks
- Automatic problem detection
- Suggested fixes with one-click apply
- Plugin system for custom checks
- Rollback capabilities

**When to use:** Something's wrong and you want AI-assisted diagnosis.

---

### cx-stacks - Python
**GitHub:** `cxlinux-ai/cx-stacks`

One-click application stack deployment.

```
Commands: cx stack lamp, cx stack docker, cx stack node
```

**Supported Stacks:**
- LAMP (Apache, MySQL, PHP)
- LEMP (Nginx, MySQL, PHP)
- Node.js with PM2
- Django with PostgreSQL
- Docker Compose templates
- SSL automation with Certbot

**When to use:** You want a complete application stack without manual setup.

---

### cx-distro - Shell
**GitHub:** `cxlinux-ai/cx-distro`

ISO builder for the CX Linux distribution.

**Purpose:**
- Builds installable ISO images
- Packages all CX components
- Configures default settings
- Handles branding and theming

**When to use:** You're building a CX Linux release.

---

## Quick CLI vs Full CLI - Clarification

There are **two** ways to interact with CX via command line:

### 1. Quick CLI (Rust, in terminal)
```bash
cx fix              # Fix the last error you saw
cx ask "question"   # Quick AI query
cx explain <thing>  # Explain a command or concept
```

**Characteristics:**
- Fast (native Rust)
- Context-aware (knows what's in your terminal)
- Lightweight (no Python runtime)
- Best for: Quick interactions while working

### 2. Full CLI (Python, cx-cli)
```bash
cx setup lamp stack with php 8.3
cx install nginx and configure for reverse proxy
cx what packages use the most disk space
```

**Characteristics:**
- Full natural language understanding
- Shows plan before execution
- Firejail sandboxing
- Best for: Complex tasks described in plain English

**They complement each other:**
- Use Quick CLI for fast fixes and questions
- Use Full CLI for natural language system administration

## Communication & Integration

### How Components Talk

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Terminal   │─────▶│   cx-cli    │─────▶│  cx-stacks  │
│   (Rust)    │ exec │  (Python)   │ import│  (Python)   │
└─────────────┘      └─────────────┘      └─────────────┘
       │                    │
       │                    │
       ▼                    ▼
┌─────────────────────────────────────┐
│           ~/.cx/daemon.sock         │
│              (Unix Socket)          │
└─────────────────────────────────────┘
                    │
                    ▼
            ┌─────────────┐
            │   cx-ops    │
            │  (Daemon)   │
            └─────────────┘
```

### Shared Resources

```
~/.cx/
├── config.yaml          # Shared configuration
├── last_error           # Error capture (terminal → cx fix)
├── history/             # Command history
├── learning/            # User model (privacy-preserving)
├── cache/               # Shared cache
└── daemon.sock          # IPC socket

/etc/cx/
├── system.yaml          # System-wide config
└── plugins/             # cx-ops plugins

/var/log/cx/
├── terminal.log
├── cli.log
└── ops.log
```

## Installation Scenarios

### Full CX Linux Install (from ISO)
Everything pre-installed and configured.

### Existing Ubuntu/Debian
```bash
# Core (natural language CLI)
curl -fsSL https://cxlinux.com/install | bash

# Optional: Terminal
sudo apt install cx-terminal

# Optional: Operations toolkit
pip install cx-ops

# Optional: Application stacks
pip install cx-stacks
```

### Minimal Install
```bash
pip install cx-cli  # Just the natural language CLI
```

## Design Decisions

### Why Rust for Terminal?
- Performance: 60fps rendering, low latency
- Memory safety: No crashes from buffer overflows
- WezTerm: Excellent foundation to build on

### Why Python for CLI/Ops/Stacks?
- Rapid iteration: NL patterns change frequently
- Library ecosystem: Rich AI/ML libraries
- Scripting: Easy to extend and customize
- Cross-platform: Same code on all Linux distros

### Why Not Merge Everything?
- Different release cycles (terminal is stable, CLI patterns evolve)
- Different expertise (graphics vs scripting)
- Different testing needs (UI vs command execution)
- User choice (install what you need)

## Future Considerations

### Potential Consolidation
If usage patterns show users always want everything, consider:
- Single installer that pulls all components
- Unified configuration system
- Shared daemon for all services

### Potential Expansion
- `cx-cloud`: Multi-server orchestration
- `cx-containers`: Docker/Kubernetes management
- `cx-dev`: Development environment setup

## Contributing

Each repository has specific guidelines. General principles:

1. **Terminal (Rust)**: Follow WezTerm patterns, add `// CX Terminal:` comments
2. **CLI (Python)**: PEP 8 style, type hints, pytest
3. **Ops (Python)**: Plugin architecture, rollback safety
4. **Stacks (Python)**: Idempotent scripts, clear success/failure
5. **Distro (Shell)**: POSIX-compatible, tested on Ubuntu/Debian

## Summary

| Component | Language | Binary | Purpose |
|-----------|----------|--------|---------|
| cx | Rust | cx-terminal-gui | GUI terminal with AI |
| cx-cli | Python | cx | Natural language → commands |
| cx-ops | Python | cx-ops | Diagnostics and repair |
| cx-stacks | Python | cx stack | Application deployment |
| cx-distro | Shell | - | ISO builder |

The modular approach enables:
- Independent development and releases
- Language-appropriate implementations
- User choice in what to install
- Clear boundaries and responsibilities

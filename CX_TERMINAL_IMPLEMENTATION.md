# CX Terminal — Implementation Guide

**Version:** 1.0
**Created:** January 2026
**Owner:** Development Team
**Status:** Active Implementation

---

## Overview

This document outlines the concrete implementation tasks to transform the WezTerm fork into a fully-branded, production-ready CX Terminal. Based on Mike's roadmap and the current codebase state.

---

## Current State Assessment

### What's Working
| Component | Status | Location |
|-----------|--------|----------|
| AI Panel (Claude/Ollama) | ✅ Implemented | `wezterm-gui/src/ai/` |
| Voice Capture | ✅ Implemented | `wezterm-gui/src/voice/` |
| Command Blocks | ✅ Implemented | `wezterm-gui/src/blocks/` |
| Agents (file, git, docker, system, package) | ✅ Implemented | `wezterm-gui/src/agents/` |
| Learning/ML | ✅ Implemented | `wezterm-gui/src/learning/` |
| Subscription/Stripe | ✅ Implemented | `wezterm-gui/src/subscription/` |
| Daemon IPC | ✅ Implemented | `wezterm-gui/src/cx_daemon/` |
| Platform-aware fonts | ✅ Fixed | `config/src/font.rs` |

### Known Issues
| Issue | Severity | Notes |
|-------|----------|-------|
| Two terminals appearing on launch | HIGH | Reported by zeno |
| WezTerm branding still present | MEDIUM | Icons, about screen, etc. |
| No embedded default config | MEDIUM | Relies on `~/.wezterm.lua` |
| No DMG installer | MEDIUM | Manual build required |

---

## Phase 1: Branding & Identity (Priority: CRITICAL)

### 1.1 Replace App Icon

**Current:** WezTerm "$W" logo
**Target:** CX Linux glyph

**Files to modify:**
```
assets/icon/                    # Create this directory
├── cx-icon.icns               # macOS (1024x1024)
├── cx-icon.ico                # Windows
├── cx-icon.png                # Linux (512x512)
└── cx-icon-16.png             # Small variants
    cx-icon-32.png
    cx-icon-64.png
    cx-icon-128.png
    cx-icon-256.png
```

**Code changes:**
```rust
// wezterm-gui/src/main.rs or window creation
// Replace icon loading path
```

**macOS Info.plist:**
```
assets/macos/
└── Info.plist                 # CFBundleIconFile = "cx-icon"
```

### 1.2 Replace Window Title & About Screen

**Search and replace in codebase:**
| Find | Replace |
|------|---------|
| `WezTerm` | `CX Terminal` |
| `wezterm` | `cx-terminal` |
| `Wez Furlong` | `CX Linux (based on WezTerm by Wez Furlong)` |
| `wezfurlong.org/wezterm` | `cxlinux.ai` |

**Files likely affected:**
- `wezterm-gui/src/termwindow/mod.rs` (window title)
- `wezterm-gui/src/about.rs` (about dialog)
- `Cargo.toml` files (package names already changed)
- `README.md`

### 1.3 Embed Default Configuration

**Goal:** Terminal boots with CX branding even without config file

**Implementation approach:**

```rust
// config/src/lib.rs or similar

pub fn default_cx_config() -> Config {
    Config {
        // CX Brand Colors
        color_scheme: "CX Dark".to_string(),

        // Window chrome
        window_decorations: "INTEGRATED_BUTTONS|RESIZE",
        integrated_title_buttons: vec!["Hide", "Maximize", "Close"],

        // Status bar with AI trigger zone
        enable_tab_bar: true,
        tab_bar_at_bottom: false,

        // Font fallback (already fixed)
        // Menlo -> Fira Code -> JetBrains Mono -> monospace

        // AI keybinding
        keys: vec![
            KeyBinding {
                key: "Space",
                mods: "CTRL",
                action: "ToggleAIPanel",
            }
        ],

        ..Default::default()
    }
}
```

**Create embedded color scheme:**
```lua
-- To be compiled into binary
-- config/src/cx_colors.rs

pub const CX_DARK_SCHEME: &str = r#"
[colors]
background = "#1a1b26"
foreground = "#c0caf5"
cursor_bg = "#00d4aa"
cursor_fg = "#1a1b26"
selection_bg = "#33467c"
selection_fg = "#c0caf5"

[colors.ansi]
black = "#15161e"
red = "#f7768e"
green = "#00d4aa"
yellow = "#e0af68"
blue = "#7aa2f7"
magenta = "#bb9af7"
cyan = "#7dcfff"
white = "#a9b1d6"
"#;
```

---

## Phase 2: Fix Known Issues

### 2.1 Two Terminals on Launch

**Investigation needed:**
```bash
# Check for multiple process spawning
ps aux | grep cx-terminal

# Check launch configuration
# Likely in wezterm-gui/src/main.rs
```

**Possible causes:**
1. Multiplexer spawning extra instance
2. macOS app bundle misconfiguration
3. Socket/IPC reconnection logic

### 2.2 Config File Independence

**Current behavior:** Errors if `~/.wezterm.lua` missing
**Target behavior:** Works with zero config, loads user config if present

```rust
// Pseudocode for config loading
fn load_configuration() -> Config {
    let user_config = try_load_user_config();

    match user_config {
        Ok(config) => merge_with_defaults(config),
        Err(_) => {
            log::info!("No user config found, using CX defaults");
            default_cx_config()
        }
    }
}
```

---

## Phase 3: macOS Packaging

### 3.1 Universal Binary

```bash
#!/bin/bash
# scripts/build-universal.sh

# Build for Apple Silicon
cargo build --release --target aarch64-apple-darwin

# Build for Intel
cargo build --release --target x86_64-apple-darwin

# Create universal binary
lipo -create \
    target/aarch64-apple-darwin/release/cx-terminal-gui \
    target/x86_64-apple-darwin/release/cx-terminal-gui \
    -output target/universal/cx-terminal-gui
```

### 3.2 App Bundle Structure

```
CX Terminal.app/
├── Contents/
│   ├── Info.plist
│   ├── MacOS/
│   │   └── cx-terminal-gui
│   ├── Resources/
│   │   ├── cx-icon.icns
│   │   ├── cx-defaults.lua
│   │   └── fonts/
│   │       ├── FiraCode-Regular.ttf
│   │       └── JetBrainsMono-Regular.ttf
│   └── Frameworks/
```

### 3.3 DMG Creation

```bash
#!/bin/bash
# scripts/create-dmg.sh

create-dmg \
    --volname "CX Terminal" \
    --volicon "assets/icon/cx-icon.icns" \
    --background "assets/dmg-background.png" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "CX Terminal.app" 150 200 \
    --app-drop-link 450 200 \
    "CX-Terminal-1.0.dmg" \
    "build/CX Terminal.app"
```

### 3.4 Code Signing & Notarization

```bash
#!/bin/bash
# scripts/notarize.sh

# Sign the app
codesign --force --deep --sign "Developer ID Application: AI Venture Holdings LLC" \
    "build/CX Terminal.app"

# Notarize with Apple
xcrun notarytool submit "CX-Terminal-1.0.dmg" \
    --apple-id "$APPLE_ID" \
    --team-id "$TEAM_ID" \
    --password "$APP_PASSWORD" \
    --wait

# Staple the notarization
xcrun stapler staple "CX-Terminal-1.0.dmg"
```

---

## Phase 4: AI Side Panel Enhancements

### 4.1 Current Implementation

Located in `wezterm-gui/src/ai/`:
- `panel.rs` - Panel UI
- `widget.rs` - AI widget rendering
- `claude.rs` - Claude API integration
- `ollama.rs` - Local LLM integration

### 4.2 Planned Enhancements

**Live Telemetry Dashboard (Ctrl+Space):**
```rust
// wezterm-gui/src/ai/telemetry.rs

pub struct TelemetryPanel {
    cpu_usage: f32,
    ram_usage: f32,
    git_branch: Option<String>,
    git_dirty: bool,
    last_exit_code: i32,
    running_processes: Vec<ProcessInfo>,
}

impl TelemetryPanel {
    pub fn render(&self, ctx: &mut RenderContext) {
        // CPU/RAM meters
        // Git status
        // Process list
        // "Fix with AI" button if last_exit_code != 0
    }
}
```

**Error Detection & AI Suggestions:**
```rust
// wezterm-gui/src/ai/error_handler.rs

pub fn on_command_exit(exit_code: i32, stderr: &str) {
    if exit_code != 0 {
        let suggestion = analyze_error(stderr);
        show_fix_suggestion(suggestion);
    }
}

fn analyze_error(stderr: &str) -> AISuggestion {
    // Pattern match common errors
    // Rust build errors
    // npm/yarn errors
    // Python tracebacks
    // Git conflicts
}
```

---

## Phase 5: Testing Checklist

### Build Verification
- [ ] `cargo build --release` completes without errors
- [ ] `cargo test` all tests pass
- [ ] Binary runs without config file
- [ ] Binary runs with custom config file

### Branding Verification
- [ ] App icon shows CX logo in Dock
- [ ] Window title shows "CX Terminal"
- [ ] About dialog shows CX branding with WezTerm attribution
- [ ] No "WezTerm" text visible in UI

### Functionality Verification
- [ ] AI Panel opens with Ctrl+Space
- [ ] Voice capture works (audio doesn't hang UI)
- [ ] Claude API integration works
- [ ] Ollama fallback works
- [ ] Command blocks render correctly
- [ ] Session persistence works across restarts

### Platform Verification
- [ ] Works on Apple Silicon Mac
- [ ] Works on Intel Mac
- [ ] Works on Ubuntu 24.04

---

## File Reference

### Key Directories
| Path | Purpose |
|------|---------|
| `wezterm-gui/src/ai/` | AI panel, providers, streaming |
| `wezterm-gui/src/agents/` | File, system, docker, git, package agents |
| `wezterm-gui/src/blocks/` | Command blocks system |
| `wezterm-gui/src/voice/` | Audio capture, transcription |
| `wezterm-gui/src/learning/` | ML models, privacy filters |
| `wezterm-gui/src/subscription/` | Stripe, licensing, tiers |
| `wezterm-gui/src/cx_daemon/` | Daemon IPC client |
| `config/src/` | Configuration, Lua bindings |
| `assets/` | Icons, images (to be created) |
| `scripts/` | Build, package, sign scripts (to be created) |

### Configuration Paths
| Platform | User Config | Data Directory |
|----------|-------------|----------------|
| macOS | `~/.cx.lua` or `~/.config/cx/cx.lua` | `~/.config/cx-terminal/` |
| Linux | `~/.config/cx/cx.lua` | `~/.config/cx-terminal/` |
| Windows | `%APPDATA%\cx\cx.lua` | `%APPDATA%\cx-terminal\` |

---

## Timeline Estimate

| Phase | Tasks | Estimate |
|-------|-------|----------|
| Phase 1 | Branding (icons, text, colors) | 2-3 days |
| Phase 2 | Bug fixes (two terminals, config) | 1-2 days |
| Phase 3 | macOS packaging | 2-3 days |
| Phase 4 | AI enhancements | 1-2 weeks |
| Phase 5 | Testing & polish | 2-3 days |

**Total:** ~2-3 weeks for production-ready macOS release

---

## Notes

- Keep WezTerm attribution in About dialog and README (MIT license requirement)
- Test on both Intel and Apple Silicon before release
- Consider TestSprite for automated testing as Mike mentioned
- Coordinate with Mike on Apple Developer account for code signing

---

**Document Classification:** Internal Development
**Review Cycle:** Weekly during active implementation

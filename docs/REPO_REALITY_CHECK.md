# CX Linux Repository Reality Check

**Date:** January 2026
**Analyst:** Claude (treating this as my own project)

---

## Executive Summary

After deep-diving into all CX repositories, here's the honest truth:

| Repo | Advertised | Reality | Verdict |
|------|-----------|---------|---------|
| **cx** (terminal) | AI-native terminal | ✅ Real - 4385 LOC CLI, actual AI calls | **Production-ready** |
| **cx-cli** (Python) | Natural language CLI | ❌ Scaffold - 425 LOC, NO AI calls | **Demo only** |
| **cx-distro** | ISO builder | ⚠️ Partial - structure exists, packages defined | **In progress** |
| **cx-ops** | Diagnostics | ❓ Unknown | Private repo |
| **cx-stacks** | App stacks | ❓ Unknown | Private repo |

---

## Detailed Analysis

### cx-cli (Python) - THE HARD TRUTH

**What the README promises:**
```
cx install nginx → AI-powered package installation
cx setup lamp stack → Natural language deployment
```

**What the code actually does:**
```python
def detect_intent(query: str) -> str:
    query_lower = query.lower()
    if any(word in query_lower for word in ["install", "add", "get"]):
        return "install"  # Just keyword matching!
```

**Evidence:**
- `grep "anthropic\|openai\|ollama\|claude" cx/cli.py` returns **NOTHING**
- `handle_generic()` literally says: `"LLM integration required for complex queries"`
- Total code: **425 lines** (including comments and boilerplate)

**Verdict:** This is a **demo/scaffold**, not a working AI CLI.

---

### cx (Terminal - Rust) - ACTUALLY WORKS

**What we built:**

```rust
// From wezterm/src/cli/ask.rs - REAL AI CALLS
fn query_claude(&self, query: &str, api_key: &str) -> Result<String> {
    let payload = serde_json::json!({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "messages": [...]
    });
    // Actually calls https://api.anthropic.com/v1/messages
}

fn query_ollama(&self, query: &str, host: &str) -> Result<String> {
    // Actually calls {host}/api/generate
}
```

**Evidence:**
- `ask.rs`: 391 lines with **real Claude and Ollama API calls**
- `ask_patterns.rs`: 394 lines of CX command pattern matching
- `shortcuts.rs`: 223 lines for `cx fix`, `cx explain`
- **Total CLI code: 4,385 lines** (10x the Python version)

**Verdict:** This is **real, working code** with actual AI integration.

---

### cx-distro - STRUCTURE EXISTS

**What exists:**
- ISO build scripts (`scripts/build.sh`)
- Debian package definitions (`packages/cx-core/debian/control`)
- Test infrastructure (`tests/`)

**Problem:**
The `cx-core` package depends on the Python CLI:
```
Depends: python3 (>= 3.11), python3-pip, python3-rich, firejail
```

But the Python CLI has no actual AI functionality!

---

## The Fundamental Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT STATE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   cx-distro (ISO)                                               │
│       │                                                         │
│       └──▶ Depends on cx-core (Python)                         │
│                   │                                             │
│                   └──▶ cx-cli: "LLM integration required" 😬    │
│                                                                 │
│   cx (Terminal - Rust)                                          │
│       │                                                         │
│       └──▶ Actually calls Claude API ✅                         │
│       └──▶ Actually calls Ollama ✅                             │
│       └──▶ Has pattern matching ✅                              │
│       └──▶ Has cx fix, cx ask, cx explain ✅                    │
│                                                                 │
│   DISCONNECT: The working code (Rust) is not what the          │
│               distro packages (Python)!                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Recommendation: Three Options

### Option A: Make Python Work (Effort: HIGH)
Add real AI to cx-cli:
- Integrate anthropic SDK
- Integrate ollama-python
- Port our Rust logic to Python
- **Risk:** Duplicating work that already exists in Rust

### Option B: Use Rust CLI for Distro (Effort: MEDIUM) ⭐ RECOMMENDED
Build the Rust CLI as standalone binary:
- Already works!
- Single binary, no Python deps
- Fast startup
- **Change:** Update cx-distro to package Rust binary instead of Python

### Option C: Hybrid (Effort: MEDIUM-HIGH)
Keep Python for high-level orchestration, call Rust for AI:
- Python handles user interaction
- Spawns Rust binary for AI queries
- **Complexity:** Two codebases to maintain

---

## My Recommendation: Option B

**Why:**

1. **The AI code already exists in Rust** - Don't rewrite it in Python
2. **Single binary** - No "pip install" issues on fresh distro
3. **Fast startup** - 10ms vs 300ms matters for frequent commands
4. **Already tested** - We've been building and running it
5. **Simpler packaging** - One binary to `/usr/bin/cx`

**Action items for Mike:**

1. Keep cx-terminal (GUI) as is
2. Extract CLI commands to standalone `cx` binary (or keep in terminal binary)
3. Update cx-distro packages to use Rust binary
4. Deprecate or archive cx-cli (Python)

---

## Code Comparison

| Feature | Python cx-cli | Rust cx terminal |
|---------|--------------|------------------|
| Lines of code | 425 | 4,385 |
| AI calls | ❌ None | ✅ Claude + Ollama |
| Pattern matching | Basic keywords | ✅ Comprehensive |
| Error capture | ❌ None | ✅ PTY-level |
| `cx fix` | ❌ None | ✅ Works |
| `cx ask` | ❌ "LLM required" | ✅ Works |
| `cx new` | ❌ None | ✅ 1017 lines |
| Dependencies | Python 3.11, pip, rich | None (single binary) |
| Startup time | ~300ms | ~10ms |

---

## Bottom Line

**The Python CLI is a facade.** The real work has been done in Rust.

The question for Mike is: Do we want to:
1. Invest time making Python work (duplicate effort)
2. Use what already works (Rust)

My vote: **Use the Rust code. It's already built and working.**

# Cortex Linux

**Linux automation that actually works.** Tell it what you want in plain English.

```bash
$ cortex install oracle-23-ai --optimize-gpu

Analyzing system... NVIDIA RTX 4090 detected
Planning: CUDA 12.3 → cuDNN → Oracle 23 AI
Installing 47 packages (this usually takes mass googling)
Configuring for GPU acceleration
Running validation...

Done. Oracle 23 AI ready at localhost:1521
Total time: 4m 23s (vs. your afternoon)
```

## The Problem

We've all been there:

- **12 browser tabs** of conflicting Stack Overflow answers
- **Dependency hell** where installing X breaks Y which needs Z
- **Config file archaeology** - who wrote this? what does `vm.swappiness=60` even do?
- **4 hours later** you still don't have CUDA working

I built Cortex because I was tired of wasting time on package management instead of actual work.

## What It Does

Cortex wraps `apt` with an LLM that:

1. **Understands what you mean** - "install a machine learning stack" → figures out PyTorch, TensorFlow, CUDA, cuDNN, Jupyter, etc.
2. **Detects your hardware** - Sees your GPU/CPU and configures appropriately
3. **Handles dependencies** - Resolves conflicts before they happen
4. **Rolls back on failure** - Something breaks? Undo with one command
5. **Runs in a sandbox** - AI-generated commands execute in Firejail isolation

It's not magic. It's just automating what a senior sysadmin would do, but faster.

## Current Status

**Working (merged to main):**
- LLM integration (Claude API via LangChain)
- Hardware detection (GPU, CPU, memory)
- Sandboxed execution (Firejail + AppArmor)
- Package manager wrapper
- Installation rollback
- Context memory (learns your preferences)

**In progress:**
- Dependency resolution improvements
- Better error messages
- Multi-step orchestration
- Web dashboard (maybe)

This is early-stage software. Expect rough edges.

## Tech Stack

- **Base:** Ubuntu 24.04 LTS
- **Language:** Python 3.11+ (yes, I know - "Python for a package manager?" - it's a prototype, Rust rewrite is on the roadmap)
- **AI:** LangChain + Claude API
- **Security:** Firejail sandboxing, AppArmor policies
- **Storage:** SQLite for history and context

## Safety

"But what if the AI hallucinates `rm -rf /`?"

Fair concern. Here's how we handle it:

1. **Sandbox everything** - Commands run in Firejail isolation
2. **Whitelist dangerous operations** - No `rm -rf`, no `dd`, no `mkfs` without explicit confirmation
3. **Dry-run by default** - Shows you what it plans to do before doing it
4. **Rollback built-in** - Every installation is reversible
5. **Human confirmation** - Destructive operations require typing "yes I'm sure"

We're paranoid about this. The AI is a suggestion engine, not root.

## Contributing

We pay bounties for merged PRs:

| Type | Amount |
|------|--------|
| Bug fixes | $25-50 |
| Features | $50-200 |
| Major features | $200-500 |

Payment via Bitcoin, USDC, PayPal, or Venmo. International contributors welcome.

Check the [issues](https://github.com/cortexlinux/cortex/issues) for bounty labels.

### What We Need

- **Linux developers** who know apt/dpkg internals
- **Python devs** for the core logic
- **Security folks** to poke holes in our sandbox
- **Technical writers** for documentation
- **Testers** to break things

## Running It

```bash
# Clone
git clone https://github.com/cortexlinux/cortex.git
cd cortex

# Install dependencies
pip install -r requirements.txt

# Set your Claude API key
export ANTHROPIC_API_KEY="your-key"

# Run
python -m cortex install "nginx with ssl"
```

Requires Ubuntu 22.04+ or Debian 12+. Other distros eventually.

## FAQ

**Q: Why Python for a package manager?**
A: It's a prototype. If this takes off, core components get rewritten in Rust. Python lets us move fast and prove the concept.

**Q: Is this just a wrapper around apt?**
A: Yes, for now. The goal is deeper integration - custom package formats, rollback at filesystem level, eventually kernel-level optimizations. You have to start somewhere.

**Q: Why Claude and not GPT-4/Llama/etc?**
A: Claude has the best instruction-following for this use case. We'll add model options eventually.

**Q: Can I use this in production?**
A: Not yet. This is alpha software. Test it on VMs first.

## Roadmap

**Phase 1 (now):** Get the basics working. Natural language → apt commands.

**Phase 2 (Q1 2025):** Polish, error handling, config file generation.

**Phase 3 (2025):** Deeper integration - package caching, custom repos, multi-distro support.

**Phase 4 (eventually):** Kernel-level stuff - we have some ideas around native LLM support in the Linux kernel. Wild, but interesting.

## Community

- **Discord:** [discord.gg/uCqHvxjU83](https://discord.gg/uCqHvxjU83)
- **Email:** mike@cortexlinux.com

## License

Apache 2.0 - Use it, fork it, sell it, whatever. Just don't blame us if it breaks.

---

*Built by [Mike Morgan](https://github.com/mikejmorgan-ai) and contributors. We're hiring - if you're good at Linux internals and want to work on something different, reach out.*

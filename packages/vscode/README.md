# Prep for VS Code

**Epistemic semantic code search, trace-aware context assembly, and structural reasoning for AI workflows.**

Prep is an epistemic context engine that traces your codebase to provide fast, verifiable retrieval for LLMs. It works with your existing AI workflows (Copilot, Cursor, Windsurf) via the Model Context Protocol (MCP) or directly within VS Code.

## Features

### 🔍 Semantic Search
Search your codebase using natural language. Prep finds relevant code chunks based on meaning, not just keywords.
- **Sovereign Context**: Your index architecture never leaks.
- **Fast**: Epistemic routing happens instantly on your device.

### 🧠 Context Assembly
Assemble prompt-ready context for your LLM.
- **Bounded**: Automatically fits within your token budget.
- **Cited**: Every chunk includes file path and line numbers.
- **Copy-paste ready**: One click to copy formatted context for ChatGPT, Claude, or local LLMs.

### 🕸️ Trace Index (Pro)
Understand code structure with graph-based analysis.
- **Navigate**: explore callers, callees, and imports visually.
- **Deep context**: expand search results to include relevant dependencies.

### 🛡️ Privacy & Security
- **No Cloud Upload**: Indexes are stored locally on your disk.
- **BYOK**: Bring Your Own Key (or use local LLMs via Ollama).
- **Offline Capable**: Works without an internet connection.

## Getting Started

1. **Install the Extension**
   Install "Prep" from the VS Code Marketplace.

2. **Start the Daemon**
   The extension requires the Prep daemon. If you have the Prep desktop app installed, it includes the daemon. Otherwise, install the CLI:
   ```bash
   pip install prep
   # or
   brew install prep
   ```

3. **Add a Project**
   Open the Prep sidebar icon and click **Add Project** (or use `Prep: Add Project` from the command palette). Select your repository folder.

4. **Build Index**
   Click the "Build" icon or run `Prep: Build Index`. Prep will trace your code structurally.

5. **Search & Chat**
   Run `Prep: Search` to find code, or `Prep: Assemble Context` to prepare a prompt.

## License

- **Free Tier**: 3 active projects, all features included.
- **Pro Tier**: Unlimited projects.

[Upgrade to Pro](https://getprep.io/pricing) to unlock advanced features.

## Requirements

- **Prep Daemon**: Running on `localhost:8400` (default).
- **Ollama** (Optional): Required if you want to use local embedding models instead of the built-in ones.

## Feedback & Support

- [Documentation](https://docs.getprep.io)
- [Issue Tracker](https://github.com/magnetic-anomaly/prep/issues)
- [Discord Community](https://discord.gg/prep)

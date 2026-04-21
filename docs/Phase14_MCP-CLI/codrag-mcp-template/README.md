# Prep MCP (prep-mcp)

Prep provides a local-first MCP server for IDE integration.

Supported IDEs:
- Cursor
- Windsurf
- Claude Desktop
- VS Code
- JetBrains

## Installation

Install Prep (the engine) via your preferred method:

```bash
# macOS (Homebrew)
brew install --cask prep

# Windows (winget)
winget install MagneticAnomaly.Prep
```

## Quickstart (Direct Mode)

Direct mode runs fully locally and does not require a daemon.

```bash
# Run the MCP server (stdio)
prep mcp --mode direct
```

Generate IDE config:

```bash
# Cursor example
prep mcp-config --mode direct --ide cursor
```

## Security & Privacy

See:
- `SECURITY.md`
- `PRIVACY.md`
- `THREAT_MODEL.md`

## License

This repository is intended to be a public-facing MCP distribution surface.

The Prep engine and commercial features may be distributed as signed binaries under a separate commercial license.

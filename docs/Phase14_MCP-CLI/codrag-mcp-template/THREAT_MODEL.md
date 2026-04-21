# Threat Model

## Components

- IDE (Cursor/Windsurf/VS Code/etc)
- MCP server process (stdio transport)
- Prep engine (local process)
- Local filesystem (your repository)
- Optional local LLM endpoints (e.g. Ollama)

## Trust boundaries

- IDE prompts are untrusted input.
- Repository contents are untrusted input (malicious code/comments may attempt prompt injection).
- Local network endpoints are only as trustworthy as the software you run locally.

## Key risks

- Prompt injection via tool outputs or repository text
- Malicious repositories causing unexpected file access patterns
- Dependency / supply-chain compromise
- Running unsigned binaries

## Mitigations

- Keep the MCP tool surface minimal and explicit.
- Prefer local-only operation; document any outbound network behavior.
- Distribute signed releases and publish checksums/SBOM.
- Provide a clear data wipe/uninstall path.

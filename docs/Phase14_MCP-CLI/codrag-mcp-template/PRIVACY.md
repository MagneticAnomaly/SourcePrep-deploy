# Privacy

Prep is designed to be **local-first**.

## What Prep does with your code

- Prep reads files from your local filesystem to build a local index.
- Prep does **not** upload your repository contents to Prep-controlled servers.

## Data stored on disk

Prep stores rebuildable index artifacts locally (for example under `.runprep/index` within a repository in direct mode).

## Network access

Prep may connect to:
- local LLM/embedding endpoints you configure (for example Ollama at `http://localhost:11434`)

## Telemetry

- Prep must work with telemetry disabled.
- If telemetry exists, it must be opt-in and limited to aggregate counters (no file contents, no raw queries, no absolute paths).

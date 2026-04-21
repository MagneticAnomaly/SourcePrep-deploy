# Privacy

CoDRAG is designed to be **local-first**.

## What CoDRAG does with your code

- CoDRAG reads files from your local filesystem to build a local index.
- CoDRAG does **not** upload your repository contents to CoDRAG-controlled servers.

## Data stored on disk

CoDRAG stores rebuildable index artifacts locally (for example under `.prep/index` within a repository in direct mode).

## Network access

CoDRAG may connect to:
- local LLM/embedding endpoints you configure (for example Ollama at `http://localhost:11434`)

## Telemetry

- CoDRAG must work with telemetry disabled.
- If telemetry exists, it must be opt-in and limited to aggregate counters (no file contents, no raw queries, no absolute paths).

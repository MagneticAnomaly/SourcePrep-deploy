# Privacy Policy

**Effective Date:** February 2026

SourcePrep is built on a **Local-First** philosophy. We believe your code is your intellectual property and should not be uploaded to cloud servers for indexing or processing without your explicit consent.

## 1. Zero Code Upload Guarantee

**SourcePrep does NOT upload your source code to any SourcePrep-controlled servers.**

- **Indexing**: All indexing (parsing, symbol extraction, vector embedding) happens locally on your machine.
- **Storage**: Your code index and trace graph are stored locally on your disk (typically in `~/.local/share/sourceprep` or inside your project's `.prep` folder).
- **Search**: All search queries are processed locally against your local index.

## 2. Network Activity

SourcePrep makes network requests **only** in the following specific scenarios:

### License Verification
- On startup, SourcePrep verifies your license key against our licensing server (`api.sourceprep.io`).
- **Data transmitted**: License key, machine fingerprint (hardware ID).
- **Data NOT transmitted**: Code snippets, file names, project metadata.

### External LLM Providers (Optional)
- If you configure SourcePrep to use an external LLM provider (e.g., OpenAI, Anthropic) via "Bring Your Own Key" (BYOK), text chunks will be sent to that provider.
- **You** control this configuration. By default, SourcePrep uses local embeddings (Ollama) and performs no external inference.
- When using a cloud model, SourcePrep **batches multiple files into single API calls** to reduce latency and cost. This means a single request to your provider may contain excerpts from multiple files in your project. The data sent is identical to what would be sent in individual calls — batching changes only the grouping, not the content. See our [BYOK Batch Processing guide](https://docs.sourceprep.io/guides/byok-batching) for full details.

### Updates
- SourcePrep checks for application updates by querying our update server.

## 3. Telemetry

We collect minimal, anonymous usage data to improve the product.
- **Opt-Out**: Telemetry can be completely disabled in Settings.
- **Collected**: Crash reports, feature usage counts (e.g., "MCP connection started").
- **NOT Collected**: File contents, file paths, function names, search queries, specific code snippets.

## 4. Third-Party Data Processing

If you use optional integrations:
- **Ollama**: Local-only. No data leaves your machine.
- **Context Compression**: Built into the engine. No data leaves your machine.

For the full commercial privacy policy, please visit [sourceprep.io/privacy](https://sourceprep.io/privacy).

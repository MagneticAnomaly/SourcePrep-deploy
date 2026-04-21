# prep-mcp: Public GitHub Strategy (MCP Trust + Closed-Source Engine)

## Decision
We will ship Prep as a **closed-source commercial engine** with **strong attestations**.

The public-facing GitHub repository for MCP directories/lists will be named: **`prep-mcp`**.

We will use the **thin open shim + closed engine** model:
- `prep-mcp` (public): MIT-licensed wrapper + docs + security posture
- Prep engine (commercial): signed binaries + licensing

To earn trust in MCP directories/communities without exposing IP, we will maintain a **public-facing GitHub repository** that contains:
- **(Optionally open-source)** MCP integration “plumbing” (schemas, tool surface, config generator) that is *not* the core indexing/trace engine.
- **Documentation + security posture + verification artifacts** (signed releases, checksums, SBOM).

This is the “thin public shim + closed engine” model.

## Why this works (fork-risk reality)
Forking is only strategically dangerous if your **moat lives in the code you publish**.

We reduce fork risk by:
- **Keeping the engine closed** (index build/search/trace algorithms, performance work, multi-project registry logic, licensing).
- Publishing only **low-moat integration code** (MCP stdio transport, tool schema definitions, IDE config generation).
- Using **trademark + official distribution** as the practical “moat” around trust and adoption.

A fork can add “multi-repo” UX, but it still must implement a high-quality engine, ship stable binaries, and earn trust.

## Goals
- **Be listable** in MCP directories and “awesome MCP” lists with a credible GitHub presence.
- **Maximize user trust** for a tool that reads local code.
- **Minimize IP leakage** (avoid handing competitors the engine).
- **Keep onboarding friction low** (CLI + MCP should be copy/paste simple).

## Non-goals
- **No promise of open-source** for the engine.
- **No reliance on secrecy alone** as a moat.
- **No misleading licensing language** (we will not call source-available code “open source”).

---

## Public repo: minimum bar (what MUST exist)
The public GitHub repo should be “complete enough” that a security-conscious developer can evaluate risk and install safely.

### 1) Landing page
- **README.md**
  - **What it is**: “Local-first code search + MCP server.”
  - **What it does**: semantic search, context assembly, optional trace analysis.
  - **What runs where**: everything local; list any outbound connections (e.g. Ollama at `http://localhost:11434`).
  - **What data is stored**: location of index (e.g. `<repo_root>/.prep/index`).
  - **What never leaves the machine**: file contents, paths (state this precisely).
  - **Quickstart**: install + `prep mcp --mode direct` + IDE config examples.
  - **Tool surface**: list MCP tools (`prep_status`, `prep_build`, `prep_search`, `prep` (context), etc) with inputs/outputs.
  - **Compatibility**: MCP protocol version (currently `2025-11-25`) and supported clients.

### 2) Security posture
- **SECURITY.md**
  - **Disclosure channel** (email alias).
  - **Expected response times**.
  - **Supported versions**.
- **PRIVACY.md**
  - **Telemetry**: default off.
  - **If enabled**: only aggregate counters; no file contents, no raw queries, no absolute paths.
- **THREAT_MODEL.md**
  - **Trust boundaries**: IDE ↔ MCP process ↔ local filesystem.
  - **Network boundary**: Ollama/local LLM endpoints.
  - **Attack surface**: prompt injection via tool outputs, malicious repos, dependency risks.

### 3) Supply-chain trust
- **Releases** (GitHub Releases is fine)
  - **Signed artifacts** for macOS/Windows/Linux.
  - **SHA256 checksums**.
  - **SBOM** (CycloneDX or SPDX).
  - **Provenance** (SLSA-style attestation if feasible).

### 4) Operational maturity
- **CHANGELOG.md**
  - **User-visible changes**.
  - **Tool surface changes** (breaking vs non-breaking).
- **Issue templates** and **bug report guidance**.

---

## Public repo: what code (if any) should be public
This is optional. If we publish code, it should be “plumbing,” not “engine.”

### Recommended public components
- **MCP tool schema definitions** (the `tools` list and JSON schemas).
- **MCP config generator** (Cursor/Windsurf/Claude Desktop config output).
- **MCP stdio transport + request routing**.

### Components to keep closed
- **Index build/search implementation** (chunking, embeddings, storage, reranking).
- **Trace index / GraphRAG internals**.
- **Multi-project registry + multi-repo orchestration**.
- **License enforcement and any paid-tier gates**.

### Practical boundary rule
If a file answers “how we get good results” rather than “how we talk MCP,” it stays closed.

---

## Licensing stance (fork-risk trade-offs)
### Option A: No public code (docs-only)
- **Pros**: maximal IP protection.
- **Cons**: some MCP directories may decline listing.

### Option B: Public plumbing code under a permissive license (MIT/Apache-2.0)
- **Pros**: highest community acceptance.
- **Cons**: easiest to fork (but low risk if it is truly just plumbing).

### Option C: Public plumbing code under a copyleft license (AGPL-3.0)
- **Pros**: forks must publish modifications; discourages closed competitors.
- **Cons**: some companies avoid AGPL.

**Recommendation:** Start with **Option B** if (and only if) we keep the public code extremely thin.

---

## Distribution strategy (closed-source friendly)
### Primary
- **Signed standalone binaries** published as GitHub Releases.

### Optional wrappers (for “one-liner install”)
- **Homebrew tap** that installs the binary.
- **npm wrapper** (`npx` / `npm i -g`) that downloads the correct binary and runs it.

### Avoid (if we truly want to hide source)
- **Pure-Python `pip install`** for the main engine (it exposes source).

---

## What MCP directories need from us (submission checklist)
- **A stable GitHub URL**.
- **Clear install + run instructions**.
- **Tool list + example configs**.
- **Security posture docs**.
- **Versioned releases**.

---

## Messaging: how we talk about “closed source” without losing trust
- **Be explicit**:
  - “Prep is proprietary software. It runs locally. It does not upload your code.”
- **Make verification easy**:
  - “Verify downloads via signatures and checksums.”
  - “Review our threat model + privacy policy.”
- **Default to user control**:
  - Opt-in telemetry only.
  - Clear uninstall + data wipe instructions.

---

## Next steps
- **Stand up `prep-mcp`** as a standalone public GitHub repo (copy from the template folder).
- **Keep it thin**: wrapper + docs; no engine internals.
- **Implement release pipeline** (engine + wrapper): signed artifacts + checksums + SBOM.
- **Publish + submit**: first tagged release + directory submissions.

---

## Directory/listing targets (distribution)

The goal is to make `prep-mcp` discoverable anywhere developers browse MCP servers.

- **Official-ish / high-signal**
  - `modelcontextprotocol/servers` (GitHub)
- **Community directories**
  - `mcpservers.org`
  - `smithery.ai`
  - `cursor.directory`
- **Native marketplaces (optional)**
  - VS Code Marketplace (a minimal “bridge” extension that only helps users install/configure the MCP server)

Notes:
- Some directories care about “open source.” Most primarily care that the repo is public, install is clear, and there is a security posture.
- If a directory requires OSI open source for the *engine*, we skip it (do not compromise the moat).

---

## prep-mcp repo skeleton (concrete)

This is the minimum structure we should implement in the public `prep-mcp` repo.

### Option 1: docs-only + signed binary releases (max IP protection)

- `README.md`
- `SECURITY.md`
- `PRIVACY.md`
- `THREAT_MODEL.md`
- `CHANGELOG.md`
- `LICENSE` (commercial EULA or proprietary license text)
- GitHub Releases:
  - `prep` (macOS/Windows/Linux)
  - `checksums.txt`
  - `checksums.txt.sig`
  - `sbom.spdx.json` (or CycloneDX)

### Option 2: thin open shim + closed engine (recommended)

- Everything in Option 1, plus a small open-source wrapper (MIT/Apache-2.0):
  - `package.json`
  - `src/` (stdio plumbing + “run the engine”)
  - `dist/` (compiled JS)
  - `bin/` (download cache; usually gitignored)
  - `.github/workflows/release.yml`

Wrapper responsibilities:
- Download/install the signed Prep engine binary (or direct users to install via `brew`/`winget`).
- Launch `prep mcp --mode direct` (or server mode when explicitly requested).
- Provide a stable command name for IDE configs (e.g. `npx prep-mcp`).

---

## Viral distribution mechanics (high leverage, low spam)

- **Shareable artifacts**
  - Exportable “trace map” images from the GUI (opt-in sharing, watermark optional).
- **Copy/paste onboarding**
  - Make `prep mcp-config --mode direct --ide cursor` the default path in docs.
- **OSS goodwill without open-sourcing the engine**
  - Offer free licenses to maintainers (policy-driven, not manual favors).

Avoid:
- Automatically injecting marketing text into context/tool output. If we do attribution, it should be optional and user-controlled.

---

## Work started (in this repo)

- `prep mcp-config` supports `--mode auto|project|direct` and the expanded IDE list (`claude`, `cursor`, `windsurf`, `vscode`, `jetbrains`, `all`).
- `prep mcp` supports:
  - server mode (connects to daemon; supports pinned project via `--project` and auto-detect via `--auto`)
  - direct mode (`--mode direct`, no daemon)
- MCP protocol version is `2025-11-25` (implemented in `src/prep/mcp_server.py` and `src/prep/mcp_direct.py`).
- The MCP server (server mode) proxies to canonical `/projects/{project_id}/status|build|search|context` and correctly unwraps the daemon's `ApiEnvelope`.

Known gaps to resolve before calling this “done”:
- CLI daemon-backed commands in `src/prep/cli.py` call `/projects/*` but do not consistently unwrap `ApiEnvelope` yet.
- Some CLI “extras” (`activity`, `coverage`, `overview`) currently call legacy root endpoints (e.g. `/status`, `/activity`, `/coverage`, `/trace/stats`) that are not implemented on the daemon; these should be migrated to project-scoped endpoints or implemented as compatibility aliases.

Starter template for the public repo:
- `public/prep-mcp/`


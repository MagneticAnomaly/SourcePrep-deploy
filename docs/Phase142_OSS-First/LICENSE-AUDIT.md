# LICENSE-AUDIT — 2026-07-17 (PRIVATE)

> **Status:** PARTIAL — dependency-license inventory complete; full-source
> copy-paste / LLM-generated-match scan **NOT yet run** (tooling gap, see below).
> PRIVATE — Phase 143 keep-private bucket. Not a substitute for legal advice.

## Tooling status (vs audit item 7 / M4 spec)

| Prescribed tool | Available? | Substitute used |
|---|---|---|
| `scancode-toolkit` (source copy-paste + license text detection) | ❌ not installed | — (GAP — see "Open gap" below) |
| `licensee detect` (top-level license identification) | ❌ not installed | manual `git ls-files` license-field sweep |
| `pip-licenses` (Python dep licenses) | ✅ 5.5.5 | used |
| `license-checker` (npm dep licenses) | ✅ present | available (full monorepo run pending) |
| `cargo-deny` (Rust dep license gate) | ❌ not installed | manual `Cargo.toml` sweep |

**Open gap:** the highest-value part of M4 — scanning *source files* for
GPL/CC-BY-SA text that may have been vendored or LLM-generated into the repo —
requires `scancode-toolkit`, which is not installed. Dependency-manifest tools
(pip-licenses, license-checker, cargo-deny) only see declared package licenses;
they cannot catch copy-pasted or model-generated GPL code. **This scan remains a
hard pre-launch blocker and is not closed by this document.** Recommend
`pipx install scancode-toolkit` (heavy; ~1GB) then
`scancode -clpeu --json-pp out.json <repo>`.

## Runtime dependency licenses (declared)

### Python (top-level runtime, from `.venv` pip-licenses)
All permissive or weak-copyleft; **no GPL/AGPL/LGPL** in the runtime set
(corroborates Phase 144 blocker #1 = resolved).

| Package | License |
|---|---|
| networkx | BSD-3-Clause |
| numpy | BSD-3-Clause (+ bundled 0BSD/MIT/Zlib/CC0) |
| onnxruntime | MIT |
| tokenizers | Apache-2.0 |
| huggingface_hub | Apache-2.0 |
| watchdog | Apache-2.0 |
| **pathspec** | **MPL-2.0** ⚠ (file-level weak copyleft — OK as unmodified dep; flag) |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| fastapi / pydantic / pydantic-settings / typer / rich | MIT |
| httpx | BSD-3-Clause |
| requests | Apache-2.0 |
| uvicorn | BSD-3-Clause |

### Rust (declared in `engine/crates/*/Cargo.toml`)
- Workspace crates: MIT (`[workspace.package] license = "MIT"`; 6 crates inherit
  via `license.workspace = true`). **`prep-selfheal/Cargo.toml` has NO license
  field** — must be added (matches audit item 3).
- Notable deps: tree-sitter + grammars (tree-sitter-python/typescript/rust/go/
  java/javascript/c/cpp) — MIT; serde, rayon, pyo3 — MIT OR Apache-2.0;
  ignore/walkdir — MIT/Unlicense.

### npm / UI (`packages/ui` runtime)
React (MIT), @radix-ui/react-slot (MIT), **@tremor/react (Apache-2.0)**,
@xyflow/react (MIT), lucide-react (ISC), react-grid-layout (MIT),
react-syntax-highlighter (MIT), clsx (MIT), tailwind-merge (MIT).

## Model / data assets
- ONNX embedder **nomic-embed-text-v1.5** — Apache-2.0 (must appear in NOTICE).
- tree-sitter grammar binaries — MIT (per-grammar).

## `package.json` license-field hygiene (needs fixing before public mirror)
10 tracked `package.json` files declare **no `license` field**: root,
`packages/vscode/webview-ui`, `src/prep/dashboard`, `src/prep/mcp_local_rag`,
`websites/apps/{docs,marketing,payments,support}`, `websites/MagneticAnomaly`,
`docs/Phase13_Storybook/theme-examples/tremor-preview`. `packages/vscode`
declares `"SEE LICENSE IN LICENSE"` (points at the proprietary root). 4 declare
MIT (`packages/ui`, `packages/paperclip-plugin-prep`, `public/sourceprep-mcp`,
`docs/Phase14_MCP-CLI/codrag-mcp-template`). Reconcile all to the chosen outbound
license once decided (Apache vs AGPL — Eric's open question #4).

## License-compatibility conclusion (preliminary)
For an **Apache-2.0 outbound** license, every declared runtime dependency above
is compatible (MIT/BSD/ISC/Apache-2.0 are permissive; MPL-2.0 `pathspec` is
file-level copyleft, satisfied by shipping it unmodified as a dependency). No
declared GPL/AGPL/LGPL runtime dependency was found. **Caveat:** this conclusion
covers *declared package licenses only* — it does not clear source-level
copy-paste/LLM-match risk, which the scancode scan (still pending) must cover.

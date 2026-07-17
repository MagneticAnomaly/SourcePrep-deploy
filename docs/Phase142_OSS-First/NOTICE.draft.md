# NOTICE (DRAFT)

> **Status:** DRAFT for review — becomes root `NOTICE` at publish, sequenced
> after the license decision (Apache vs AGPL) and IP Assignment. Attributions
> below are derived from the declared dependency licenses inventoried in
> `LICENSE-AUDIT.md` (2026-07-17). Verify completeness with a scancode pass and a
> full `license-checker` monorepo run before shipping.

---

SourcePrep
Copyright (c) 2026 Magnetic Anomaly LLC

This product includes software developed by third parties. The following
components are distributed under their respective licenses. Full license texts
are available from each project.

## Machine-learning model
- **nomic-embed-text-v1.5** — Apache License 2.0 — Nomic AI. Bundled/downloaded
  as the default local embedding model.

## Python components
- **NetworkX** — BSD-3-Clause
- **NumPy** — BSD-3-Clause
- **ONNX Runtime** — MIT — Microsoft
- **tokenizers**, **huggingface_hub** — Apache-2.0 — Hugging Face
- **watchdog** — Apache-2.0
- **pathspec** — Mozilla Public License 2.0
- **cryptography** — Apache-2.0 / BSD-3-Clause — PyCA
- **FastAPI**, **Pydantic**, **Typer**, **Rich** — MIT
- **Starlette / Uvicorn**, **httpx** — BSD-3-Clause
- **Requests** — Apache-2.0

## Rust components
- **tree-sitter** and grammars (Python, TypeScript, JavaScript, Rust, Go, Java,
  C, C++) — MIT
- **serde**, **rayon**, **PyO3** — MIT / Apache-2.0
- **ignore**, **walkdir** — MIT / Unlicense

## Frontend (TypeScript/React) components
- **React** — MIT — Meta
- **Radix UI** (`@radix-ui/*`) — MIT — WorkOS
- **Tremor** (`@tremor/react`) — Apache-2.0
- **React Flow** (`@xyflow/react`) — MIT
- **lucide-react** — ISC
- **react-grid-layout**, **react-syntax-highlighter** — MIT
- **clsx**, **tailwind-merge**, **Tailwind CSS** — MIT

---

_This NOTICE is provided for attribution under the terms of the project's
outbound license. It is not itself a grant of rights._

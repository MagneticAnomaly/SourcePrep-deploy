# Deep-Research Session C — SBOM / vendored-copyleft scan (DR-1): Findings

**Date:** 2026-07-19
**Status:** COMPLETE — scan run, reconciled, gate verdict rendered.
**Scope:** the public-mirror push gate (`PUBLIC_MIRROR_MANIFEST_2026-07-19.json`).
**Handoff:** `docs/Phase142_OSS-First/DEEP_RESEARCH_HANDOFF_C_SBOM.md`
**Prior partial:** `docs/Phase142_OSS-First/LICENSE-AUDIT.md` (2026-07-17, dependency inventory only; source-scan gap left open — this doc closes it).

> **One-line gate verdict:** **CLEAR** to push the public *source* mirror on
> copyleft/license-contamination grounds. The mirror distributes only
> first-party Apache-2.0/MIT code; every non-permissive license found is
> fetch-at-install, dev-only, or otherwise excluded from the mirror. Six
> follow-up items (none block the *source* push) are itemised in §3 and §7 —
> two of them (NOTICE `certifi`/`tqdm` attribution; vendor-logo trademark
> note) should be resolved before the *binary* release artifacts and are
> cross-checked with the legal session.

---

## 1. Method

### Tools actually run (this session)

| Ecosystem / target | Tool | Version | Result |
|---|---|---|---|
| Python (installed `.venv`, 107 pkgs) | `pip-licenses` + project gate `tools/check_python_licenses.py` | 5.5.5 | **PASS** |
| npm (root workspace closure, ~1097–1377 pkgs) | project gate `tools/check_npm_licenses.mjs` | node 22 | **PASS** (with a coverage bug — §3.1) |
| npm (root production) | `npx license-checker --production` | latest | PASS (30 pkgs, all permissive) |
| Rust **engine** (`engine/`, 95 crates) | `cargo deny check licenses` | cargo-deny 0.20.2 / cargo 1.93.1 | **PASS** (`licenses ok`) |
| Rust **Tauri app** (`src/prep/dashboard/src-tauri/`, 539 crates) | `cargo deny check licenses` | cargo-deny 0.20.2 | **PASS on 3rd-party** (only first-party `prep` crate flagged — §3.4) |
| Source-text (1245 first-party files) | `scancode-toolkit` | 32.5.0 | **CLEAR** — see §4 |

**scancode ran the full toolkit** (authorization lifted for this session per
the handoff). It is installed in a throwaway venv
(`scratchpad/scancode-venv`), with an arm64 `libmagic` from `/opt/homebrew`
(the default x86_64 brew build mismatched the arm64 Python). To avoid the
`--ignore` globs failing to exclude nested `node_modules` (they did, on a
naive full-tree run), the source scan was run over a **`git archive HEAD`
export** of the distributed first-party trees — tracked files only, so
`node_modules`/`.venv`/`target` are structurally absent. Raw outputs are in
`docs/Phase142_OSS-First/scan-output/`.

### Scope & the decisive scoping fact

The public mirror is a **curated 1662-file subset** (`included` bucket of the
manifest). It **ships only first-party source**; third-party dependencies are
fetched at install/build time (pip/npm/cargo) and are **not vendored**:

- 0 paths under `included[]` match `node_modules` / `site-packages` / `.venv`
  / `target` / `dist` / `vendor`.
- No `vendor/` or `third_party/` directory anywhere in the tree.
- No committed model weights (`*.onnx`/`*.safetensors`) or grammar binaries
  (`*.so`/`*.wasm`) — the ONNX embedder is downloaded at runtime; tree-sitter
  grammars are cargo crates.
- `docs/` is almost entirely excluded (3 of ~1064 docs files included), so
  two of the three handoff "hotspots" — `docs/Phase13_Storybook` and
  `docs/Phase14_MCP-CLI/codrag-mcp-template` — are **not distributed** at all.
  Only `packages/vscode` (40 files) ships.

Consequence: a copyleft license can only *contaminate the Apache-2.0 mirror*
if it appears in **distributed first-party source**. The dependency scans
below therefore matter for (a) NOTICE attribution and (b) the *binary*
release artifacts (Docker/PyInstaller/Tauri) that DO bundle dependencies —
not for the source-mirror grant.

### Limitations

- scancode was scoped to the 1245-file first-party export (all shipped source
  + the two non-shipped hotspots), not every doc/markdown file in the repo. A
  complementary **whole-tree grep** for copyleft license strings + SPDX tags
  and a **foreign-copyright-header sweep** were run across *all* tracked files
  as the broad net (both clean — §4).
- The npm gate's own coverage is incomplete (skips scoped packages — §3.1);
  this session re-derived the scoped set independently rather than trust it.
- Container base images, GitHub Actions, and other non-package assets are
  noted in §7 as out-of-scope for the source mirror.

---

## 2. Per-component license summary

Full per-package data: `scan-output/pip_licenses.json`,
`scan-output/cargo_metadata.json`, `scan-output/cargo_metadata_tauri.json`,
`scan-output/npm_licenses.json`, `scan-output/cargo_deny_licenses.txt`,
`scan-output/cargo_deny_tauri.txt`, `scan-output/sbom_scan.json`.

### 2.1 Python (runtime, from `pyproject.toml` + transitive closure)

| Component | License | Kind | In NOTICE? | Verdict |
|---|---|---|---|---|
| networkx | BSD-3-Clause | direct runtime | yes | ok |
| numpy | BSD-3-Clause | direct | yes | ok |
| onnxruntime | MIT | direct | yes | ok |
| tokenizers, huggingface-hub | Apache-2.0 | direct | yes | ok |
| watchdog, requests | Apache-2.0 | direct | yes | ok |
| fastapi, pydantic(-settings), typer, rich, python-multipart | MIT | direct | partial | ok |
| starlette/uvicorn, httpx | BSD-3-Clause | direct | yes | ok |
| cryptography | Apache-2.0 OR BSD-3-Clause | direct | yes | ok |
| aiosqlite | MIT | direct | no | ok (add for completeness) |
| **pathspec** | **MPL-2.0** | direct | yes | ok (weak, unmodified) |
| **certifi** | **MPL-2.0** | transitive (requests/httpx) | **NO** | **attribute** (§3.2) |
| **tqdm** | **MPL-2.0 AND MIT** | transitive (huggingface-hub) | **NO** | **attribute** (§3.2) |
| pyinstaller / pyinstaller-hooks-contrib | GPL-2.0 (+Apache) | **dev-only** build tool | n/a | ok (§3.5, documented exception) |
| prep / prep-engine | Apache-2.0 (reads "UNKNOWN") | first-party | n/a | ok |

No GPL/AGPL/LGPL in the Python **runtime** closure.

### 2.2 Rust

- **Engine** (`engine/`, 95 crates): `cargo deny check licenses` → **`licenses
  ok`**. Distribution: MIT / Apache-2.0 / BSD / ISC / Zlib / CC0 / Unicode /
  Unlicense duals only. The one copyleft-token crate, `r-efi` (`MIT OR
  Apache-2.0 OR LGPL-2.1-or-later`), is a disjunctive triple-license — the
  permissive election is valid.
- **Tauri app** (`src/prep/dashboard/src-tauri/`, 539 crates): all 539
  third-party crates permissive (246 "MIT OR Apache-2.0", 133 MIT, …).
  **0 copyleft-only crates.** Five MPL-2.0 crates (`cssparser`,
  `cssparser-macros`, `dtoa-short`, `selectors`, `thin-slice` — Servo/webview)
  are allowed (weak, file-level); they matter only for **binary** attribution
  (§3.2/§5). cargo-deny returns `FAILED` **only** on the first-party `prep`
  crate lacking a `license` field (§3.4) — a hygiene issue, not contamination.

### 2.3 npm

- Native gate (`tools/check_npm_licenses.mjs`): **PASS** — 0 GPL/AGPL across
  the covered closure; 3 documented MIT metadata exceptions
  (`busboy`, `streamsearch`, `format`). **Caveat:** the gate silently skips
  all scoped `@scope/name` packages (§3.1), so its green is not, by itself,
  trustworthy coverage — this session re-derived the scoped set.
- Independent scoped re-derivation surfaced two non-permissive scoped packages
  (`@vscode/vsce-sign` proprietary; `elkjs` EPL-2.0) and two CC-BY data
  packages (`caniuse-lite`, `spdx-exceptions`). **All are fetch-at-install and
  absent from the mirror** (verified: 0 `included[]` paths contain any of
  them). See §3.1/§3.3.

---

## 3. Non-permissive hits — framed decisions

None of the below distributes copyleft/proprietary code in the **source
mirror**. Each is framed as a recommendation with a default; the decision is
Eric's / an attorney's per hit.

### 3.1 npm license gate skips all scoped packages — **gate reliability** (recommend: **fix**)

`tools/check_npm_licenses.mjs:111` — `if (!name || name.includes("/"))
continue;` — treats any scoped name (`@vscode/vsce-sign`) as "not a real
package leaf" and skips it. This drops **~442 scoped packages (~32% of the
closure)**, including the proprietary **`@vscode/vsce-sign`** (Microsoft
Software License Terms) and EPL-2.0 `elkjs`. The gate's exit-0 is therefore
**not evidence** the scoped tree is clean.

- **Distributed?** No. `@vscode/vsce-sign` is a `vsce`/publish build tool;
  `elkjs` is fetch-at-install. 0 mirror paths.
- **Recommended default:** *fix* the scoped-name extraction so scoped packages
  are checked, then add a documented dev-tool `EXCEPTION` for
  `@vscode/vsce-sign*` (proprietary, build/publish-only, never distributed).
  Also harden the fail-set to flag EPL/CDDL/MS-RL/EUPL (currently only
  GPL/AGPL/UNKNOWN/"SEE LICENSE IN" fail). **Not a source-push blocker.**

### 3.2 `certifi` (MPL-2.0) and `tqdm` (MPL-2.0 AND MIT) missing from NOTICE — **attribution** (recommend: **attribute**)

Both are core-runtime transitive deps (`certifi` ← requests/httpx; `tqdm` ←
huggingface-hub) in the same weak-copyleft class as the listed `pathspec`, but
neither is in NOTICE — an internal inconsistency.

- **Distributed?** Not in the source mirror (fetch-at-install). **But** the
  GHCR image (`docker-headless.yml`, `pip install .[headless]`) and the
  PyInstaller/Tauri desktop app (`release.yml`, `prep-daemon.spec`
  `collect_all('prep')`) **do bundle** them → MPL-2.0 §3.2 applies to those
  binary artifacts (light — see §5).
- **Recommended default:** *attribute* — add `certifi` (MPL-2.0) and `tqdm`
  (MPL-2.0 AND MIT) to the NOTICE Python section, plus a "source obtainable at
  PyPI/upstream" pointer. Required **before shipping the binary artifacts**;
  hygiene for the source mirror.

### 3.3 `elkjs` (EPL-2.0), `caniuse-lite`/`spdx-exceptions` (CC-BY) — **binary-bundle attribution** (recommend: **attribute if bundled**)

`elkjs` (a `packages/ui` graph-layout dep) is **EPL-2.0** (weak reciprocal
copyleft); `caniuse-lite` (CC-BY-4.0) and `spdx-exceptions` (CC-BY-3.0) are
attribution-only data packages. All fall through the npm gate's fail-set.

- **Distributed?** Not in the source mirror. `elkjs` *may* end up in the
  built Storybook/dashboard bundles (`packages/ui` is compiled into both).
- **Recommended default:** *no action for the source push*; if any deployed
  build bundles `packages/ui`, add an EPL-2.0 attribution + offer-of-source
  for `elkjs` and CC-BY attributions. EPL-2.0 is Apache-compatible for
  aggregation; the obligation is attribution/source-availability, not
  relicensing.

### 3.4 First-party `prep` crate (src-tauri) has no `license` field — **hygiene** (recommend: **fix**)

`src/prep/dashboard/src-tauri/Cargo.toml` declares `name = "prep"` with no
`license` field, so `cargo deny` reports `error[unlicensed]: prep = 0.1.0`.
This is our own crate (Apache-2.0 via the repo), not third-party.

- **Recommended default:** *fix* — add `license = "Apache-2.0"` to
  `src-tauri/Cargo.toml` (mirrors `pyproject.toml:10` and the engine
  workspace). Then wire a **second cargo-deny CI job** with
  `working-directory: src/prep/dashboard/src-tauri` so the 539-crate Tauri
  tree is gated on every push (today only `engine/`'s 95 are — §7).

### 3.5 `pyinstaller` / `pyinstaller-hooks-contrib` (GPL-2.0) — **dev tool** (recommend: **none**)

Flagged for honesty. Both are **dev/build-only** (`pyproject.toml`
`[project.optional-dependencies].dev`, absent from core `dependencies`), with
a documented gate exception. PyInstaller's GPL does not reach bundled output
(bootloader exception). Not a runtime dep, not distributed source.

- **Recommended default:** *none* — verified-clean and correctly scoped.

### 3.6 Vendor/competitor logos in the mirror — **trademark, cross-cutting to legal** (recommend: **escalate to Session A**)

`websites/apps/marketing/public/logos/` ships 9 third-party **trademarked**
brand assets — `claude.svg` (Anthropic), `cursor*.svg` (Cursor), `gemini.svg`
(Google), `vscode.svg` + `copilot.png` (Microsoft), `windsurf*.svg`
(Codeium), `paperclip.svg` — all in the mirror `included` set, with no
trademark/nominative-use note (`grep -i trademark NOTICE` → nothing). This is
a **trademark** obligation class no SBOM scanner touches; it is not a
copyleft/copyright-license blocker.

- **Recommended default:** *escalate to the legal session (A)* — add a
  nominative-use/trademark note ("logos are the property of their respective
  owners; used to indicate compatibility") or confirm each vendor's brand-usage
  policy permits redistribution, **before** the public push. Out of pure-SBOM
  scope but surfaced here so it is not lost.

---

## 4. Vendored / LLM-generated copyleft scan — the open question

**Definitive answer: NO.** No vendored or model-generated copyleft
(GPL/AGPL/LGPL/MPL/CC-BY-SA) source is hiding in the distributed tree. Five
independent signals agree:

1. **scancode-toolkit 32.5.0** over the 1245-file first-party export
   (`scan-output/sbom_scan.json`, 1164 files scanned in 218s): only **44**
   files carry a detected license expression, all permissive — 24 apache-2.0,
   6 mit, plus json/bsd/isc/cc-by-4.0. Eight files matched a copyleft/
   proprietary token; **every one is a verified false positive in first-party
   license-*discussion* text, not vendored code** (see the table below).
2. **Whole-tree copyleft-string grep** (all tracked files, SPDX tags + license
   names for GPL/AGPL/LGPL/CC-BY-SA/copyleft): the only hits are
   meta-discussion in planning docs and the license-gate tooling's own
   comments — **zero in shipped source**.
3. **Foreign-copyright-header sweep** across all distributed `.py/.ts/.tsx/.js/
   .jsx/.rs/.css`: **zero** non-Magnetic-Anomaly copyright headers.
4. **Deep-read verification agent** (independent read of all distributed
   hotspots — `packages/vscode` 24 files, `packages/paperclip-plugin-prep`,
   `public/sourceprep-mcp` — and the two non-shipped hotspots): **CLEAR**. The
   only third-party couplings are permissive fetch-at-install deps and
   MIT-origin boilerplate (Microsoft `vscode-extension-samples` `getNonce`
   pattern; Heroicons SVG path data). No minified vendor blob (longest
   distributed line 240 chars).
5. **No vendored source/binaries** anywhere (§1).

`docs/Phase14_MCP-CLI/codrag-mcp-template/bin/codrag-mcp.js` is byte-identical
to the first-party `public/sourceprep-mcp` shim (the only delta is the dead
`codrag` codename in log strings — a branding cleanup, tracked separately, and
excluded from the mirror regardless).

### scancode copyleft/proprietary detections — all false positives

Every one of the 8 flagged files is **tracked first-party** and flagged only
because scancode matched license *vocabulary* in prose/config, not vendored
copyleft code:

| File (first-party) | scancode expr | Why it's a false positive |
|---|---|---|
| `src/prep/core/cluster.py` | gpl-1.0-plus … | The GPL-**removal** comment/docstring ("Earlier versions used Leiden via igraph+leidenalg (GPL)"). Code is networkx Louvain. |
| `tools/check_npm_licenses.mjs` | gpl/agpl/lgpl … | The license-gate script's own `FAIL_PATTERNS` array + comments naming the licenses it rejects. |
| `tools/check_python_licenses.py` | gpl/agpl/lgpl … | Same — the Python gate's `FAIL_PATTERNS` + the PyInstaller-exception prose. |
| `src/prep/dashboard/package-lock.json` | …cc-by-4.0… | Lockfile: scancode aggregates the *declared* licenses of listed deps (e.g. caniuse-lite = CC-BY-4.0). Metadata, not vendored code. |
| `docs/Phase13_Storybook/.../tremor-preview/package-lock.json` | …cc-by-4.0… | Same lockfile aggregation; also excluded from the mirror. |
| `packages/vscode/README.md` | proprietary-license | First-party README `## License` section text. |
| `websites/apps/marketing/src/app/terms/page.tsx` | proprietary-license | Our own Terms page — its text literally affirms "SourcePrep source code is licensed under the Apache License 2.0". |
| `src/prep/core/lemon_squeezy.py`, `.../hooks/useLicenseSystem.ts` | json | First-party JSON/license-handling code; scancode matched the generic "json" token. |

**No file in the distributed tree carries actual vendored or LLM-generated
GPL/AGPL/LGPL/MPL/EPL/CC-BY-SA source.** scancode's result corroborates the
whole-tree grep, the foreign-copyright sweep, and the deep-read agent.

---

## 5. MPL-2.0 file-level obligation

MPL-2.0 deps: **Python** — `pathspec`, `certifi`, `tqdm` (MPL portion);
**Rust (Tauri)** — `cssparser`, `cssparser-macros`, `dtoa-short`, `selectors`,
`thin-slice`. (Engine Rust tree has **no** MPL crate — cargo-deny reported the
`MPL-2.0` allowance unused.) `pathspec` confirmed verbatim MPL-2.0; `certifi`
METADATA `License: MPL-2.0`; `tqdm` is MPL-2.0 for all files except the
MIT-licensed `tqdm/_tqdm.py`.

**Source-mirror push: NOT triggered.** MPL-2.0 §3.1/§3.2 obligations attach to
*distribution of Covered Software*. None of these packages is vendored (0
paths in the git tree or the mirror manifest; `.venv` untracked; no wheel/
bundle in the mirror). **Declaring a pip/cargo dependency is not distributing
Covered Software** — so the source-mirror push triggers no MPL obligation.

**Binary release artifacts: lightly triggered.** The GHCR image and the
PyInstaller/Tauri desktop app bundle the MPL binaries in Executable Form,
engaging §3.2. The obligation is **light**: the packages are unmodified
upstream, MPL is file-level copyleft, and §3.3 explicitly permits the
Apache+MPL "Larger Work." Satisfy it by (a) attributing `certifi`, `tqdm`, and
the five Tauri MPL crates in NOTICE, and (b) providing a "source obtainable
at [PyPI/crates.io/upstream]" pointer. No relicensing, no source rebundling
required.

---

## 6. NOTICE recommendations

| # | Item | Type | Action |
|---|---|---|---|
| 6.1 | `NOTICE:27` pointed to internal `AI_WORK_TODO.md Stream 3` (dangling in the mirror — `docs/` not shipped) | fix-now | **APPLIED** → now points to `docs/Phase142_OSS-First/README.md` (commit alongside this doc) |
| 6.2 | `certifi` (MPL-2.0), `tqdm` (MPL-2.0 AND MIT), and the 5 Tauri MPL crates missing | attribute | **recommend** — add before the binary-artifact release; hygiene for the source mirror |
| 6.3 | `NOTICE:22-27` DRAFT / "legal-trigger review" banner ships as-is | recommend-only | **recommend removal at publish (Eric signs off)** — the scancode + monorepo verification the banner demands is now DONE (this doc). NOT removed here per handoff. |
| 6.4 | `NOTICE:30-31` calls the ONNX model "Bundled / downloaded" | hygiene | **recommend** reword — the model is downloaded at runtime from HuggingFace, not bundled/distributed (no `*.onnx` in tree/manifest). Over-attribution is safe; info only. |
| 6.5 | `aiosqlite` (MIT), `python-multipart` — minor completeness | hygiene | optional — add for a complete runtime attribution set |

Per the handoff, the DRAFT banner (6.3) is **recommend-only** and awaits
Eric's sign-off; only the `NOTICE:27` pointer (6.1) was applied.

---

## 7. Gate verdict

### PUBLIC MIRROR (source) PUSH: **CLEAR** on copyleft/license-contamination

**Rationale:** The mirror distributes only first-party Apache-2.0/MIT source.
All three dependency ecosystems (Python 107, npm closure, Rust 95 engine + 539
Tauri) are permissive; the GPL community-detection dep was removed and guarded
(verified — §4/Appendix); no vendored or LLM-generated copyleft source exists;
no third-party dependency source is shipped. Every non-permissive license
found is fetch-at-install, dev-only, or excluded.

### Follow-up docket (none block the *source* push)

| Item | Severity | Before what? | §  |
|---|---|---|---|
| Fix npm gate scoped-package skip + fail-set (EPL/CDDL) | gate reliability | next license-gate run | 3.1 |
| Add second cargo-deny CI job for the 539-crate Tauri tree | gate coverage | next CI change | 3.4 / 7 |
| Add `license = "Apache-2.0"` to `src-tauri/Cargo.toml` | hygiene | Tauri gate | 3.4 |
| Add `certifi`/`tqdm` + 5 Tauri MPL crates to NOTICE | attribution | **binary release** (Docker/PyInstaller/Tauri) | 3.2 / 5 / 6.2 |
| `elkjs` EPL-2.0 attribution if `packages/ui` is bundled in a deployed build | attribution | Storybook/dashboard deploy | 3.3 |
| **Vendor-logo trademark note** | trademark (cross-cutting) | **public push** — Eric/legal call | 3.6 |
| Remove NOTICE DRAFT banner + reword ONNX line | hygiene | publish (Eric signs off) | 6.3 / 6.4 |

**The only item that plausibly warrants Eric/legal sign-off *before* the
public push is the vendor-logo trademark note (§3.6)** — and that is a
trademark question, not a copyleft/SBOM one, flagged here for the legal
session (A). On the SBOM/copyleft mandate this session owns, the gate is
**CLEAR**.

---

## Appendix — GPL community-detection removal (Phase 144 Blocker #1): CLOSED

`src/prep/core/cluster.py` previously used `igraph` (GPL-2.0) + `leidenalg`
(GPL-3.0) for community detection. Verified replaced with `networkx` Louvain
(BSD-3-Clause):

- `cluster.py:40` `import networkx as nx`; both algorithmic functions call
  `nx.algorithms.community.louvain_communities(...)` (L779, L981); the third
  path is pure BFS. Only `igraph`/`leidenalg` tokens remaining are prose
  comments.
- Repo-wide `grep 'import igraph|leidenalg'` (excl `.venv`/`node_modules`/
  `docs`) → **empty**. No `importlib`/`subprocess` GPL re-entry.
- Neither GPL lib installed in `.venv`; no alternative GPL community lib
  (`community`/`python-louvain`/`cdlib`/`graph-tool`/`pygraphviz`).
- Guard `tests/test_no_gpl_deps.py` present + run by
  `.github/workflows/license-audit.yml`.
- `networkx` 3.6.1 confirmed BSD-3-Clause from its own LICENSE.

_Naming debt (non-blocking): `build_clusters_leiden` still runs Louvain
internally — optional rename._

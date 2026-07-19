# SBOM scan outputs — Deep-Research Session C (DR-1), 2026-07-19

Raw artifacts backing `../DEEP_RESEARCH_C_SBOM_FINDINGS.md`. Large JSONs are
gzipped (`gunzip -k <file>.gz` to read). This dir is under `docs/` and is
**excluded from the public mirror** — it's a private compliance record.

| File | Tool | What |
|---|---|---|
| `pip_licenses.json` | pip-licenses 5.5.5 | Python `.venv` closure (107 pkgs) |
| `npm_licenses.json` | license-checker | root npm production deps (30 pkgs) |
| `cargo_metadata.json.gz` | cargo metadata (1.93.1) | engine crate licenses (95) |
| `cargo_deny_licenses.txt` | cargo-deny 0.20.2 | engine license gate — `licenses ok` |
| `cargo_metadata_tauri.json.gz` | cargo metadata | Tauri app crate licenses (539) |
| `cargo_deny_tauri.txt` | cargo-deny | Tauri license gate — 3rd-party clean; only first-party `prep` crate flagged (no license field) |
| `sbom_scan.json.gz` | scancode-toolkit 32.5.0 | source-license scan of the 1245-file first-party `git archive` export (1164 files scanned) |

Note: `sbom_scan.json` paths are prefixed `scan-tree/` (the `git archive HEAD`
export used to guarantee no `node_modules`/`.venv`/`target` in the scan).

# 03 — Security Tooling Baseline

**Verified:** 2026-06-16 (negative findings confirmed by absence-search).
The point of this doc: know what the pipeline already catches so the human audit
spends its time on what tooling *can't* see, and so Phase 8 (hardening) has a
concrete gap list.

---

## What runs today (CI)

`.github/workflows/security-audit.yml` — on push/PR to `main`, weekly cron
(Mon 06:00 UTC), and `workflow_dispatch`:

| Job | Tool | Scope | Blocking? |
|-----|------|-------|-----------|
| `python-safety` *(misnomer — runs pip-audit, not `safety`)* | **pip-audit** | resolved `[dev]` deps | yes |
| `npm-audit` | **npm audit** | root (`--audit-level=critical`, blocking); `packages/ui` + `public/sourceprep-mcp` (`--audit-level=high`, `|| true` non-blocking) | partial |
| `cargo-audit` | **cargo audit** | `engine/` Rust deps | yes |

**That's the whole automated security surface: dependency-vuln scanning only.**

## Runtime defenses (product code, with tests)

These are *application* protections, not CI scanners — but they're real and unit-tested:

| Defense | Code | Test |
|---------|------|------|
| LLM input sanitization (invisible-unicode/homoglyph injection, OWASP LLM01) | `core/content_sanitizer.py`, `core/llm_client.py:692` | `tests/test_content_sanitizer.py` |
| DLP / cloud-provider allowlist | `core/team_config.py` (admin policy) | `tests/test_admin_policy.py` |
| Secret-leak guard before remote upload | `services/remote_sync.py` | `tests/test_remote_sync.py` (`TestCheckForLeakedSecrets`) |
| SARIF parse + size-limit (DoS guard) | `core/sarif*.py` | `tests/test_sarif.py`, `tests/test_sarif_adapters.py` |
| GPL-dependency regression guard | (import guard) | `tests/test_no_gpl_deps.py` |
| 16 runtime "security health" checks | `core/security_health.py:576` | **none — `tests/test_security_health.py` is ABSENT** |

The 16 health checks (license, S3 endpoint, secrets perms, index integrity, DLP,
config drift, network, daemon auth, CORS, dev-mode, content sanitization, API-key
hygiene, MCP rate-limit, secret-detection coverage, data-exposure, unicode-in-index)
are **end-user posture checks** wired only into the admin panel
(`api/routers/settings.py`) — they are *not* a repo SAST/DAST pipeline, and they
have no test coverage. Phase 8 should add `tests/test_security_health.py`.

## What's absent (the gap list for Phase 8)

| Category | Tool | Status | Note |
|----------|------|--------|------|
| Python SAST | **bandit** | ❌ absent | not in `[dev]` deps or CI |
| Python SAST | ruff `S` / flake8-bandit rules | ❌ absent | `pyproject.toml:114-122` selects `E,W,F,I,B,C4,UP` — no `S` |
| Multi-lang SAST | **semgrep** | ❌ not run | exists only as a SARIF *input* adapter (`core/sarif_adapters.py:22`) |
| Code scanning | **CodeQL** | ❌ not run | only a SARIF input adapter (`sarif_adapters.py:27`) |
| Secret scanning | **gitleaks / trufflehog** | ❌ absent | no CI step, no config |
| Dep updates | **Dependabot** | ❌ absent | no `.github/dependabot.yml` |
| Rust license/advisory | **cargo-deny** | ❌ absent | `deny.toml` planned in Phase142/144 docs only |
| License/SBOM gate | pip-licenses `--fail-on`, cyclonedx, syft | ❌ absent | `pip_licenses_report.json` is a manual one-off |
| DAST / container scan | Trivy / ZAP / OSV / grype | ❌ absent | docker workflow builds but doesn't scan |
| Pre-commit | root `.pre-commit-config.yaml` | ❌ absent | `pre-commit` is a `[dev]` dep with no config |

> **Irony worth noting:** SourcePrep's own `prep_audit` *ingests and enriches*
> SARIF from semgrep/CodeQL/ruff/eslint, but the repo never *runs* any of those
> scanners against itself. Phase 8 can dogfood: run semgrep → pipe through
> `prep_audit(findings=...)` → triage with structural context.

## Supply chain

- **Strongest leg:** pip-audit + npm audit + cargo audit (above).
- **No SBOM tooling** of any kind (cyclonedx/spdx/syft/grype/trivy).
- **No automated license gate** — `cargo deny check licenses` /
  `pip-licenses --fail-on=GPL` / `license-checker` are docs-only aspirations
  (`Phase142_OSS-First/`, `Phase144_LegalPreLaunch/`). The only enforced license
  guard is the runtime/test `tests/test_no_gpl_deps.py`.
- **No Dependabot** → dependency upgrades are manual.

## Immune-system opportunity (prep-native)

`prep_audit(action="antibodies")` returns **no antibodies** today — there are no
`constraint`/`architecture` concepts with anchors. The audit should *create* them
so the codebase actively defends its own invariants. Candidate constraint concepts
to seed (via `prep_concepts`), each with a testable assertion + file anchor:

- "The daemon must never bind a non-loopback host without `PREP_DAEMON_TOKEN`" → anchor `server.py:246`
- "`/license/dev-override` must be unreachable unless `PREP_DEV_MODE=1` was set at launch" → anchor `api/routers/license.py:502`
- "All outbound URLs from user config must pass `is_safe_url`/`_validate_s3_endpoint`" → anchors `llm.py:159`, `remote_sync.py:71`
- "Archive extraction must enforce uncompressed-size + zip-slip bounds" → anchor `s3_storage.py:292`
- "Audit-log detail payloads must be secret-redacted before persistence" → anchor `core/audit_log.py:148`

Once saved, these surface as immune-system alerts in `prep()` ambient context and
fire when a future edit violates them — turning this one-time audit into a
standing defense.

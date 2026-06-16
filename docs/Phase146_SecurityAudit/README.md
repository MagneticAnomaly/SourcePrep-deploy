# Phase 146 — Security Audit (Scaffold)

**Status:** Scaffolding / pre-deep-dive
**Opened:** 2026-06-16
**Supersedes:** `docs/Phase_SecurityAuditPrep/` (removed — see Errata below)

---

## Purpose

Build the foundation for a deep, orchestrated security audit of SourcePrep.
This phase does **not** find vulnerabilities — it establishes verified ground
truth so the later deep-dive phases start from facts, not guesses.

## The one rule for this phase (Provenance Policy)

> **Every file path cited must be confirmed to exist. Every "fixed / unfixed"
> claim must cite `file:line` evidence. No invented CVSS, no invented
> percentages, no pre-written "expected findings."**

This rule exists because the first pass violated all of it (see Errata). If a
claim cannot be grounded in a read of the source, it is labelled
**CANDIDATE / UNVERIFIED** and routed to a deep phase for confirmation — it is
never stated as fact.

---

## Documents

| File | What it is | Trust level |
|------|-----------|-------------|
| [`STATUS.md`](STATUS.md) | **Living progress ledger** — the single source of truth for what's verified, pending, and owned. Update this as work proceeds. | authoritative |
| [`01_ORIENTATION.md`](01_ORIENTATION.md) | Verified architecture + real attack surface + data-ingest entry points | verified 2026-06-16 |
| [`02_PRIOR_FINDINGS_LEDGER.md`](02_PRIOR_FINDINGS_LEDGER.md) | The real Phase 06 audit findings, real locations, and current code state | verified 2026-06-16 |
| [`03_TOOLING_BASELINE.md`](03_TOOLING_BASELINE.md) | Security tooling that exists vs. is absent (CI, SAST, secret-scan, SBOM) | verified 2026-06-16 |
| [`04_CANDIDATE_FINDINGS.md`](04_CANDIDATE_FINDINGS.md) | New, **unverified** issues this pass surfaced — the deep phases' starting backlog | candidate |
| [`05_DEEP_DIVE_PLAN.md`](05_DEEP_DIVE_PLAN.md) | The workstream plan + multi-agent orchestration design for the real audit | plan |

Read `STATUS.md` first. It indexes everything else by state.

---

## How this was built

The scaffolding was rebuilt by a 6-agent verification workflow
(`security-scaffold-verify`, run 2026-06-16) that read the actual source:
the prior audit doc, the root `SECURITY.md`, the HTTP/MCP/CLI attack surface,
the real security-critical files, the CI/tooling config, and an adversarial
review of the first pass. Findings in 01–03 are double-sourced where the
verifier and the file-locator agents independently confirmed them; anything
single-sourced or inferred is marked as such.

---

## Dogfooding note

SourcePrep is both the audit target and (normally) the audit tool. The `prep`
MCP server was **disconnected** during this session, so this scaffold was built
with raw file tools + a verification workflow instead. That itself is a product
data point: when the daemon is down, the agent loses all structural context and
must fall back to grep/glob. The deep phases should note every place where a
live `prep` query would have changed the analysis.

---

## Errata — why the first pass was discarded

The initial orientation (committed `0aa18e0e`, authored under a lighter model)
was **largely ungrounded** and is preserved only in git history. An adversarial
review found:

- **~60–70% of cited file paths did not exist** — e.g. the entire
  `src/prep/core/auth/` tree, `core/storage.py`, `core/telemetry.py`,
  `adapters/git.py`, `services/llm_augmenter.py`, `services/import_service.py`.
  The audit's #1 "must-review" target (`src/prep/core/auth/`) was fabricated.
- **100% of the prior-finding statuses were wrong** — CRIT-1, CRIT-2 and
  HIGH-5 were asserted "UNRESOLVED" when the code shows them addressed
  (Ed25519 license verify, S3 SSRF guard, 10 GB zip-bomb cap).
- Invented CVSS scores, invented surface-area percentages, and pre-written
  "expected findings" that biased the audit toward conclusions the code
  contradicts.

For a security audit, "already fixed" stated as "unresolved" wastes effort, and
fabricated paths send reviewers to dead ends — but the inverse (calling a live
hole "fixed") is dangerous. Everything in this phase is rebuilt from verified
reads to avoid both.

# Startup Prompt — Phase 146 Security Audit

Paste the block below into a fresh session to pick up where we left off.
(Last checkpoint: commit `b961879c`, 2026-06-16 — scaffolding complete, audit not yet started.)

---

```
We're resuming the SourcePrep security audit (Phase 146). Use the prep MCP tool.

FIRST: call `prep` (no args) for structural orientation, then read these in order:
- docs/Phase146_SecurityAudit/STATUS.md   ← the living ledger; START HERE
- docs/Phase146_SecurityAudit/README.md   ← charter + provenance policy + errata
- docs/Phase146_SecurityAudit/05_DEEP_DIVE_PLAN.md ← the 8 workstreams
- docs/Phase146_SecurityAudit/04_CANDIDATE_FINDINGS.md ← unverified backlog

CONTEXT (don't re-derive this):
- NO audit has been performed yet. Everything in Phase146 is SCAFFOLDING built
  on verified ground truth. Nothing in it is a finding.
- The "prior audit" referenced in the docs is an OLD repo artifact
  (docs/Phase06_Team_And_Enterprise/SECURITY_AUDIT.md, Mar 2026) — not our work.
- An earlier scaffold (docs/Phase_SecurityAuditPrep/, commit 0aa18e0e) was
  discarded because ~60-70% of its file paths were fabricated and 100% of its
  finding-statuses were inverted. The provenance policy exists to prevent that:
  every cited path must exist; every "fixed/open" claim must cite file:line;
  no invented CVSS; no pre-written "expected findings."

PROVENANCE POLICY (enforce it): if a claim can't be grounded in a source read,
label it CANDIDATE/UNVERIFIED and route it to a deep phase — never state it as fact.

DECISIONS NEEDED before deep work (see STATUS.md "Open decisions"):
- D-1: run deep phases as one big workflow, or one phase at a time w/ review? (rec: one at a time)
- D-2: scope = product code only, or also public/sourceprep-deploy/ + websites/?
- D-3: THREAT MODEL — can the daemon ever run non-loopback? This swings candidates
  C-1 (auth off by default) and C-5 (MCP transport no token) from medium to critical.
  Answer D-3 first; Phase 1 depends on it.

RECOMMENDED NEXT STEP: Phase 1 — Auth & Daemon Boundary (risk-first). Scope/files
are in 05_DEEP_DIVE_PLAN.md. Per-phase shape: Map → Probe → adversarially-Verify
→ Synthesize; promote a candidate to a finding only if it survives a refute panel.

DOGFOODING (CLAUDE.md): every prep call is also a product test. Known live issue:
prep_search is biased toward planning .md files and missed code files on 2026-06-16
(team_config.py, is_safe_url) — prefer prep() role-view + prep_impact for code, grep
as the floor. Log misses as product findings (observation 04c21021b460 already filed).

Tell me which of D-1/D-2/D-3 you want to set, then I'll start Phase 1. Don't begin
the audit until I confirm.
```

---

## Quick state snapshot (for the human, not the prompt)

- **Done:** scaffolding (verified) — 7 docs in this directory, committed `b961879c`.
- **Not done:** the audit itself (Phases 1–8 in `STATUS.md` are all ⏳ PENDING).
- **Blocking:** decisions D-1/D-2/D-3 above (D-3 is the important one).
- **First move when resuming:** answer D-3, then run Phase 1 (Auth & Daemon Boundary).

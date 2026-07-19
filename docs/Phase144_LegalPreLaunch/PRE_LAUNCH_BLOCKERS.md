# OSS Launch Critical Blockers

> **DO NOT PUBLISH THE REPOSITORY UNTIL THESE ARE RESOLVED.**
> These items present direct legal, security, or acquisition risks if the repository goes public before they are addressed.

## 1. GPL Dependency Replacement (Critical Legal Blocker)
- **Status:** [x] Resolved 2026-06-10
- **Risk:** The Python backend used `igraph` (GPL) and `leidenalg` (GPL-3.0). GPL is "viral." Publishing SourcePrep under Apache 2.0 while importing GPL libraries would have violated the GPL and could have forced the entire project to be re-licensed as GPL.
- **Resolution:** Replaced Leiden community detection (`igraph` + `leidenalg`) with Louvain via `networkx` (BSD-3-Clause). Changes scoped to `src/prep/core/cluster.py`. `networkx>=3.0` added as a declared dependency in `pyproject.toml`. Both GPL libraries uninstalled from `.venv`. Regression guard added at `tests/test_no_gpl_deps.py` to prevent reintroduction. See `docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md` and `docs/superpowers/plans/2026-06-10-gpl-dependency-replacement.md`.

## 2. Live-Tree Secrets Removal (Critical Security Blocker)
- **Status:** [ ] Open
- **Decision (D8, 2026-07-18):** The history-rewrite question is **decided** —
  the public surface is a **fresh-initial-commit** mirror built by
  `tools/build_public_mirror.py` (allowlist curation + denylist-regex gate,
  see `DECISION_MEMO_2026-07-17.md` C2 / D1). The private dev repo at
  `/Volumes/4TB-BAD/HumanAI/CoDRAG/` keeps its full history and **never** goes
  public, so the old "git filter-repo / squash the existing history" framing is
  moot — there is no history to scrub *into* the public repo because the public
  repo starts from a clean initial commit assembled from a curated file
  allowlist. `git filter-repo` and history-squash are **removed** as action
  items (D1 reclassified them).
- **Risk (live-tree only):** The mirror allowlist can still include a file that
  contains a real secret — `codrag.key` is the known case (it is already on
  `origin`, but must still be excluded from the public tree). The denylist-regex
  gate (codrag, ACQUIRER, SCRUTINY, DISTRIBUTION_AND_REVENUE_PLAN, CLAUDE.md,
  .runprep, codrag.key, private-key markers, AUDIT_2026-07-17, HANDOFF_PROMPT,
  RESEARCH_ROUND_2) is the gate that catches this; the build fails on any hit.
- **Action Required (live-tree, not history):**
  - (a) **Remove live-tree secrets** from the curated allowlist — confirm
    `codrag.key` and any other private-key / token files are on the denylist and
    do not appear in the emitted mirror tree. Run `trufflehog` / `gitleaks` over
    the *emitted mirror tree* (not the dev repo history).
  - (b) **Verify-no-real-history-secrets (informational)** — the dev repo's
    full private history stays private and is never published; a historical
    secret in the dev repo is not a public exposure as long as the dev repo
    itself is never made public. Note for the record: `codrag.key` is already
    on `origin` (the private remote) — rotate it regardless, since the private
    remote's access list is wider than the public mirror will be.
- **Supersedes** the earlier "run a secret scanner over the history; use
  `git filter-repo` or squash into a clean Initial Commit" advice — that advice
  assumed the existing repo would be made public directly, which D8 reversed.

## 3. Formal IP Assignment (Acquisition Blocker)
- **Status:** [ ] Open
- **Risk:** For a clean "chain of title" during acquisition due diligence, the entity granting the open-source license (Magnetic Anomaly LLC) must legally own all the code. If Eric wrote the code personally before forming the LLC, or in his personal capacity, the LLC does not automatically own it.
- **Action Required:** Execute a formal Intellectual Property Assignment agreement transferring all rights in the SourcePrep/CoDRAG codebase from Eric (individual) to Magnetic Anomaly LLC. (See Phase 144, Question 3.2).

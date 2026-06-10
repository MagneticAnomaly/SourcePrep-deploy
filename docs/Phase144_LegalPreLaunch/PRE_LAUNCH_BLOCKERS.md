# OSS Launch Critical Blockers

> **DO NOT PUBLISH THE REPOSITORY UNTIL THESE ARE RESOLVED.**
> These items present direct legal, security, or acquisition risks if the repository goes public before they are addressed.

## 1. GPL Dependency Replacement (Critical Legal Blocker)
- **Status:** [x] Resolved 2026-06-10
- **Risk:** The Python backend used `igraph` (GPL) and `leidenalg` (GPL-3.0). GPL is "viral." Publishing SourcePrep under Apache 2.0 while importing GPL libraries would have violated the GPL and could have forced the entire project to be re-licensed as GPL.
- **Resolution:** Replaced Leiden community detection (`igraph` + `leidenalg`) with Louvain via `networkx` (BSD-3-Clause). Changes scoped to `src/prep/core/cluster.py`. `networkx>=3.0` added as a declared dependency in `pyproject.toml`. Both GPL libraries uninstalled from `.venv`. Regression guard added at `tests/test_no_gpl_deps.py` to prevent reintroduction. See `docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md` and `docs/superpowers/plans/2026-06-10-gpl-dependency-replacement.md`.

## 2. Git History Scrubbing (Critical Security Blocker)
- **Status:** [ ] Open
- **Risk:** Making a private repository public exposes its entire commit history. Any API keys, AWS secrets, Lemon Squeezy tokens, or private internal notes ever committed—even if later deleted—will be visible and immediately scraped by bots.
- **Action Required:** Execute Part A of `Phase142_OSS-First/IMPLEMENTATION_PLAN.md`. Run a secret scanner (e.g., `trufflehog`) over the history. Either use `git filter-repo` to strip sensitive data or squash the entire history into a clean "Initial Commit."

## 3. Formal IP Assignment (Acquisition Blocker)
- **Status:** [ ] Open
- **Risk:** For a clean "chain of title" during acquisition due diligence, the entity granting the open-source license (Magnetic Anomaly LLC) must legally own all the code. If Eric wrote the code personally before forming the LLC, or in his personal capacity, the LLC does not automatically own it.
- **Action Required:** Execute a formal Intellectual Property Assignment agreement transferring all rights in the SourcePrep/CoDRAG codebase from Eric (individual) to Magnetic Anomaly LLC. (See Phase 144, Question 3.2).

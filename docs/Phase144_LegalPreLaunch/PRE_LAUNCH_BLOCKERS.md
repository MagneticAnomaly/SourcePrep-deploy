# OSS Launch Critical Blockers

> **DO NOT PUBLISH THE REPOSITORY UNTIL THESE ARE RESOLVED.**
> These items present direct legal, security, or acquisition risks if the repository goes public before they are addressed.

## 1. GPL Dependency Replacement (Critical Legal Blocker)
- **Status:** [ ] Open
- **Risk:** The Python backend currently relies on `igraph` (GPL) and `leidenalg` (GPL-3.0). GPL is "viral." Publishing SourcePrep under Apache 2.0 while importing GPL libraries violates the GPL and could force the entire project to be re-licensed as GPL, severely harming enterprise adoption and acquisition potential.
- **Action Required:** Replace `igraph` and `leidenalg` (used for community detection in the graph) with Apache/MIT-compatible alternatives. `networkx` or a pure-Python Louvain implementation are recommended replacements.

## 2. Git History Scrubbing (Critical Security Blocker)
- **Status:** [ ] Open
- **Risk:** Making a private repository public exposes its entire commit history. Any API keys, AWS secrets, Lemon Squeezy tokens, or private internal notes ever committed—even if later deleted—will be visible and immediately scraped by bots.
- **Action Required:** Execute Part A of `Phase142_OSS-First/IMPLEMENTATION_PLAN.md`. Run a secret scanner (e.g., `trufflehog`) over the history. Either use `git filter-repo` to strip sensitive data or squash the entire history into a clean "Initial Commit."

## 3. Formal IP Assignment (Acquisition Blocker)
- **Status:** [ ] Open
- **Risk:** For a clean "chain of title" during acquisition due diligence, the entity granting the open-source license (Magnetic Anomaly LLC) must legally own all the code. If Eric wrote the code personally before forming the LLC, or in his personal capacity, the LLC does not automatically own it.
- **Action Required:** Execute a formal Intellectual Property Assignment agreement transferring all rights in the SourcePrep/CoDRAG codebase from Eric (individual) to Magnetic Anomaly LLC. (See Phase 144, Question 3.2).

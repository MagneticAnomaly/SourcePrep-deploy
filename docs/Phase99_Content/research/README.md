# Phase 99 — Research Sources

This folder inventories the external research, open-source projects, papers, and standards that Prep has drawn on during development. It is a **working bibliography**, not a literature review — each entry links back to the phase doc where it was originally cited and notes, in one or two sentences, how Prep actually used it.

## Why this exists

Prep's architecture synthesizes a lot of prior work: code-retrieval papers, chunking/compression techniques, RAG research, traceability standards, security tooling, competitor implementations, and protocol specs. Those citations live scattered across ~15 phase folders. This file consolidates them so that:

1. Credit can be given cleanly when writing blog posts, the whitepaper, investor decks, or the site.
2. Decisions can be re-traced back to the paper/repo that justified them.
3. New research can be slotted in without re-walking the entire docs tree.

## Files in this folder

- [`00_Research_Sources_Master_List.md`](./00_Research_Sources_Master_List.md) — the main list, grouped by source type (arXiv, academic, GitHub, whitepapers, standards).

## Scope note

- **Included:** external sources (repos, papers, blogs, standards) that shaped a design decision, were benchmarked against, or were evaluated as alternatives.
- **Excluded:** Prep's own repos and issue trackers, `package-lock.json` transitive deps, GitHub sponsor URLs, and competitor pricing pages cited purely for $/seat data.
- Citations are preserved as the phase docs present them. A handful of arXiv IDs encode post-2025 years — those are kept verbatim; verify before citing in public-facing material.

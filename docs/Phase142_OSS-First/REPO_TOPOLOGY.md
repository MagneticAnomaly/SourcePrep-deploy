# Repo Topology — private workshop → public storefront (DECIDED 2026-07-17)

> **Status:** DECIDED. Captures how the private working repo and the public OSS
> repo relate, so the plan is unambiguous. PRIVATE — Phase 143 keep-private bucket.

## The decision in one line
Keep everything under the **`MagneticAnomaly`** GitHub org. Develop privately in a
**workshop** repo; publish a curated one-way **mirror** to a public **storefront**
repo. The workshop is never a relic — it stays the active dev repo forever.

## The two repos

**Workshop (private, active forever).**
- Today: `github.com/MagneticAnomaly/SourcePrep` — the local checkout at
  `/Volumes/4TB-BAD/HumanAI/CoDRAG`.
- Holds **everything**: Rust engine, Python daemon, TS dashboard, Tauri app,
  marketing sites, docs source, the future closed hosted backend, and all
  strategy/planning/security IP. Full 1600+ commit history stays here, private.
- At publish time it is **renamed** to `MagneticAnomaly/SourcePrep-Private` so the
  clean `SourcePrep` name is free for the storefront. Same repo, same history —
  only the name/URL changes. **Not archived, not a relic** — day-to-day work
  continues here.

**Storefront (public, a published artifact).**
- `github.com/MagneticAnomaly/SourcePrep` — a **new, separate** repo.
- Contains only the cleaned-up OSS subset: engine, CLI, daemon, MCP server,
  dashboard, public docs, `LICENSE`/`NOTICE`/`README`/`CONTRIBUTING`, ADRs,
  `HISTORY.md`. **None** of the strategy, hosted-backend, or planning docs.
- Built by the `tools/build_public_mirror.py` allowlist tool as a **fresh single
  initial commit** (no private history). Development does **not** happen here
  day-to-day; you publish curated releases to it.

## The flow (one-way)
`workshop  →  (curate via mirror tool)  →  storefront`

Nothing flows storefront → workshop automatically. If a community member opens a
PR on the public repo, you decide whether to bring it back into the workshop; it
then flows out again in the next curated push (credit the author in the commit).
Public history = clean curated releases, not a raw log.

## What NOT to do
- ❌ Do **not** develop the whole product in the open — the workshop has IP that
  can never be public.
- ❌ Do **not** flip the private repo to public (destroys the ability to curate,
  exposes Actions logs, can't be undone cleanly).
- ❌ Do **not** stand up a separate `sourceprep` org yet — deferred to a possible
  future C-corp/VC path (optionally grab & sit on `github.com/sourceprep`).
- ❌ Do **not** keep the `SourcePrep-MCP` stub — 0 stars/forks/listings; archive it
  with a README pointer. (MCP discovery comes from a registry `server.json` +
  published package + claiming Glama/PulseMCP listings, not a stub repo.)

## Safe flip sequence (execute at publish time, not before)
Nothing needs to change today. When license is decided + the mirror tool is built
+ docs are curated:

1. **Rename** `MagneticAnomaly/SourcePrep` → `MagneticAnomaly/SourcePrep-Private`.
2. **Immediately repoint the local remote** from `/Volumes/4TB-BAD/HumanAI/CoDRAG`:
   `git remote set-url origin git@github.com:MagneticAnomaly/SourcePrep-Private.git`.
3. **Create** the new public repo `MagneticAnomaly/SourcePrep` (private at first;
   make public only at the launch moment).
4. **Push** the curated mirror as the clean initial commit.
5. **Archive** `MagneticAnomaly/SourcePrep-MCP` (README pointer to the new repo).

### The one footgun (why step 2 is mandatory, and mandatory *before* step 3)
GitHub keeps a redirect from a renamed repo's old URL — but that redirect **dies
the instant a new repo occupies the old name** (step 3). If your local `origin`
still points at `…/SourcePrep.git` when step 3 runs, it will then resolve to the
**public** repo, and a habitual `git push` could shove private history + secrets
into public. Repointing in step 2 closes that hole. (Confirmed against GitHub Docs
on renaming/redirects, 2026-07-17.)

## Downstream ripples
- The marketing/docs sites currently link to `MagneticAnomaly/SourcePrep-MCP` in a
  few places (`ClientLayout.tsx`, docs) — those URLs update to the storefront as
  part of the marketing team's OSS pass.
- Package/registry names (PyPI `prep`, the MCP registry `io.github.<user>/…`
  namespace) are independent of the repo name and coordinated separately.

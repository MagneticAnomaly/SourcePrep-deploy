# Contributing to SourcePrep

SourcePrep is a local-first codebase intelligence MCP server. Thanks for
considering contributing — every contribution is read.

> **Status:** DRAFT for legal-trigger review (Phase 144, item D8). The
> DCO mechanics and security reporting contact below are final in shape;
> the project lead (Eric Bintner, Magnetic Anomaly LLC) signs off before
> the public mirror push.

## Project shape

SourcePrep is a three-language monorepo:

- **Python backend** (`src/prep/`) — the daemon, MCP server, CLI, core engine
- **Rust engine** (`engine/crates/`) — parsing, graph, chunking, called via maturin
- **TypeScript frontends** (`packages/`, `src/prep/dashboard/`, `websites/`) — UI, VS Code extension, docs/marketing

See `CLAUDE.md` and `AGENTS.md` for the full build/test commands. The short
version for a fresh clone:

```bash
# Python
pip install -e ".[dev]"
pytest tests/ -v

# Rust
cd engine && cargo build --release && cargo test

# Frontend (Node 20)
npm install
npm run typecheck
npm run lint
```

## Developer Certificate of Origin (DCO)

SourcePrep uses the **Developer Certificate of Origin** — a lightweight
per-commit sign-off, **not** a Contributor License Agreement. No rights are
assigned to the project; you keep your own copyright.

Every commit must be signed off:

```bash
git commit -s -m "your message"
```

This adds a `Signed-off-by: Your Name <you@example.com>` trailer, certifying:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that (a) the
contribution was created in whole or in part by me and I have the right
to submit it under the open source license indicated in the file; or
(b) the contribution is based upon previous work that, to the best of
of my knowledge, is covered under an appropriate open source license and
I have the right under that license to submit that work with
modifications, whether created in whole or in part by me, under the same
open source license (unless I am permitted to submit under a different
license), as indicated in the file; or (c) the contribution was provided
directly to me by some other person who certified (a), (b) or (c) and I
have not modified it.

I certify that the contribution was authored in the format in which I
submit it, and that I am providing the contribution under the terms of
the license for the project as well as the conditions stated above.
```

Commits must include a `Signed-off-by` trailer (`git commit -s`).
A DCO check will be wired to CI before the public mirror push; until then,
missing sign-off is caught at review.

## License

SourcePrep is licensed under **Apache License 2.0** — see `LICENSE`.
New source files should carry an SPDX identifier:

```
# SPDX-License-Identifier: Apache-2.0
```

Do **not** mass-rewrite existing files to add headers (cosmetic-only diffs
are noise); add the identifier to new files going forward.

## Before you open a pull request

- **Discuss architectural changes first.** Open an issue describing what
  you intend to change before writing code for anything beyond a small
  fix. This saves wasted work.
- **Run the full test suite** and keep it green. CI reruns it, but local
  first is faster.
- **One concern per PR.** A PR that fixes a bug, adds a feature, and
  reformats unrelated code is hard to review and slow to land.
- **Sign off every commit** (`-s`).

## Maintenance reality

SourcePrep is currently maintained by **a single developer**. Response
times may vary. This is stated plainly so contributors can plan around it:

- Bug reports: read and triaged as time allows; security reports get
  priority (see `SECURITY.md`).
- PRs: reviewed in order received; larger PRs take longer.
- Major architectural changes: discussed in an issue first; expect
  iteration before merge.

Good first issues are labeled `good first issue`. Please don't open
drive-by "fix typo" PRs on prose — they cost review time without adding
value. Real typo fixes in code/comments are welcome.

## Code of conduct

Participation in this project is governed by `CODE_OF_CONDUCT.md`. By
participating you agree to abide by its terms.
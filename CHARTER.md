# SourcePrep Charter

> **Status:** DRAFT for legal-trigger review (Phase 144, item D8). This
> charter records the licensing and scope commitments the project makes
> to its users. It is the anti-rug-pull trust signal: the license story
> will not change out from under you.

## Purpose

SourcePrep is a local-first codebase intelligence MCP server. It builds
persistent semantic and structural indexes of a codebase and serves
bounded, source-cited context to AI coding agents via the Model Context
Protocol. The engine, CLI, daemon, MCP server, local dashboard, VS Code
extension, and AGENTS.md generator are the open-source product.

## Licensing commitment (permanent)

- The **engine OSS surface** ships under the **Apache License 2.0** and
  will remain Apache-2.0 **permanently**. There is no AGPL fallback and
  no plan to relicense the OSS surface to a more restrictive license.
- Contributions are accepted under the **Developer Certificate of
  Origin** (`Signed-off-by`), not a Contributor License Agreement. No
  contributor assigns rights to the project; each contributor retains
  their own copyright. The tradeoff is accepted deliberately: with DCO
  and no CLA, a later relicense would require every contributor's
  agreement, which is effectively impossible — that is the point. The
  "we will never take this back" signal is the value.

## What is open source and what is not

- **Open source (Apache-2.0, in this repo):** the Rust engine, the
  Python core/CLI/daemon, the MCP server, the local single-user
  dashboard, the VS Code extension, the AGENTS.md generator, all
  prompts in the OSS surface, and the public documentation.
- **Proprietary (separate codebase, never published):** the hosted
  multi-tenant backend (org-shared indexes, SSO, RBAC, audit log
  storage), the Tauri signing / notarization / auto-update server, and
  the license-key infrastructure. These are the convenience and
  infrastructure surface of the paid tiers (Pro / Teams / Enterprise).

This is the standard open-core boundary (GitLab CE/EE, Sentry OSS/SaaS,
Mattermost). The OSS surface is the full single-user product; the
proprietary surface is multi-tenant infrastructure and distribution
polish that an OSS user cannot replicate by reading the source.

## No "source-available" flip

The project commits that the **OSS surface will not become
source-available** (readable-but-restricted) in the future. The Apache-2.0
grant on what ships to the public repo is permanent. If the project ever
introduces a paid-only capability, it will be **new proprietary code in the
separate backend repo** — never a reclassification of code that was
previously published under Apache-2.0.

## No capability paywalls in the engine

Algorithms, prompts, indexing methods, and any in-engine capability that
ships in the public repo are **never gated behind a paid tier**. Paid
tiers gate distribution (signed installer, auto-update), multi-tenant
infrastructure (hosted indexes, SSO, RBAC), and support — never engine
capability. Gating engine capability would imply the OSS is
feature-limited, which contradicts the open-core boundary above.

## Trademark

"SourcePrep"™ and the SourcePrep logo are trademarks of Magnetic Anomaly
LLC, claimed under common law pending federal registration. The Apache-2.0
license grants no trademark rights; use of the name "SourcePrep" or the
logo to endorse or promote derivative works, or to suggest endorsement by
or affiliation with Magnetic Anomaly LLC, is not permitted without written
permission. Forks are welcome and encouraged; please choose a distinct
name that does not incorporate "SourcePrep." See the `NOTICE` file and the
project Terms of Service for the full trademark notice, or contact
legal@sourceprep.io.

## Governance

SourcePrep is maintained by Magnetic Anomaly LLC (Eric Bintner). See
`CONTRIBUTING.md` for the contribution process and the maintenance-reality
note.
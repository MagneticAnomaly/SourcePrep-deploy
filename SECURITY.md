# Security Policy

> **Status:** DRAFT for legal-trigger review (Phase 144, item D8). The
> reporting contact and disclosure window below are final in shape;
> confirm `security@sourceprep.io` is live before the public mirror push.

## Reporting a vulnerability

If you believe you have found a security vulnerability in SourcePrep,
please report it privately — **do not open a public GitHub issue.**

Email: **security@sourceprep.io** (with "Security" in the subject).

Please include:

- A description of the issue and its potential impact
- Steps to reproduce, or a proof-of-concept
- The SourcePrep version / commit you tested against
- Whether you have a proposed fix (optional — not required)

## Response timeline

- **Acknowledgement:** within **5 business days** of the report.
- **Initial assessment:** within **14 days**, with a read on severity and a
  proposed path (fix, mitigation, or rationale if not treated as a
  vulnerability).
- **Coordinated disclosure:** we default to a **90-day** disclosure window
  and will publish an advisory + credit (if desired) once a fix is
  available. We will not publish details before a fix is shipped unless
  you are content for us to do so. We are happy to extend the window if
  the fix needs longer.

## Scope

In scope:

- Vulnerabilities in the SourcePrep engine, daemon, MCP server, CLI,
  dashboard, and VS Code extension that could lead to code execution,
  data exposure, denial of service, or license/auth bypass.
- Vulnerabilities in the build/release pipeline that could lead to a
  compromised published artifact.

Out of scope:

- Vulnerabilities in third-party dependencies not reachable through
  SourcePrep's own code (report those upstream).
- "SourcePrep reads files from my repo" — this is the product's intended
  behavior. SourcePrep indexes source code on the local machine; users
  should review the integration before running it on repositories
  containing sensitive content. The local daemon does not upload source
  to any remote service.
- Findings from automated scanners without a demonstrated impact.

## Supported versions

SourcePrep is pre-1.0 and maintained by a single developer. Only the
**latest published release** receives security fixes. Users should run
the most recent release.

| Version | Supported |
|---|---|
| latest release | ✅ |
| anything older | ❌ (upgrade) |

## Acknowledgements

We credit reporters in published advisories unless they prefer to
remain anonymous. Thank you for helping keep SourcePrep and its users
safe.
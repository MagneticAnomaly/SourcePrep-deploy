# Opportunities — Phase 06 (Team & Enterprise)

## Purpose
Track opportunities that make team adoption smooth without compromising the local-first posture.

## Opportunities
- **Hierarchical config merging**: global → team → project overrides, while keeping shared configs secret-free.
- **Policy packs**: ship curated ignore + safety defaults for common stacks; org can enforce via team config.
- **Operational modes**: “embedded committed index” vs “local-only index” vs future server mode; ensure `.codrag/**` loop avoidance stays bulletproof.

## Opportunities (dashboard tools + settings)
- **Config provenance UI**: for every relevant setting, show where it came from:
  - default
  - global
  - team policy
  - project override
- **Policy compliance checks**:
  - warn if a project config violates team policy (e.g., attempts to include disallowed paths)
  - show “effective config” that will be used for builds
- **Embedded index status UX**:
  - “using committed index” vs “index missing” vs “index incompatible” vs “index has merge conflicts; rebuild required”
  - one-click rebuild (and clear warning about repo bloat if committing)
- **Network-mode safety UX (post-MVP implementation)**:
  - persistent “Remote mode” indicator
  - “auth required” status and clear error shapes (unauthorized vs connectivity)

## Opportunities (meaningful visualization)
- **Team consistency view** (post-MVP implementation): show whether multiple clients are using the same:
  - config hash
  - index `format_version`
  - embedding model
- **Index portability indicators**: show index size and “commit impact” for embedded mode (helps teams decide commit vs rebuild).

## Hazards
- **Security foot-guns**: remote binding without auth (or unclear UI indicators) is catastrophic for trust.
- **Config drift across teammates**: if settings aren’t reproducible and visible, team results diverge and adoption stalls.
- **Repo bloat / merge conflict pain**: committed indexes can explode repo size and create frequent conflicts; UX must treat indexes as rebuildable artifacts.
- **Path leakage in remote mode**: project paths must not be surfaced to remote clients; errors must be redacted.
- **Watcher loops in embedded mode**: `.codrag/**` must always be excluded from watchers and rebuild triggers.

## References
- `TEAM_TIER_TECHNICAL_SPEC.md`
- ChunkHound issue #161 (demand for hierarchical config + richer provider config)
- `docs/Phase06_Team_And_Enterprise/README.md`
- `docs/WORKFLOW_RESEARCH.md` (enterprise case studies)

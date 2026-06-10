# GPL Dependency Replacement — Leiden → Louvain

**Date:** 2026-06-08
**Status:** Design approved; ready for implementation plan
**Phase:** 144 (Legal Pre-Launch) — Blocker #1
**Related:** `docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md`

## Problem

SourcePrep is scheduled to ship under Apache 2.0 (Phase 142). The Python
backend currently uses `igraph` (GPL-2.0) and `leidenalg` (GPL-3.0-or-later)
for community detection in `src/prep/core/cluster.py`. GPL is copyleft;
publishing Apache 2.0 source that imports GPL libraries creates a license
incompatibility that, on a conservative read, could force the whole
project to GPL — severely harming enterprise adoption and acquisition
potential.

Discovered scope is narrower than the blocker doc states:

- The two libraries are imported at three sites in one file
  (`src/prep/core/cluster.py` lines 631–632, 668–669, 979–980).
- Neither is declared in `pyproject.toml` — they were installed ad-hoc
  into `.venv`.
- The code already has a runtime feature-detection check
  (`_leiden_available()` at line 628) with a non-Leiden fallback.

## Goals

1. Remove all runtime use of `igraph` and `leidenalg`.
2. Preserve the public API of `cluster.py` (callers unchanged).
3. Add a guard so the GPL deps cannot silently return.
4. Preserve clustering quality at the scales this project sees
   (file graphs <2000 nodes per layer).

## Non-goals

- Refactoring `cluster.py` beyond the swap.
- Changing the `pyproject.toml` `license = "MIT"` field (that is a
  Phase 142 / Phase 144 license-application task, not this one).
- Performance optimization.
- Adding GPL detection across other dependencies (Phase 144 Part H).

## Approach

Replace Leiden (via `leidenalg` + `igraph`) with **Louvain via
`networkx.algorithms.community.louvain_communities`**.

Rationale:

- `networkx` is BSD-3-Clause (Apache-compatible) and is already
  installed at 3.6.1 as a transitive dep.
- Louvain is Leiden's predecessor. The known quality gap (Leiden
  guarantees connected communities; Louvain does not) is negligible
  at our scale: per-layer graphs of a few hundred to ~2000 nodes
  with reasonable edge density.
- Alternative considered: `graspologic` (Apache 2.0, Microsoft;
  includes a genuine Leiden implementation). Rejected because it
  pulls in scipy/sklearn, materially expanding install weight for
  a marginal algorithmic difference at our scale.
- Alternative considered: drop the algorithmic path entirely and
  lean on the existing tag-based + connected-components fallback.
  Rejected because the quality regression is meaningful and the
  Louvain swap is cheap.

## Components

### 1. `src/prep/core/cluster.py`

| Change | Location |
|---|---|
| Add `import networkx as nx` at module top | imports block |
| Delete `_leiden_available()` | line 628 |
| Delete fallback-to-`build_clusters` branch on missing lib | line 661 |
| Replace `import igraph as ig` + `import leidenalg` | line 668 |
| Replace `g = ig.Graph(n=n, directed=False)` + `g.add_edges(...)` + `g.es["weight"] = ...` with `nx.Graph()` + `g.add_nodes_from(range(n))` (preserves isolated nodes — `igraph.Graph(n=n)` did this implicitly) + `g.add_weighted_edges_from([(i, j, w) for (i, j), w in zip(sorted_edges, weights)])` | inside `build_clusters_leiden` |
| Replace `leidenalg.find_partition(g, leidenalg.RBConfigurationVertexPartition, weights="weight", resolution_parameter=resolution, n_iterations=-1)` with `nx.algorithms.community.louvain_communities(g, weight="weight", resolution=resolution, seed=42)` | line 783 |
| Adjust partition iteration to consume `list[set[int]]` instead of leidenalg partition | line 807 |
| Same swap in `build_clusters_structural` | lines 979–994 |
| Update module docstring to mention Louvain + GPL-avoidance rationale | top of file |

Function signatures unchanged. The try/except around the partition
call stays as a defensive fallback.

### 2. `pyproject.toml`

Add `"networkx>=3.0"` to the `dependencies` array. networkx becomes
an explicit runtime dependency rather than a transitive one.

### 3. `tests/test_no_gpl_deps.py` (new)

Asserts `igraph` and `leidenalg` are NOT importable. Fails loudly
if either gets reinstalled.

```python
import importlib
import pytest

@pytest.mark.parametrize("modname", ["igraph", "leidenalg"])
def test_gpl_dep_not_installed(modname):
    with pytest.raises(ImportError):
        importlib.import_module(modname)
```

### 4. `tests/test_cluster_louvain.py` (new)

Sanity test for `build_clusters_leiden` (which is now Louvain
internally): build a 6-file graph with two obvious dense communities
and a sparse bridge edge, assert two distinct clusters emerge with
the right files in each.

### 5. Documentation

- `docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md` — flip
  blocker #1 to ✅ Resolved with one-line rationale + date.
- `cluster.py` module docstring — note the swap.

## Data flow

Identical to today. The graph is built from the same edge dict
(`edge_pairs: Dict[Tuple[int, int], float]`), partitioned, then
the partition is consumed identically (each community becomes a
`Cluster` with majority-vote primary tag and layer suffix).

The only observable difference is the algorithm choice; for the
same input graph, Louvain and Leiden may produce slightly different
partitions in edge cases (Louvain can theoretically produce a
disconnected community, Leiden cannot). At our graph sizes this
is rarely material.

## Error handling

- **Library missing:** Cannot happen post-change — networkx is a
  declared hard dep. The `_leiden_available()` check is deleted.
- **Algorithm failure:** Preserved. The existing `try/except` around
  the partition call falls back to "each node is its own cluster"
  for that layer (line 793).
- **Empty graph / single node:** Preserved by existing guards
  (lines 676, 700, 768).

## Testing

| Test | Purpose |
|---|---|
| `tests/test_cluster.py` (existing) | Tag-based path — must still pass, unchanged |
| `tests/test_cluster_swarm.py` (existing) | Mocks `build_clusters` — unaffected |
| `tests/test_cluster_louvain.py` (new) | Sanity check on the swapped algorithm |
| `tests/test_no_gpl_deps.py` (new) | Import guard against re-contamination |

Full suite: `.venv/bin/pytest tests/ -v` — must stay green.

Manual dogfooding: after restart, run prep on this repo and verify
clusters look sensible via `prep` MCP tool (CLAUDE.md per-task
practice).

## Implementation in a worktree

Per user preference, this change ships in an isolated git worktree:

1. Create worktree (`superpowers:using-git-worktrees` skill).
2. Make changes + tests there.
3. Run full pytest suite + manual daemon dogfood.
4. Merge back only after verification passes.

## Risks

| Risk | Mitigation |
|---|---|
| Louvain produces lower-quality clusters in some edge case | Sanity test asserts the obvious-community case; manual dogfood verifies real repo output |
| networkx Louvain API changes between minor versions | Pin `>=3.0`; networkx Louvain has been stable since 2.7 |
| Removal of igraph/leidenalg breaks an unrelated import path we missed | Full test suite + repo-wide grep already shows only `cluster.py` uses them |
| Someone later adds back igraph for an unrelated feature | `tests/test_no_gpl_deps.py` catches it in CI |

## Acceptance criteria

1. `grep -rn "import igraph\|import leidenalg" --include='*.py' src/` returns nothing.
2. `pip uninstall igraph leidenalg python-igraph -y` succeeds (libraries removed from `.venv`).
3. `pip install -e .` installs networkx as a declared dep.
4. `pytest tests/ -v` is green.
5. `pytest tests/test_no_gpl_deps.py -v` passes — proves the guard works.
6. Manual: daemon restart + clustering run produces sensible clusters on the SourcePrep repo itself (visible via `prep` MCP).
7. `PRE_LAUNCH_BLOCKERS.md` blocker #1 marked Resolved with date and rationale.

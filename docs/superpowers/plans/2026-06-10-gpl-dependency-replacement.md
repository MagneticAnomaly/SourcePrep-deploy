# GPL Dependency Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace GPL-licensed `igraph` + `leidenalg` with BSD-licensed `networkx` (Louvain community detection) so SourcePrep can publish cleanly under Apache 2.0 (Phase 144 blocker #1).

**Architecture:** Swap the algorithm internals in `src/prep/core/cluster.py` (the only file using these libs). Preserve the public API — both modified functions (`build_clusters_leiden`, `build_clusters_structural`) keep their signatures so callers are unaffected. Add an import-guard regression test so the GPL deps can't return. Declare `networkx` as an explicit dep.

**Tech Stack:** Python 3.11, `networkx>=3.0` (BSD-3-Clause), pytest.

**Spec:** `docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md`

**Pre-work fact:** A repo-wide grep shows `build_clusters_leiden` and `build_clusters_structural` have **no external callers** today — only their own definitions. The legal fix is the priority; functionally these are dormant code paths. We swap them anyway to preserve the public API for future use and so the new tests have something real to exercise.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/prep/core/cluster.py` | Modify | Replace Leiden internals with Louvain; delete `_leiden_available()`; update module docstring |
| `pyproject.toml` | Modify | Add `networkx>=3.0` to `dependencies` |
| `tests/test_cluster_louvain.py` | Create | Sanity test for Louvain-backed `build_clusters_leiden` |
| `tests/test_no_gpl_deps.py` | Create | Import-guard regression test |
| `docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md` | Modify | Flip blocker #1 to ✅ Resolved with date |

---

## Task 1: Create isolated worktree

**Why:** Per user preference, all work happens in a git worktree so `main` stays clean until verification passes.

- [ ] **Step 1: Create the worktree**

Run from the main repo (`/Volumes/4TB-BAD/HumanAI/CoDRAG`):

```bash
git worktree add -b fix/gpl-dep-replacement ../CoDRAG-gpl-fix main
```

Expected: `Preparing worktree (new branch 'fix/gpl-dep-replacement')` and a new directory at `../CoDRAG-gpl-fix`.

- [ ] **Step 2: Verify the worktree**

```bash
cd ../CoDRAG-gpl-fix && git status && git branch --show-current
```

Expected: clean tree, branch `fix/gpl-dep-replacement`.

- [ ] **Step 3: Create venv symlink for shared environment**

The project venv lives at `/Volumes/4TB-BAD/HumanAI/CoDRAG/.venv`. To use the same Python env from the worktree without reinstalling:

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG-gpl-fix
ln -s /Volumes/4TB-BAD/HumanAI/CoDRAG/.venv .venv
```

Expected: `.venv` symlink present.

**All subsequent tasks run from `/Volumes/4TB-BAD/HumanAI/CoDRAG-gpl-fix`.**

---

## Task 2: Add networkx as a declared dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add networkx to dependencies**

In `pyproject.toml`, after the `"cryptography>=42.0.0",` line (currently line 48 of the `dependencies` array), add:

```toml
    "networkx>=3.0",
```

Final dependencies block should end with:

```toml
    "cryptography>=42.0.0",
    "networkx>=3.0",
]
```

- [ ] **Step 2: Reinstall the package**

```bash
.venv/bin/pip install -e .
```

Expected: networkx already at 3.6.1, no version change; package re-registered.

- [ ] **Step 3: Verify networkx is importable and the louvain API exists**

```bash
.venv/bin/python -c "from networkx.algorithms.community import louvain_communities; print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: declare networkx>=3.0 explicitly (was transitive)"
```

---

## Task 3: Write Louvain sanity test (passes against current Leiden — baseline)

**Why TDD this way:** The same behavioral test should pass before AND after the swap. Writing it first against the current Leiden implementation gives us a baseline; running it after the swap proves no regression.

**Files:**
- Create: `tests/test_cluster_louvain.py`

- [ ] **Step 1: Write the test**

Create `tests/test_cluster_louvain.py`:

```python
"""Sanity tests for build_clusters_leiden after Leiden→Louvain swap.

The test asserts behavioral parity: a graph with two obvious dense
communities and one weak bridge edge must produce at least two
distinct clusters. The exact algorithm (Leiden or Louvain) is an
implementation detail; this test must pass with either.
"""
from prep.core.cluster import build_clusters_leiden
from prep.core.cluster import EpistemicEntry


def _entry(node_id: str, tags: list[str]) -> EpistemicEntry:
    return EpistemicEntry(
        node_id=node_id,
        domain_tags=tags,
        responsibility="",
        contracts=[],
        invariants=[],
        intent="",
    )


def test_two_obvious_communities_separate():
    # Two dense triangles connected by one weak bridge edge.
    # Community A: files a1, a2, a3 (dense interconnects, weight 1.0)
    # Community B: files b1, b2, b3 (dense interconnects, weight 1.0)
    # Bridge: a1 ↔ b1 with weight 0.1
    files_a = [f"file:src/a{i}.py" for i in (1, 2, 3)]
    files_b = [f"file:src/b{i}.py" for i in (1, 2, 3)]
    all_files = files_a + files_b

    entries = {f: _entry(f, ["impl"]) for f in all_files}

    def edge(src: str, tgt: str, conf: float) -> dict:
        return {
            "source": src,
            "target": tgt,
            "kind": "imports",
            "metadata": {"confidence": conf},
        }

    edges = []
    # Dense within A
    for i, src in enumerate(files_a):
        for tgt in files_a[i + 1:]:
            edges.append(edge(src, tgt, 1.0))
    # Dense within B
    for i, src in enumerate(files_b):
        for tgt in files_b[i + 1:]:
            edges.append(edge(src, tgt, 1.0))
    # Weak bridge
    edges.append(edge(files_a[0], files_b[0], 0.1))

    clusters = build_clusters_leiden(
        entries,
        edges,
        min_cluster_size=1,
        resolution=1.0,
    )

    # Expect at least two clusters; the A-files should not all share a
    # cluster with the B-files.
    assert len(clusters) >= 2, f"expected ≥2 clusters, got {len(clusters)}"

    # Find which cluster each file landed in
    file_to_cluster = {}
    for c in clusters:
        for nid in c.member_node_ids:
            file_to_cluster[nid] = c.cluster_id

    a_clusters = {file_to_cluster[f] for f in files_a if f in file_to_cluster}
    b_clusters = {file_to_cluster[f] for f in files_b if f in file_to_cluster}

    # Community A and B should not be the same single cluster
    assert a_clusters != b_clusters or len(a_clusters | b_clusters) >= 2, \
        f"A and B collapsed into the same cluster: A={a_clusters}, B={b_clusters}"
```

- [ ] **Step 2: Verify EpistemicEntry shape**

Quick sanity check that the `EpistemicEntry` constructor matches what the test passes:

```bash
.venv/bin/python -c "from prep.core.cluster import EpistemicEntry; import dataclasses; print([f.name for f in dataclasses.fields(EpistemicEntry)])"
```

Expected: a list including `node_id`, `domain_tags`, `responsibility`, `contracts`, `invariants`, `intent`. If field names differ, update the `_entry` helper in the test to match.

- [ ] **Step 3: Run the test against current (Leiden) implementation**

```bash
.venv/bin/pytest tests/test_cluster_louvain.py -v
```

Expected: PASS. This establishes the baseline — the same test must still pass after the swap.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cluster_louvain.py
git commit -m "test(cluster): sanity test for community detection (baseline)"
```

---

## Task 4: Replace Leiden with Louvain in `build_clusters_leiden`

**Files:**
- Modify: `src/prep/core/cluster.py`

- [ ] **Step 1: Add networkx import at module top**

In `src/prep/core/cluster.py`, after the existing `from typing import ...` line (currently line 32), add:

```python
import networkx as nx
```

- [ ] **Step 2: Replace the igraph+leidenalg block in `build_clusters_leiden`**

Find this block in `build_clusters_leiden` (currently around lines 661–669):

```python
    if not _leiden_available():
        logger.info("CL-1: igraph/leidenalg not available, falling back to tag-based clustering")
        return build_clusters(
            epistemic_entries, edges, min_cluster_size,
            max_cluster_fraction, max_cluster_abs,
        )

    import igraph as ig
    import leidenalg
```

Replace with (delete the fallback branch entirely — networkx is now a hard dep, and the module-level import handles availability):

```python
    # Louvain via networkx (BSD-3-Clause). Previously Leiden via
    # igraph+leidenalg (GPL); swapped 2026-06-10 to clear Phase 144
    # blocker #1. See docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md
```

- [ ] **Step 3: Replace igraph Graph construction**

Find this block in `build_clusters_leiden` (currently around lines 762–767):

```python
        # Build igraph Graph
        g = ig.Graph(n=n, directed=False)
        if edge_pairs:
            sorted_edges = sorted(edge_pairs.keys())
            weights = [edge_pairs[e] for e in sorted_edges]
            g.add_edges(sorted_edges)
            g.es["weight"] = weights
        else:
```

Replace with:

```python
        # Build networkx Graph. add_nodes_from preserves isolated
        # nodes (igraph.Graph(n=n) did this implicitly).
        g = nx.Graph()
        g.add_nodes_from(range(n))
        if edge_pairs:
            sorted_edges = sorted(edge_pairs.keys())
            weights = [edge_pairs[e] for e in sorted_edges]
            g.add_weighted_edges_from(
                [(i, j, w) for (i, j), w in zip(sorted_edges, weights)]
            )
        else:
```

- [ ] **Step 4: Replace the Leiden partition call**

Find this block in `build_clusters_leiden` (currently around lines 782–790):

```python
        # Run Leiden
        try:
            partition = leidenalg.find_partition(
                g,
                leidenalg.RBConfigurationVertexPartition,
                weights="weight",
                resolution_parameter=resolution,
                n_iterations=-1,
            )
        except Exception as e:
            logger.warning("CL-1: Leiden failed for layer %s: %s, falling back", layer, e)
```

Replace with:

```python
        # Run Louvain. Deterministic via seed=42; matches default
        # iteration behavior of leidenalg (run until convergence).
        try:
            partition = nx.algorithms.community.louvain_communities(
                g,
                weight="weight",
                resolution=resolution,
                seed=42,
            )
        except Exception as e:
            logger.warning("CL-1: Louvain failed for layer %s: %s, falling back", layer, e)
```

- [ ] **Step 5: Verify the partition iteration still works**

The downstream code (lines 807–833 currently) does:

```python
        for community in partition:
            member_nids = [layer_nodes[i] for i in community]
```

This must continue to work. `networkx.algorithms.community.louvain_communities` returns `list[set[int]]` where each set contains the node indices we added. Iteration is identical to the leidenalg partition. **No change needed here** — verify with the next step.

- [ ] **Step 6: Run the sanity test**

```bash
.venv/bin/pytest tests/test_cluster_louvain.py -v
```

Expected: PASS. This confirms the swap works inside `build_clusters_leiden`.

- [ ] **Step 7: Run the existing cluster test suite**

```bash
.venv/bin/pytest tests/test_cluster.py -v
```

Expected: PASS (these tests exercise `build_clusters`, the tag-based path, which is untouched).

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/cluster.py
git commit -m "feat(cluster): replace Leiden with Louvain in build_clusters_leiden"
```

---

## Task 5: Replace Leiden with Louvain in `build_clusters_structural`

**Files:**
- Modify: `src/prep/core/cluster.py`

- [ ] **Step 1: Replace the conditional Leiden block**

Find this block in `build_clusters_structural` (currently around lines 976–994):

```python
        # Try Leiden, fall back to connected components
        communities: List[List[int]] = []
        if _leiden_available():
            import igraph as ig
            import leidenalg
            g = ig.Graph(n=ln, directed=False)
            sorted_ep = sorted(edge_pairs.keys())
            weights = [edge_pairs[ep] for ep in sorted_ep]
            g.add_edges(sorted_ep)
            g.es["weight"] = weights
            try:
                partition = leidenalg.find_partition(
                    g, leidenalg.RBConfigurationVertexPartition,
                    weights="weight", resolution_parameter=resolution,
                    n_iterations=-1,
                )
                communities = list(partition)
            except Exception:
                communities = []
```

Replace with:

```python
        # Try Louvain (networkx, BSD), fall back to connected components.
        communities: List[List[int]] = []
        g = nx.Graph()
        g.add_nodes_from(range(ln))
        sorted_ep = sorted(edge_pairs.keys())
        weights = [edge_pairs[ep] for ep in sorted_ep]
        g.add_weighted_edges_from(
            [(i, j, w) for (i, j), w in zip(sorted_ep, weights)]
        )
        try:
            partition = nx.algorithms.community.louvain_communities(
                g, weight="weight", resolution=resolution, seed=42,
            )
            # louvain_communities returns list[set[int]]; convert
            # each set to a sorted list for stable iteration.
            communities = [sorted(c) for c in partition]
        except Exception:
            communities = []
```

- [ ] **Step 2: Run the cluster test suite**

```bash
.venv/bin/pytest tests/test_cluster.py tests/test_cluster_louvain.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/prep/core/cluster.py
git commit -m "feat(cluster): replace Leiden with Louvain in build_clusters_structural"
```

---

## Task 6: Delete `_leiden_available()` and update module docstring

**Files:**
- Modify: `src/prep/core/cluster.py`

- [ ] **Step 1: Delete `_leiden_available()`**

Find and delete this function (currently lines 628–635):

```python
def _leiden_available() -> bool:
    """Check if igraph + leidenalg are installed."""
    try:
        import igraph  # noqa: F401
        import leidenalg  # noqa: F401
        return True
    except ImportError:
        return False
```

- [ ] **Step 2: Verify no other call sites remain**

```bash
grep -n "_leiden_available\|import igraph\|import leidenalg" src/prep/core/cluster.py
```

Expected: no matches. (If matches appear, find and remove them.)

- [ ] **Step 3: Update the module docstring**

Find the existing module docstring at the top of `src/prep/core/cluster.py` (the triple-quoted block after the `from __future__ import annotations` line). Append a paragraph (preserving existing docstring content; if there is no module docstring, add one):

```python
"""... existing docstring content ...

Community detection uses Louvain via ``networkx`` (BSD-3-Clause).
Earlier versions used Leiden via ``igraph`` + ``leidenalg`` (GPL);
the swap was made on 2026-06-10 to keep the codebase Apache-2.0
publishable. See docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md
for the rationale and tradeoff.
"""
```

If `cluster.py` has no existing module docstring, add this whole block immediately below the `from __future__ import annotations` line:

```python
"""Cluster synthesis for the SourcePrep epistemic pipeline.

Community detection uses Louvain via ``networkx`` (BSD-3-Clause).
Earlier versions used Leiden via ``igraph`` + ``leidenalg`` (GPL);
the swap was made on 2026-06-10 to keep the codebase Apache-2.0
publishable. See docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md
for the rationale and tradeoff.
"""
```

- [ ] **Step 4: Run cluster tests**

```bash
.venv/bin/pytest tests/test_cluster.py tests/test_cluster_louvain.py tests/test_cluster_swarm.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/cluster.py
git commit -m "refactor(cluster): drop _leiden_available shim + update docstring"
```

---

## Task 7: Uninstall igraph + leidenalg from the venv

**Why:** Both libs are still present in `.venv` from earlier ad-hoc installs. Until they're removed, the import-guard test (Task 8) will fail.

- [ ] **Step 1: List installed versions for the record**

```bash
.venv/bin/pip show igraph leidenalg python-igraph 2>&1 | grep -E "^Name|^Version"
```

Expected output similar to:

```
Name: igraph
Version: 1.0.0
Name: leidenalg
Version: 0.11.0
```

(If `python-igraph` is also installed, note it — older name for the same package.)

- [ ] **Step 2: Uninstall**

```bash
.venv/bin/pip uninstall -y igraph leidenalg python-igraph 2>&1
```

Expected: confirmation of removal for each package present. `python-igraph` may report "not installed" — that is fine.

- [ ] **Step 3: Verify they are gone**

```bash
.venv/bin/python -c "import igraph" 2>&1
.venv/bin/python -c "import leidenalg" 2>&1
```

Expected: both raise `ModuleNotFoundError`.

- [ ] **Step 4: Run cluster tests to confirm nothing breaks**

```bash
.venv/bin/pytest tests/test_cluster.py tests/test_cluster_louvain.py tests/test_cluster_swarm.py -v
```

Expected: PASS. The code no longer references either library, so removal is a no-op runtime-wise.

(No commit here — this step changes the venv, not the repo.)

---

## Task 8: Add import-guard regression test

**Files:**
- Create: `tests/test_no_gpl_deps.py`

- [ ] **Step 1: Write the test**

Create `tests/test_no_gpl_deps.py`:

```python
"""Regression guard: GPL-licensed graph libraries must not be installed.

SourcePrep ships under a permissive license (target: Apache 2.0). The
``igraph`` (GPL-2.0) and ``leidenalg`` (GPL-3.0-or-later) libraries
were removed in the Phase 144 GPL dependency replacement. This test
fails if either reappears in the environment so the contamination
cannot return unnoticed.

If you have a legitimate need for community detection, use
``networkx.algorithms.community.louvain_communities`` instead.
"""
import importlib

import pytest


@pytest.mark.parametrize("modname", ["igraph", "leidenalg"])
def test_gpl_dep_not_installed(modname: str) -> None:
    with pytest.raises(ImportError):
        importlib.import_module(modname)
```

- [ ] **Step 2: Run the test**

```bash
.venv/bin/pytest tests/test_no_gpl_deps.py -v
```

Expected: PASS (both `igraph` and `leidenalg` were uninstalled in Task 7).

- [ ] **Step 3: Verify it actually catches contamination (smoke check)**

Temporarily re-install one lib, confirm the test fails, then uninstall:

```bash
.venv/bin/pip install igraph 2>&1 | tail -3
.venv/bin/pytest tests/test_no_gpl_deps.py -v 2>&1 | tail -10
```

Expected: the `igraph` parametrized case FAILS (DID NOT RAISE).

Then restore:

```bash
.venv/bin/pip uninstall -y igraph 2>&1 | tail -3
.venv/bin/pytest tests/test_no_gpl_deps.py -v
```

Expected: both pass again.

- [ ] **Step 4: Commit**

```bash
git add tests/test_no_gpl_deps.py
git commit -m "test: regression guard against igraph/leidenalg reinstall"
```

---

## Task 9: Run full test suite

- [ ] **Step 1: Run everything**

```bash
.venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -80
```

Expected: green. If any test fails, **stop and diagnose** — do not skip.

Likely-relevant failure modes to look for:
- `ModuleNotFoundError: igraph` or `leidenalg` in unrelated tests → grep for missed imports and fix.
- Unexpected partition iteration error in `cluster.py` → re-check Task 4 Step 5 (the `for community in partition:` loop expects an iterable-of-iterables-of-ints).

- [ ] **Step 2: Commit any incidental fixes**

If Step 1 surfaced and required code fixes, commit them with a descriptive message. If everything was green, skip this step.

---

## Task 10: Manual daemon dogfood

**Why:** Per CLAUDE.md, this project dogfoods itself. Restart the daemon and verify clustering still produces sensible output on the SourcePrep repo.

- [ ] **Step 1: Stop any running daemon**

If the daemon is running for the original `/Volumes/4TB-BAD/HumanAI/CoDRAG` checkout, leave it alone — it's pointed at the unmodified main checkout. The worktree change does not affect it until merged.

For this verification, we want the daemon to load the modified code. Easiest: temporarily run the daemon from the worktree:

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG-gpl-fix
.venv/bin/prep serve --port 8401 &
```

(Use port 8401 so it doesn't collide with any 8400 daemon.)

- [ ] **Step 2: Trigger a clustering run**

This depends on the project's pipeline workflow. Two options:

(a) If a project is already indexed and `build_clusters` runs during a fast/deep rebuild, trigger one:

```bash
curl -s -X POST http://localhost:8401/pipeline/fast -H 'Content-Type: application/json' -d '{"force_from_start": true}' | head -20
```

(b) If you only want to verify import-time correctness (no full pipeline run), this minimal check is enough:

```bash
.venv/bin/python -c "from prep.core.cluster import build_clusters_leiden, build_clusters_structural; print('imports clean')"
```

Expected: `imports clean` and no traceback.

- [ ] **Step 3: Stop the daemon**

```bash
pkill -f "prep serve --port 8401"
```

Expected: no error.

(No commit — this is a verification step.)

---

## Task 11: Update PRE_LAUNCH_BLOCKERS.md

**Files:**
- Modify: `docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md`

- [ ] **Step 1: Flip blocker #1 to resolved**

In `docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md`, replace the section:

```markdown
## 1. GPL Dependency Replacement (Critical Legal Blocker)
- **Status:** [ ] Open
- **Risk:** The Python backend currently relies on `igraph` (GPL) and `leidenalg` (GPL-3.0). GPL is "viral." Publishing SourcePrep under Apache 2.0 while importing GPL libraries violates the GPL and could force the entire project to be re-licensed as GPL, severely harming enterprise adoption and acquisition potential.
- **Action Required:** Replace `igraph` and `leidenalg` (used for community detection in the graph) with Apache/MIT-compatible alternatives. `networkx` or a pure-Python Louvain implementation are recommended replacements.
```

With:

```markdown
## 1. GPL Dependency Replacement (Critical Legal Blocker)
- **Status:** [x] Resolved 2026-06-10
- **Risk:** The Python backend used `igraph` (GPL) and `leidenalg` (GPL-3.0). GPL is "viral." Publishing SourcePrep under Apache 2.0 while importing GPL libraries would have violated the GPL and could have forced the entire project to be re-licensed as GPL.
- **Resolution:** Replaced Leiden community detection (`igraph` + `leidenalg`) with Louvain via `networkx` (BSD-3-Clause). Changes scoped to `src/prep/core/cluster.py`. `networkx>=3.0` added as a declared dependency. Both GPL libraries uninstalled from `.venv`. Regression guard added at `tests/test_no_gpl_deps.py` to prevent reintroduction. See `docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md` and `docs/superpowers/plans/2026-06-10-gpl-dependency-replacement.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md
git commit -m "docs(phase144): mark blocker #1 (GPL deps) resolved"
```

---

## Task 12: Final verification + merge offer

- [ ] **Step 1: Re-run full test suite one more time**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG-gpl-fix
.venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: green.

- [ ] **Step 2: Final repo-wide GPL grep**

```bash
grep -rn "import igraph\|from igraph\|import leidenalg\|from leidenalg" --include="*.py" .
```

Expected: no matches.

- [ ] **Step 3: Show commits to be merged**

```bash
git log --oneline main..HEAD
```

Expected output similar to:

```
<hash> docs(phase144): mark blocker #1 (GPL deps) resolved
<hash> test: regression guard against igraph/leidenalg reinstall
<hash> refactor(cluster): drop _leiden_available shim + update docstring
<hash> feat(cluster): replace Leiden with Louvain in build_clusters_structural
<hash> feat(cluster): replace Leiden with Louvain in build_clusters_leiden
<hash> test(cluster): sanity test for community detection (baseline)
<hash> deps: declare networkx>=3.0 explicitly (was transitive)
```

- [ ] **Step 4: Stop and ask the user how to integrate**

Do NOT auto-merge to `main`. Per the user's preference (memory: `feedback_explicit_push_only.md`), changes stay in the worktree until the user explicitly says merge/ship. Present the user with options:

> **Worktree complete and verified.** Branch: `fix/gpl-dep-replacement`. 7 commits. All tests green. Full suite: `<N>` passed.
>
> Integration options:
> 1. **Merge to main locally** (`git checkout main && git merge --ff-only fix/gpl-dep-replacement`), no push
> 2. **Keep the worktree open** for further review
> 3. **Discard** (`git worktree remove ../CoDRAG-gpl-fix && git branch -D fix/gpl-dep-replacement`)
>
> Which?

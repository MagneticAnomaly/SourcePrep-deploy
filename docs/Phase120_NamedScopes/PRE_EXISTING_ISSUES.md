# Pre-existing issues observed during Phase 120 setup

Surfaced while running the baseline test pass before starting Phase 120
implementation. **Not in scope for Phase 120**; documented here so the
next person who runs the suite isn't surprised and so the issue gets
tracked somewhere.

## 1. `tests/test_scope_orchestrator.py::test_add_files_triggers_rebuild`

**Symptom:**

```
assert 0 == 1
 +  where 0 = len([])
tests/test_scope_orchestrator.py:56
```

The test calls `scope_orchestrator.on_files_added(...)` and expects a
rebuild to fire once within the assertion window. It fires zero times.

**Confirmed scope:**
- Fails on the `phase120-named-scopes` worktree.
- Fails on `main` at `08250892`.
- 35 other scope-related tests pass on both.

This is a real failure, not a flake we can blame on environment. It
either means the orchestrator's debounce-timing test is broken, or the
production path that fires the rebuild has regressed. Either way the
test was broken before Phase 120 started.

**Why this isn't a Phase 120 concern:**
Phase 120 introduces a `mock_orchestrator` test fixture
(`tests/api/conftest.py`) that monkey-patches the orchestrator
singleton with a recorder. All Phase 120 tests assert against the
recorder, never against the live debounce timing. So this failure
neither blocks our work nor masks new bugs in our code.

**Recommendation:**
File as a separate ticket. Likely fixes:
- If the test is wrong: add a `wait_for_debounce` helper or use the
  orchestrator's existing `status()` polling instead of asserting on
  a captured-list length.
- If production is wrong: trace why `on_files_added` no longer fires
  `_schedule_rebuild`. Bisect against recent Phase 117/118/119
  changes that touched the orchestrator's debounce logic.

The Phase 120 plan does NOT change `scope_orchestrator.py` itself,
only its callers — so this fix is genuinely orthogonal.

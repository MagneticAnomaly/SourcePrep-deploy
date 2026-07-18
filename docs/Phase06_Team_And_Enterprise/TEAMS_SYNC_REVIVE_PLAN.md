# Teams Sync Revive & Finish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the SourcePrep Teams tier from "built-but-rotted" to a shippable, license-gated, privacy-correct shared-index sync — by reviving the existing implementation, not rebuilding it.

**Architecture:** Teams Sync already exists end-to-end (headless CI indexer → S3 artifact → client daemon fetch + local delta merge → served to agents). It was built Feb–Mar 2026, then drifted after the `.runprep`→`.sourceprep` rename and 140+ phases of churn. This plan (a) fixes the rot to restore a green baseline, (b) closes a real license-gate bypass, (c) makes the never-published Docker image exist, (d) wires the privacy boundary, and (e) surfaces the sync UI. The full handoff vision (commit-addressable artifacts, git-diff delta, overlay graph, webhook) is captured as a prioritized Phase-2 backlog.

**Tech Stack:** Python 3.11 (FastAPI daemon, Typer CLI), Rust engine (tree-sitter), React/Vite dashboard + `@prep/ui`, boto3/S3-compatible storage (AWS S3 / Cloudflare R2 / MinIO), GitHub Actions + GHCR, pytest (`asyncio_mode=auto`).

---

## Why this plan exists (read first)

Today's greenfield handoff — `docs/superpowers/plans/2026-07-18-teams-sync-handoff.md` — describes this feature **as if nothing is built**. That is wrong and, if followed literally, would rebuild over ~65% of salvageable, tested code. This plan **supersedes** that handoff. Evidence for the current state:

- **The suite is RED.** `.venv/bin/pytest tests/test_remote_sync.py tests/test_layered_index.py tests/test_headless_runner.py tests/test_s3_storage.py tests/test_team_sync_integration.py -q` → **~23 failed, ~103 passed** on HEAD (2026-07-18). Three root causes, all drift: (1) tests still use the old `.runprep/` embedded dir (product renamed it to `.sourceprep/`), (2) `HEADLESS_STAGES` grew 10→11, (3) the embedder patch target moved in Phase 139. **All test-rot — no product regression in these.**
- `docs/Phase06_Team_And_Enterprise/PROGRESS.md` still claims "69/69 pass, 0 regressions." **That claim is now false.**
- The handoff cites **"$30/seat Enterprise"**; pricing changed to **$24/seat** on 2026-07-18 (commits `5f69e5e4`, `f8072293`).

### What already works (do NOT rebuild)
`src/prep/services/headless_runner.py` (real 11-stage headless orchestrator, wired to `prep sync-headless`), `src/prep/services/s3_storage.py` (real boto3 upload/download with atomic swap, zip-slip + zip-bomb guards, content-hash verify), `src/prep/services/remote_sync.py` (client polling + secrets-leak detection), `src/prep/core/layered_index.py` (real base+delta **embedding** merge with tombstones), `src/prep/core/team_config.py` + `feature_gate.py` (license tiers), CPU+GPU Dockerfiles, GitHub Actions / Modal / RunPod / AWS ECS deploy templates.

### The one pivotal scope decision (decide before Task 4)
**Does MVP Teams use a customer-provided bucket (BYO) or a SourcePrep-hosted bucket?** This changes the size of the privacy work:

- **BYO-bucket (recommended MVP):** the customer supplies their own S3/R2/MinIO creds (exactly what the code does today via `PREP_S3_*`). Shipping index `content` to the customer's *own* bucket is **not a leak**. Enterprise (customer VPC/MinIO) is the same case. → The content-strip + client-hydration work becomes **Phase 2**, gated on hosted-bucket launch. Fastest path to a sellable tier.
- **SourcePrep-hosted bucket (bigger MVP):** SourcePrep hosts the worker + bucket (handoff §3.2). Then shipping raw source to *our* infra **violates the §5 "source is NEVER uploaded" promise** and is a hard launch blocker → Task 4's strip **and** the Phase-2 client-hydration companion both move into MVP.

**Recommendation:** ship **BYO-bucket first**. Task 4 still lands the fail-closed `strip_source_content` capability + test so the switch is ready, but the heavier client-hydration path stays in Phase 2 (P2-4) until hosting is offered. Confirm this with Eric before executing Task 4.

> ⚠️ **Accuracy correction (supersedes an earlier statement):** the source-content upload is a leak **only for a SourcePrep-hosted bucket**. For Enterprise (customer VPC) and BYO-bucket Teams it is the customer's own infra and is acceptable. Frame all messaging accordingly.

---

## Repo conventions for the implementer (non-negotiable)

- **Branch first.** Current branch is `main`. Create `git checkout -b phase06-teams-sync-revive` before any change. Never commit MVP work directly to `main`.
- **Commit locally only. Do NOT push, tag, or trigger CI.** Every `git push`, `git tag ... && git push`, and `gh workflow run` in this plan is an **explicit action for Eric to run himself** — the implementer must stop and hand him the exact command. (Each push triggers 4 Netlify builds; a `app-v*` tag also triggers the desktop release pipeline — see Task 5.)
- **No `Co-Authored-By` trailer** in commit messages.
- **Use the project venv:** `.venv/bin/python`, `.venv/bin/pytest` — never system Python. `codrag`/`prep` is the project itself, not a pip dependency; test via pytest.
- **Restart the daemon before any live validation.** `prep serve` has no hot-reload; stale in-memory code will silently pass validation against old behavior.
- **This machine is on a USB/external drive.** SQLite WAL is unreliable here; do not enable it.

---

## File Structure (what each MVP task touches)

| Task | Files | Responsibility |
|------|-------|----------------|
| 0 | (none — baseline capture) | Record the red starting state as evidence |
| 1 | `tests/test_remote_sync.py`, `tests/test_layered_index.py`, `tests/test_team_sync_integration.py` | Test-only `.runprep`→`.sourceprep` sweep (26 sites, 3 files) |
| 2 | `tests/test_headless_runner.py` | Fix stage-count (10→11) + embedder patch target (Phase 139) |
| 3 | `src/prep/services/project_helpers.py` (+ new test in `tests/test_team_sync_integration.py`) | Close the license-gate bypass on the `/status` polling path |
| 4 | `src/prep/services/s3_storage.py`, `src/prep/services/remote_sync.py`, `src/prep/services/headless_runner.py` (+ `tests/test_s3_storage.py`) | Fail-closed `strip_source_content` privacy capability at the upload boundary |
| 5 | `.github/workflows/docker-headless.yml`, `public/sourceprep-deploy/github-actions/prep-sync.yml`, `public/sourceprep-deploy/modal/modal_adapter.py`, `public/sourceprep-deploy/aws/ecs-task-definition.json`, `public/sourceprep-deploy/aws/README.md`, `public/sourceprep-deploy/README.md`, `websites/apps/docs/src/app/guides/team-sync/page.tsx`, `websites/apps/docs/src/app/guides/enterprise-deploy/page.tsx` | Fix ghcr namespace + publish the headless image (Eric runs the publish) |
| 6 | `src/prep/api/routers/projects/watch.py`, `src/prep/server.py`, `src/prep/dashboard/src/App.tsx` (or a settings page) | "Sync Now" endpoint + render `SyncStatusCard` |
| 7 | `docs/Phase06_Team_And_Enterprise/PROGRESS.md`, `docs/superpowers/plans/2026-07-18-teams-sync-handoff.md` | Correct stale claims; mark handoff superseded; final green-suite gate |

---

## Task 0: Capture the red baseline

**Files:** none (evidence only).

- [ ] **Step 1: Record current failures**

Run:
```bash
.venv/bin/pytest tests/test_remote_sync.py tests/test_layered_index.py \
  tests/test_headless_runner.py tests/test_s3_storage.py \
  tests/test_team_sync_integration.py -q 2>&1 | tail -30
```
Expected: **~23 failed, ~103 passed**. Paste the summary line into the task's PR/notes as the "before" evidence. This is the baseline every later task drives toward zero.

---

## Task 1: Fix the `.runprep`→`.sourceprep` test rot (test-only)

**Category:** test-rot. Product code is correct (`project_registry.py:63`, `remote_sync.py:239` both use `.sourceprep`). The tests write config/index under the dead `.runprep/` dir, so the service finds nothing and returns `None`/plain-`CodeIndex`.

**Files:**
- Modify: `tests/test_remote_sync.py` (1 site + docstring, ~L198–199)
- Modify: `tests/test_layered_index.py` (11 sites: L235,255,280,338,363,387,402,420,456,489,496)
- Modify: `tests/test_team_sync_integration.py` (13 sites: L351,379,410,477,527,536,550,573,635,710,729,762,882)

> **SCOPE GUARDRAIL — do NOT run a repo-wide replace.** Other test files intentionally assert on `.runprep` for legacy back-compat (`test_user_exclude_respected.py`, `test_walker_parity.py`, `test_no_self_ingestion.py`, `test_phase128_*.py`, `test_paths.py`, `test_data_dir_migration.py`, `tests/core/test_git_evidence.py`) and MUST keep it. And do NOT change any `.runprep` in `src/` — those are deliberate legacy-install support (e.g. `~/.runprep/license.json` fallback, additive exclude globs). Rewriting either would delete real coverage / break legacy installs.

- [ ] **Step 1: Run the three files to confirm the failures (before)**

Run:
```bash
.venv/bin/pytest tests/test_remote_sync.py tests/test_layered_index.py \
  tests/test_team_sync_integration.py -q 2>&1 | tail -5
```
Expected: **21 failed, 67 passed**.

- [ ] **Step 2: Apply the scoped replacement (exactly these 3 files)**

Run (macOS `sed`):
```bash
sed -i '' 's/\.runprep/.sourceprep/g' \
  tests/test_remote_sync.py \
  tests/test_layered_index.py \
  tests/test_team_sync_integration.py
```
This swaps all 26 occurrences (dir construction + the one docstring on `test_remote_sync.py:198`). All are plain path construction — none are assertions on legacy behavior (verified: 0 `assert`/`exclude`/`glob` uses near `.runprep` in these files).

- [ ] **Step 3: Verify the three files are green (after)**

Run:
```bash
.venv/bin/pytest tests/test_remote_sync.py tests/test_layered_index.py \
  tests/test_team_sync_integration.py -q 2>&1 | tail -5
```
Expected: **0 failed, 88 passed**.

- [ ] **Step 4: Verify scope was respected (legacy tests still green)**

Run:
```bash
.venv/bin/pytest tests/test_user_exclude_respected.py tests/test_walker_parity.py \
  tests/test_no_self_ingestion.py tests/test_paths.py \
  tests/test_phase128_license_path_fallback.py \
  tests/test_phase128_paths_migration_orphan_warning.py -q 2>&1 | tail -5
```
Expected: all pass (no regressions).

- [ ] **Step 5: Commit**

```bash
git add tests/test_remote_sync.py tests/test_layered_index.py tests/test_team_sync_integration.py
git commit -m "test(phase06): fix .runprep->.sourceprep rot in team-sync tests"
```

---

## Task 2: Fix stage-count + embedder patch-target rot in `test_headless_runner.py`

**Category:** test-rot. Product behavior is intentional: `HEADLESS_STAGES` has 11 stages (the 11th is `group_reasoning`, inserted mid-list), and Phase 139 routes native embedding through `embedder_factory.create_embedder` (no direct `NativeEmbedder()` construction). Fix the tests, not the product.

**Files:**
- Modify: `tests/test_headless_runner.py` (`TestHeadlessCreateEmbedder` ~L99–116; `TestHeadlessStages` ~L177–178)

- [ ] **Step 1: Confirm the two failures (before)**

Run:
```bash
.venv/bin/pytest tests/test_headless_runner.py -q 2>&1 | tail -8
```
Expected: 2 failed (`TestHeadlessStages::test_stage_count` = `assert 11 == 10`; `TestHeadlessCreateEmbedder::test_fallback_to_ollama_when_native_unavailable` — order-dependent mock leak), ~22 passed.

- [ ] **Step 2: Replace the embedder tests to patch the real Phase-139 call sites**

In `tests/test_headless_runner.py`, replace `test_native_when_available` and `test_fallback_to_ollama_when_native_unavailable` (currently ~L99–116) with:
```python
    def test_native_when_available(self):
        # Phase 139: native path delegates to embedder_factory.create_embedder,
        # it no longer constructs prep.core.NativeEmbedder() directly.
        cfg = HeadlessConfig(embedder="native")
        sentinel = object()
        with patch("prep.core.NativeEmbedder.is_available", return_value=True), \
             patch(
                 "prep.services.embedder_factory.create_embedder",
                 return_value=sentinel,
             ) as mock_create:
            embedder = headless_create_embedder(cfg)
            assert embedder is sentinel
            mock_create.assert_called_once_with("native")

    def test_fallback_to_ollama_when_native_unavailable(self):
        # is_available() is a staticmethod on the class — patch the class attr,
        # not the instance, so the availability gate actually returns False.
        cfg = HeadlessConfig(embedder="native")
        with patch("prep.core.NativeEmbedder.is_available", return_value=False), \
             patch("prep.core.OllamaEmbedder") as mock_ollama:
            mock_ollama_instance = MagicMock()
            mock_ollama.return_value = mock_ollama_instance
            embedder = headless_create_embedder(cfg)
            assert embedder is mock_ollama_instance
```

- [ ] **Step 3: Fix the stage-count assertion and add an ordered identity check**

Replace `test_stage_count` (currently `assert len(HEADLESS_STAGES) == 10` at ~L177–178) with:
```python
    def test_stage_count(self):
        assert len(HEADLESS_STAGES) == 11

    def test_stage_ids_in_order(self):
        # Identity check instead of a bare magic number: if the pipeline
        # gains/loses/reorders a stage this fails with the actual diff.
        assert [s[0] for s in HEADLESS_STAGES] == [
            "structural",
            "inferred_edges",
            "catalogue",
            "validation",
            "knowledge",
            "enrichment",
            "group_reasoning",
            "clustering",
            "atlas",
            "deepening",
            "deep_knowledge",
        ]
```

- [ ] **Step 4: Run the whole file (not `-k`) to prove the singleton-leak is gone**

Run:
```bash
.venv/bin/pytest tests/test_headless_runner.py -v 2>&1 | tail -15
```
Expected: all pass (25 tests incl. the new `test_stage_ids_in_order`). Running the full file matters — it exercises the shared-embedder singleton path that caused the original order-dependent failure.

- [ ] **Step 5: Commit**

```bash
git add tests/test_headless_runner.py
git commit -m "test(phase06): fix headless stage-count (11) and Phase-139 embedder patch targets"
```

---

## Task 3: Close the license-gate bypass on the `/status` polling path (product bug)

**Category:** product-bug. `get_project_sync_status()` starts S3 polling whenever `team_config.json` has `sync.enabled: true`, with **no** `check_feature("team_config")` gate. It's called on every `GET /projects/{id}/status` (which the dashboard polls continuously), so any free/pro tier with a committed team config silently gets the paid Team feature. The CLI (`cli.py:1408`) and startup auto-poll (`server.py:1280`) are correctly gated — the `/status` path is the hole.

**Files:**
- Modify: `src/prep/services/project_helpers.py` (`get_project_sync_status`, ~L418–429)
- Test: `tests/test_team_sync_integration.py` (add to the existing `TestFeatureGating` area)

- [ ] **Step 1: Write the failing gate test**

Add to `tests/test_team_sync_integration.py` (uses the existing license-tier fixtures / `clear_license_cache` pattern in that file):
```python
    def test_status_polling_gated_by_license(self, tmp_path, monkeypatch):
        # A project with sync.enabled=true must NOT start polling on the
        # /status path unless the license is Team+ (parity with cli.py:1408).
        from unittest.mock import MagicMock
        import prep.services.project_helpers as ph
        from prep.services.remote_sync import RemoteSyncService

        prep_dir = tmp_path / ".sourceprep"
        prep_dir.mkdir(parents=True)
        (prep_dir / "team_config.json").write_text(
            json.dumps({"sync": {"enabled": True, "s3_bucket": "b"}})
        )
        project = _make_project_obj(tmp_path)  # existing helper in this file
        started = MagicMock()
        monkeypatch.setattr(RemoteSyncService, "start_polling", started)

        _set_tier("free")  # existing tier helper (clears license cache)
        ph.get_project_sync_status(project, {})
        assert started.call_count == 0

        _set_tier("team")
        ph.get_project_sync_status(project, {})
        assert started.call_count == 1
```
> If `_make_project_obj` / `_set_tier` helper names differ in the file, use the equivalents already present in `TestFeatureGating` (which sets tiers via `clear_license_cache` + a license fixture). Do not invent new fixtures.

- [ ] **Step 2: Run it to verify it fails**

Run:
```bash
.venv/bin/pytest "tests/test_team_sync_integration.py::TestFeatureGating::test_status_polling_gated_by_license" -v 2>&1 | tail -10
```
Expected: FAIL — `start_polling` is called on the free tier (`call_count == 1`, not 0).

- [ ] **Step 3: Add the gate at the chokepoint**

In `src/prep/services/project_helpers.py`, replace the polling-start block (currently ~L425–427) inside `get_project_sync_status`:
```python
    # Start polling if enabled, licensed, and not already polling.
    # Gate with team_config (Team tier) — parity with cli.py:1408 and
    # server.py:1280. Without this, GET /projects/{id}/status (polled
    # continuously by the dashboard) would start S3 polling for ANY tier
    # that merely has a committed team_config.json, bypassing the license.
    from prep.core.feature_gate import check_feature
    if (
        syncer._config
        and syncer._config.enabled
        and syncer._poll_thread is None
        and check_feature("team_config")
    ):
        syncer.start_polling()
```
Gate the **polling** (the paid work), not `status_dict()` — keep returning status so the UI can still show an upgrade prompt. Use the in-function lazy import (matches the existing style at `project_helpers.py:153,241`).

- [ ] **Step 4: Verify the gate test passes and nothing else broke**

Run:
```bash
.venv/bin/pytest tests/test_team_sync_integration.py tests/test_remote_sync.py -q 2>&1 | tail -6
```
Expected: all pass (the existing end-to-end tests call `check_and_sync()` directly, not through `get_project_sync_status`, so they're unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/project_helpers.py tests/test_team_sync_integration.py
git commit -m "fix(phase06): gate team-sync polling on /status path behind team_config license"
```

> **Deferred (see P2):** downgrade Team→Free does not stop an already-running poll thread until daemon restart. Tracked as P2-7.

---

## Task 4: Land the fail-closed source-content privacy capability (upload boundary)

**Category:** product-bug (capability gap). `documents.json` carries the raw source (`content=ch.content`, `index.py:621`) and is uploaded verbatim (`s3_storage.py` `INDEX_ARTIFACTS` includes it). For a **SourcePrep-hosted** bucket that violates the §5 promise. For **BYO-bucket / Enterprise** (customer's own infra) it's acceptable.

> **DECISION GATE (from the scope note up top):** confirm BYO-vs-hosted MVP with Eric first.
> - **BYO-bucket MVP (recommended):** implement this task's **strip capability + test only** (default OFF; content still ships to the customer's own bucket). The client-hydration companion that makes strip=ON usable is **P2-4** and is required before any hosted-bucket launch.
> - **Hosted-bucket MVP:** implement this task **and** P2-4 (client working-tree hydration) together, and default `strip_source_content=True` (fail-closed).

**Why not simpler options (verified):** excluding `documents.json` entirely breaks *search* itself (embeddings.npy is row-aligned with it); scrubbing at the write site breaks the *local* daemon (renders its own context from the same file). The only correct place to strip is the **uploaded copy**.

**Files:**
- Modify: `src/prep/services/s3_storage.py` (`INDEX_ARTIFACTS` region ~L24–54; `upload_index` ~L174–217; add `S3Config.strip_source_content`)
- Modify: `src/prep/services/remote_sync.py` (`_get_s3_provider` ~L289–295 — pass the flag)
- Modify: `src/prep/services/headless_runner.py` (~L413 provider construction — pass the flag)
- Test: `tests/test_s3_storage.py`

- [ ] **Step 1: Write the failing privacy test**

Add to `tests/test_s3_storage.py`:
```python
def test_upload_strips_source_content_when_flagged(tmp_path):
    import json, zipfile
    from prep.services.s3_storage import S3StorageProvider, S3Config

    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "documents.json").write_text(json.dumps([
        {"id": "d1", "source_path": "a.py", "file_hash": "h",
         "role": "code", "section": "", "span": {"start_line": 1, "end_line": 1},
         "content": "SECRET_TOKEN = 'xyz'"},
    ]))
    # embeddings.npy must exist for a realistic artifact set
    import numpy as np
    np.save(idx / "embeddings.npy", np.zeros((1, 8), dtype="float32"))

    provider = S3StorageProvider(S3Config(bucket="b", strip_source_content=True))
    captured = {}
    provider._client = _mock_s3_capturing(captured)  # existing test helper pattern

    provider.upload_index(idx, branch="main", commit_sha="abc")

    zbytes = captured["put_bytes"]  # the uploaded zip payload
    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        docs = json.loads(zf.read("documents.json"))
    assert "content" not in docs[0]          # raw source stripped
    assert docs[0]["source_path"] == "a.py"  # metadata + span kept
    assert docs[0]["span"] == {"start_line": 1, "end_line": 1}
```
> Adapt `_mock_s3_capturing` / `provider._client` assignment to the mock style already used in `test_s3_storage.py` (that file assigns `provider._client = mock_client`). The key assertion is: the uploaded `documents.json` has no `content` key when `strip_source_content=True`.

- [ ] **Step 2: Run it to verify it fails**

Run:
```bash
.venv/bin/pytest "tests/test_s3_storage.py::test_upload_strips_source_content_when_flagged" -v 2>&1 | tail -10
```
Expected: FAIL — `content` is still present (no strip capability exists yet).

- [ ] **Step 3: Add the strip capability to `s3_storage.py`**

Near `INDEX_ARTIFACTS` (top of `s3_storage.py`), add:
```python
_CONTENT_BEARING_ARTIFACTS = {"documents.json"}  # raw source lives here

def _scrub_documents_json(raw_json: str) -> bytes:
    """Drop raw source ('content') from a documents.json payload, keeping
    metadata + span. Row order is preserved so embeddings.npy stays aligned."""
    import json as _json
    docs = _json.loads(raw_json)
    for d in docs:
        d.pop("content", None)
        d.pop("truncated", None)
        d.pop("original_size", None)
    return _json.dumps(docs).encode()
```
Add `strip_source_content: bool = False` to `S3Config`. In `upload_index`, replace the zip-write loop body:
```python
            strip = self.config.strip_source_content
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for artifact in artifacts:
                    if strip and artifact.name in _CONTENT_BEARING_ARTIFACTS:
                        scrubbed = _scrub_documents_json(artifact.read_text())
                        zf.writestr(artifact.name, scrubbed)
                        total_bytes += len(scrubbed)
                    else:
                        zf.write(artifact, artifact.name)
                        total_bytes += artifact.stat().st_size
```

- [ ] **Step 4: Plumb the flag (default fail-closed for hosted; OFF for BYO/Enterprise)**

In `remote_sync.py` `_get_s3_provider` (~L289) and `headless_runner.py` (~L413), pass `strip_source_content` from the sync config. Source of truth = a new `TeamSyncConfig.bucket_is_vendor_hosted` (or `tier`) field; default the flag **True (fail-closed)** so a misconfigured hosted setup loses fidelity rather than leaking, and let Enterprise/BYO explicitly set it False. Document the field in `team_config.json` schema.
> For **BYO-bucket MVP**, the default in practice is OFF (customer bucket). Wire the field; do not force strip on BYO.

- [ ] **Step 5: Verify + guard against the foot-gun**

Run:
```bash
.venv/bin/pytest tests/test_s3_storage.py tests/test_team_sync_integration.py -q 2>&1 | tail -6
```
Expected: all pass. Existing `test_index_artifacts_*` stay valid (the allowlist is unchanged; only the payload is scrubbed).
> **Foot-gun note for the plan:** `strip_source_content=True` **without** the P2-4 client hydration renders every `get_context` block as an empty ```` ``` ```` fence (search still ranks, but no code is shown). If Eric picks hosted-bucket MVP, do P2-4 in the same milestone. If BYO MVP, keep strip OFF until P2-4 ships.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/s3_storage.py src/prep/services/remote_sync.py \
        src/prep/services/headless_runner.py tests/test_s3_storage.py
git commit -m "feat(phase06): fail-closed strip_source_content capability at S3 upload boundary"
```

---

## Task 5: Publish the headless Docker image (currently never published)

**Category:** infra. Every deploy template references `ghcr.io/ericbintner/prep-headless:{cpu,gpu}`, but **no image was ever built** (no `app-v*` tag ever fired the workflow). Two blockers must be resolved or even a manual run fails/produces an un-pullable image.

**Verified facts (2026-07-18):** origin = `MagneticAnomaly/SourcePrep` (org); `IMAGE_NAME: ericbintner/prep-headless` (user namespace) → `GITHUB_TOKEN` can't push there (403). `git tag -l 'app-v*'` is empty. Both `docker-headless.yml` **and** `release.yml` trigger on `push: tags: 'app-v*'` → a tag-push also launches the desktop release pipeline. GHCR packages default to **private** (unauthenticated customer pulls would 401).

**Files:**
- Modify: `.github/workflows/docker-headless.yml` (`IMAGE_NAME`, L15)
- Modify (consumer refs, only if renaming namespace): `public/sourceprep-deploy/github-actions/prep-sync.yml:29`, `public/sourceprep-deploy/modal/modal_adapter.py:25`, `public/sourceprep-deploy/aws/ecs-task-definition.json:13`, `public/sourceprep-deploy/aws/README.md:17-20`, `public/sourceprep-deploy/README.md:59-60`, `websites/apps/docs/src/app/guides/team-sync/page.tsx` (L64,70,116,259,265), `websites/apps/docs/src/app/guides/enterprise-deploy/page.tsx` (L53,59,83,84,113)

- [ ] **Step 1: Confirm no image exists (baseline)**

Run:
```bash
docker manifest inspect ghcr.io/ericbintner/prep-headless:cpu 2>&1 | tail -2   # expect: not found
git tag -l 'app-v*'                                                             # expect: empty
```

- [ ] **Step 2: Resolve BLOCKER 1 — namespace (DECISION)**

Pick one:
- **Option A (recommended):** rename `IMAGE_NAME: ericbintner/prep-headless` → `magneticanomaly/prep-headless` (matches the repo owner, so `GITHUB_TOKEN`'s `packages: write` works out of the box), and update **all** consumer references listed above to `ghcr.io/magneticanomaly/prep-headless`.
- **Option B:** keep the `ericbintner` namespace and add a PAT secret (`write:packages` for the ericbintner account) used as the `docker/login-action` password in both login steps (lines ~27–32 and ~64–69) instead of `secrets.GITHUB_TOKEN`. Smaller diff, but adds a personal-account PAT dependency + a confusing user/org split.

Apply the chosen edit(s). If Option A, do a scoped grep to confirm no `ericbintner/prep-headless` reference is missed:
```bash
grep -rn "ericbintner/prep-headless" . --include=*.yml --include=*.py --include=*.json --include=*.md --include=*.tsx
```

- [ ] **Step 3: Commit the code/config edits**

```bash
git add .github/workflows/docker-headless.yml public/sourceprep-deploy websites/apps/docs
git commit -m "fix(phase06): headless image namespace -> magneticanomaly for GHCR publish"
```

- [ ] **Step 4: PUBLISH — Eric runs this himself (do NOT auto-run)**

`workflow_dispatch:` already exists on `docker-headless.yml` (line 7), so **no tag is needed** (and a tag would also trigger `release.yml`). Hand Eric:
```bash
# Eric runs (explicit CI trigger):
gh workflow run docker-headless.yml --ref phase06-teams-sync-revive   # or main once merged
gh run watch $(gh run list --workflow=docker-headless.yml -L1 --json databaseId -q '.[0].databaseId')
```
This publishes the floating `:cpu` and `:gpu` tags every consumer references (plus `:cpu-dev`/`:gpu-dev`).

- [ ] **Step 5: Resolve BLOCKER 2 — make the package public (Eric runs, one-time)**

```bash
# Eric runs after the first successful publish:
gh api --method PATCH \
  /orgs/MagneticAnomaly/packages/container/prep-headless/visibility \
  -f visibility=public
```
(or via UI: Packages → prep-headless → Package settings → Change visibility → Public).

- [ ] **Step 6: Verify an unauthenticated pull + entrypoint**

```bash
docker logout ghcr.io
docker pull ghcr.io/magneticanomaly/prep-headless:cpu          # must succeed unauthenticated
docker run --rm ghcr.io/magneticanomaly/prep-headless:cpu sync-headless --help   # expect CLI help
```

> **Do NOT** publish via `git tag app-v...` — it also triggers `release.yml`'s full Tauri desktop release (macOS+Windows signing, draft GitHub Release). If a versioned image tag is ever wanted, decouple the two workflows first (e.g. give the image workflow a distinct `img-v*` prefix).

---

## Task 6: Surface sync status in the dashboard (MVP-minimal)

**Category:** feature-gap. `SyncStatusCard` exists and is exported from `@prep/ui`, but is **never rendered** in the dashboard; the compact `TeamSyncIndicator` already renders in the header (`App.tsx:1299`) fed by `projectStatus?.sync`, so the read-side data pipe already works. There is **no "Sync Now" trigger endpoint** — `RemoteSyncService.check_and_sync()` is not exposed on any route.

**Files:**
- Modify: `src/prep/api/routers/projects/watch.py` (add `POST /projects/{id}/sync/now`)
- Modify: `src/prep/server.py` (bind `_get_project_syncer`, next to `_get_project_sync_status` ~L421)
- Modify: `src/prep/dashboard/src/App.tsx` (or a global settings page) to render `SyncStatusCard`
- Test: `tests/test_team_sync_integration.py`

- [ ] **Step 1: Write the failing endpoint gate test**

Add a test hitting `POST /projects/{id}/sync/now` via the FastAPI `TestClient`: assert a free-tier caller gets the feature-gate error envelope (402/`FeatureGateError`) and a Team-tier caller gets 200 with a status dict. Model it on the existing `TestAPIIntegration` client fixture in the file.

- [ ] **Step 2: Run it to verify it fails (404 — route doesn't exist)**

Run:
```bash
.venv/bin/pytest "tests/test_team_sync_integration.py" -k "sync_now" -v 2>&1 | tail -10
```
Expected: FAIL (route not found).

- [ ] **Step 3: Add the gated, non-blocking Sync-Now endpoint**

In `src/prep/api/routers/projects/watch.py` (`require_feature` already imported at L13):
```python
@router.post("/projects/{project_id}/sync/now")
async def trigger_project_sync(project_id: str) -> Dict[str, Any]:
    """Force an immediate team-index sync (Team tier)."""
    require_feature("team_config")
    srv = _srv()
    proj = srv._require_project(project_id)
    syncer = srv._get_project_syncer(proj)
    import asyncio
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, syncer.check_and_sync)   # S3 I/O off the event loop
    return ok(syncer.status_dict())
```
In `src/prep/server.py`, next to `_get_project_sync_status` (~L421):
```python
def _get_project_syncer(project: Project) -> Any:
    from prep.services.project_helpers import get_project_syncer
    return get_project_syncer(project, _project_syncers)
```

- [ ] **Step 4: Render `SyncStatusCard` (MVP: reuse an existing global page)**

`projectStatus.sync` is already in `App` scope. Add to an existing global settings page (`License.tsx` or `Integrations.tsx` — cheapest) rather than a new route:
```tsx
<SyncStatusCard
  status={projectStatus.sync}
  onSyncNow={async () => {
    await fetch(`/projects/${selectedProjectId}/sync/now`, { method: "POST" });
    // header TeamSyncIndicator refreshes on the next /status poll
  }}
/>
```
`SyncStatusCard` returns `null` when `status.enabled` is false, so it self-hides for non-team projects.
> **Scope note:** there is **no in-app "connect to team" flow** today (team config is a committed file; S3 creds come from `PREP_S3_*` env). An in-dashboard API-key/S3-credential input is a separate secrets-handling feature — **explicitly deferred** (P2-6), not part of MVP.

- [ ] **Step 5: Verify**

Run:
```bash
.venv/bin/pytest tests/test_team_sync_integration.py -q 2>&1 | tail -6
cd packages/ui && npm run typecheck && cd -
cd src/prep/dashboard && npm run typecheck && cd -
```
Expected: pytest green; both typechecks pass. Then **restart the daemon** and click through the settings page live (card renders for a team-enabled project; "Sync Now" issues the POST; header indicator updates on next poll).

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/projects/watch.py src/prep/server.py \
        src/prep/dashboard/src tests/test_team_sync_integration.py
git commit -m "feat(phase06): team-sync 'Sync Now' endpoint + render SyncStatusCard in dashboard"
```

---

## Task 7: Fix stale docs + final green-suite gate

**Files:**
- Modify: `docs/Phase06_Team_And_Enterprise/PROGRESS.md`
- Modify: `docs/superpowers/plans/2026-07-18-teams-sync-handoff.md`

- [ ] **Step 1: Correct the false "done/green" claim**

In `PROGRESS.md`, replace the "69/69 pass, 0 regressions" claim and the `[x]` "all tests pass" checkboxes with the real post-Task state and a pointer to this plan.

- [ ] **Step 2: Mark the greenfield handoff superseded**

At the top of `2026-07-18-teams-sync-handoff.md`, add a banner: `> SUPERSEDED by docs/Phase06_Team_And_Enterprise/TEAMS_SYNC_REVIVE_PLAN.md — Teams Sync is ~65% built, not greenfield. This doc's architecture is the target vision; see the revive plan for actual state.` Correct the "$30/seat Enterprise" reference to "$24/seat".

- [ ] **Step 3: Final gate — full team-sync suite green**

Run:
```bash
.venv/bin/pytest tests/test_remote_sync.py tests/test_layered_index.py \
  tests/test_headless_runner.py tests/test_s3_storage.py \
  tests/test_team_sync_integration.py -q 2>&1 | tail -5
```
Expected: **0 failed**. This is the MVP exit criterion for the code side (image publish in Task 5 is Eric-gated).

- [ ] **Step 4: Commit**

```bash
git add docs/Phase06_Team_And_Enterprise/PROGRESS.md docs/superpowers/plans/2026-07-18-teams-sync-handoff.md
git commit -m "docs(phase06): correct stale team-sync claims; mark greenfield handoff superseded"
```

---

## MVP Definition of Done

1. `tests/test_{remote_sync,layered_index,headless_runner,s3_storage,team_sync_integration}.py` all green (Tasks 1,2,3,4,6).
2. License-gate bypass on `/status` closed (Task 3).
3. `strip_source_content` capability landed + tested; content-strip policy set per the BYO/hosted decision (Task 4).
4. Headless image published to GHCR and **pullable unauthenticated** (Task 5 — Eric runs the publish).
5. Dashboard shows sync status + "Sync Now" works live against a restarted daemon (Task 6).
6. Stale docs corrected; handoff marked superseded (Task 7).

> **What MVP deliberately does NOT do:** per-commit index caching, correct-index-for-your-commit fetching, up-to-date *graph* context for locally-edited files, push-triggered auto-indexing, and in-app team onboarding. Those are real limitations — document them in the Teams tier's "known limitations" so early customers aren't surprised. They are the Phase-2 backlog below.

---

## Important TODO — Phase 2 backlog (the full handoff vision + hardening)

Ordered by leverage. Each is a **separate plan** when picked up (do not micro-step them here). Effort in T-shirt sizes.

### Correctness / the "hard parts" the handoff describes
- **P2-1 — Commit-addressable artifacts (M–L).** Today one mutable `index.zip` per prefix overwrites on every push. Implement `s3://[bucket]/[project-id]/[branch]/[commit-hash].tar.zst` + a `latest.json` branch pointer + `.tar.zst` (zstd) compression, and add a `--commit` checkout to `headless_runner._clone_repo` (currently clones branch *tip*, not the pushed SHA). Unlocks per-commit caching, rollback, and correct manifest↔bytes agreement. *Handoff §3.1(1), §3.2.*
- **P2-2 — git-HEAD detection + git-diff delta (L).** The client sync trigger is a filesystem watcher, not git. Add `.git/HEAD` change detection + `git diff` vs the remote commit to compute changed files, and **fix the delta-build being unreachable for trace-enabled projects** (`watch.py` `trigger_build` returns via the pipeline orchestrator before the delta branch, so local edits go to the MAIN index and `local_deltas/` never populates — the exact projects this feature targets). *Handoff §3.3, §4 Phase C.*
- **P2-3 — Base + Overlay GRAPH split (XL).** The embedding merge is real, but there is no `LayeredTraceIndex`; graph/trace queries hit only the remote base, so agents get **stale graph context for locally-changed files**. Build the read-only-base + read-write-overlay graph with dedup. This is the single largest deferred piece. *Handoff §4 Phase C item 1.*
- **P2-4 — Client working-tree content hydration (M).** Companion to Task 4: when `strip_source_content` is ON, the client must re-hydrate `content` from the working tree (line-slice via each doc's `span`, reconcile against `file_hash`, fall back to empty on drift; handle `span=None` synopsis chunks). **Required before any SourcePrep-hosted-bucket / hosted-Teams launch.** *Handoff §5.*

### Distribution / infra
- **P2-5 — GitHub webhook listener + GitLab CI (M).** The handoff's §2.1 "trigger indexing on push" webhook **does not exist** (`github_webhook.py` is unrelated roadmap plumbing; push-trigger is currently delegated to GitHub Actions `on: push`). Add a real push-webhook listener and a `.gitlab-ci.yml` template (the latter is required for the Enterprise air-gap story). *Handoff §2.1, §5.*
- **P2-6 — Team API key + hosted proxy (L).** Auth today is raw S3 creds handed to every dev (no "Team API key" concept exists). For hosted Teams, add a scoped Team API key + the proxy API the handoff posits, so credentials are centrally revocable. Includes the in-app "connect to team" onboarding UI deferred from Task 6. *Handoff §3.2, §4 Phase B.*

### Hardening (from the Mar-2026 code audit + gap analysis)
- **P2-7 — Security + reliability backlog (S–M each).** SEC-1 Docker images run as root (add non-root `USER`); SEC-2 deprecate CLI secret flags; SEC-3 add auth to the Modal webhook; SEC-4 remove the redundant soft license gate in `HeadlessRunner`; **stop_polling on Team→Free downgrade** (deferred from Task 3); S3 download content-hash mismatch should **abort/rollback, not warn** (currently the bad index is already swapped in before the check). *Audit `TEAM_ENTERPRISE_CODE_AUDIT.md` + gap analysis.*
- **P2-8 — Model defaults + multi-model headless (S/M).** MODEL-1: bump headless defaults off `qwen3:4b` (below quality floor) to `qwen3.5:9b`. ARCH-1: add `--fast-model`/`--reasoning-model` so teams don't pay reasoning prices for JSON-extraction stages.
- **P2-9 — Real end-to-end test coverage (M).** `HeadlessRunner.run()`, `S3StorageProvider.download_index()` (incl. zip-slip), the polling loop, and the real delta build are all untested or mocked-at-the-seam; `TestWatcherDeltaRouting` re-implements the routing inline instead of calling the real `watch.py trigger_build`. Add at least one test per seam that does **not** mock the seam under test (repo rule).
- **P2-10 — Config unification + rename-hardening (S/M).** ARCH-2: `team_config.json` is parsed by two non-overlapping loaders (`core/team_config.py` ignores the `sync` section; `remote_sync.py` reads only it) — unify. Add an exported `EMBEDDED_DIR_NAME = ".sourceprep"` constant routed through `project_registry`/`remote_sync`/`team_config` so the `.runprep`-style rename-rot (Tasks 1–2) can't recur.

---

## Self-Review (performed against the handoff spec + gap analysis)

- **Spec coverage:** handoff §3.1 headless indexer → exists (Task 5 publishes it) + P2-1 (commit checkout); §3.2 S3 layer → exists, Task 4 (privacy) + P2-1 (path scheme); §3.3 local sync/delta → exists for embeddings, P2-2/P2-3 (git-diff + graph overlay); §4 Phase A → Task 5; §4 Phase B → Task 6 + P2-6; §4 Phase C → P2-2/P2-3; §5 privacy → Task 4 + P2-4; §2.1 webhook → P2-5. Every spec section maps to an MVP task or a Phase-2 item.
- **Placeholder scan:** MVP tasks carry complete, verified code (extracted from the actual current source, not summaries). Design-open points (BYO-vs-hosted, namespace A/B) are explicit decision gates, not vague TODOs.
- **Type/name consistency:** `strip_source_content` (S3Config field + upload param + scrub fn) used consistently; `_get_project_syncer` binding matches `get_project_syncer(proj, _project_syncers)`; `check_feature("team_config")` matches the tier key in `feature_gate.py:60`.

---

## Execution Handoff

Plan complete and saved. **No code has been changed** (this is a plan only). Two execution options when you're ready:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks. Fast iteration, isolated blast radius.
2. **Inline Execution** — execute tasks in-session with checkpoints.

Before executing Task 4, confirm the **BYO-bucket vs SourcePrep-hosted** MVP decision. Before Task 5's publish/visibility steps, those are **yours to run** (explicit CI/registry actions).

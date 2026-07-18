# Feedback — Concept pipeline audit (external dogfood report)

**Date:** 2026-07-11
**Source:** Adversarial verification of the concept-generation pipeline against current `main`, triggered by a real degraded run observed in a downstream consumer project (the Applivation repo, 2026-07-11).
**Method:** 7-agent verification workflow — 6 concern verifiers + 1 completeness critic — each reading the exact source files and returning a `file:line`-cited verdict (`CONFIRMED` / `PARTIAL` / `REFUTED`). Load-bearing evidence for the confirmed bugs was spot-checked against source by the author before publishing.
**Verifier model:** `glm-5.2:cloud` (an `opus` override was requested but not honored by the workflow harness). Findings stand on their source citations, not on the model; the three publish-critical claims (C1, C4, C5) were re-read in source by the author.

This is an external feedback report, not a phase doc. Each finding is independently actionable. Statuses here are the audit's, not the pipeline's.

---

## TL;DR

| # | Finding | Verdict | Severity |
|---|---|---|---|
| C1 | Swarm synthesis failure silently degrades the index to raw worker rationales — no retry, no signal, no provenance | **CONFIRMED** | bug |
| C2 | Worker "clarifying questions" have a thin REST consumer but no MCP surface and no feedback into generation — they accumulate as a near-orphan dump | **PARTIAL** | loose-end |
| C3 | No MCP tool to list/read/answer concept questions; the ambient trailer actively misleads ("Use prep_concepts to explore") | **CONFIRMED** | loose-end |
| C4 | `concept_generate_manifest.json` records no health field and writes `completed_at` unconditionally — degraded runs look clean and the next run's freshness check locks in the failure | **CONFIRMED** | bug |
| C5 | No provenance field distinguishes synthesis-fallback rationales from synthesized ones; `prep_search` L2/file-context paths surface them undifferentiated | **PARTIAL** | loose-end |
| C6 | 1699 → 26 → 16 count discrepancy and "Pass4 0 gated" | **REFUTED** | by-design |

Plus 9 additional findings from the completeness critic (§4): one category-remap bug, a sticky-failure bug distinct from C4, a terminal `triage_pending` state, human-edit clobbering on re-run, stale `.f67_pending` backups, non-deterministic dedup tie-breaks, unguarded `prompt_revision` drift, dead code, and a missing MCP curation write-path.

### Priority order (suggested)
1. **C4 + critic-2** (sticky degraded run): a 0-candidate or failed-save Generate run writes a fingerprint-matching manifest, so the *next* run skips Generate entirely. Self-healing never happens without `force=True`. Highest impact — silently bricks the concept index across runs.
2. **C1** (silent fallback): a timed-out synthesis pass reports `status="success"` and feeds degraded `module_rationale` rows into the downstream synthesizer, which has no idea its input is fallback-quality. No provenance, no retry, no user-visible signal.
3. **C5** (unfiltered context injection): `prep_search` L2/file-context surface raw fallback rationales as if they were curated concepts. The primary `prep_concepts` surface is safe; this is the leak.
4. **C3 + critic-9** (MCP curation gap): the product's stated model is AI-assisted curation, but MCP can only read concepts — not list/answer questions, not promote, not archive. The ambient trailer is actively wrong.
5. **C2** (questions near-orphan): decide whether the question→answer→concept loop is a real feature (then wire MCP + feedback into generation) or scaffolding (then cap emission at the synthesizer, not per-worker).
6. The remaining critic findings (§4) — clobber-on-rerun, `triage_pending` terminal state, dead code, non-determinism, prompt-revision drift, `.f67_pending` cleanup.

---

## How this was produced

A downstream consumer project ran the concept pipeline and observed, in its log:
```
WARNING [prep.core.concept_seeder] [Swarm/Concepts] Synthesis pass produced no concepts;
merged 1699 concepts and 1220 questions from 738 worker outputs as a fallback.
To recover the synthesis pass, increase the swarm wall-time budget for the configured cloud model.
```
with `concept_generate_manifest.json` showing only `{rationale_count: 1700, candidates_after_dedup: 26, prompt_revision: 2, swarm_size: 3, completed_at: …}` — no signal that anything had degraded. That raised six concerns, each verified against source here.

---

## §1 Confirmed bugs

### C1 — Swarm synthesis fallback is silent, terminal, and unprovenanced

**Files:** `src/prep/core/concept_seeder.py`, `src/prep/core/concept_synthesizer.py`, `src/prep/services/concept_store.py`

**What happens:** When the swarm's synthesis pass produces no concepts, the code falls back to merging raw per-module worker outputs with best-effort title-only dedupe — no cross-module pattern extraction, no global invariants, no question synthesis. It then:
- persists those raw outputs with the **identical schema** as a successful synthesis run (`concept_seeder.py:953-954` sets `kind="module_rationale"` for both paths),
- returns `status="success"` unconditionally (`concept_seeder.py:1001-1012`) — **no `synthesis_failed` / `fallback` flag**,
- records the failure only as a `concepts_synthesis_failed` telemetry event (`concept_seeder.py:917-938`) — **grep across `src/prep` finds zero consumers of that event**,
- and does **not retry**. The fallback is terminal for the run.

The downstream cross-cutting synthesizer (`concept_synthesizer.py:262-281`) then reads *all* `module_rationale` rows as grounding input with no awareness that the swarm synthesis failed, so the degradation propagates silently into the curated `kind="concept"` layer.

**Evidence:**
- `concept_seeder.py:885` — `synthesis_was_empty = not final_concepts`
- `concept_seeder.py:889-916` — the fallback merge (title-only dedupe) + the verbatim warning
- `concept_seeder.py:1001-1012` — return dict hardcodes `"status": "success"`, no fallback field
- `concept_seeder.py:917-938` — `concepts_synthesis_failed` telemetry event; no code consumer (grep-verified)
- `concept_seeder.py:953-954` — `entry.setdefault("kind", "module_rationale")` on both paths, no provenance field added
- `concept_store.py:119-145` — `Concept` schema has no provenance/origin/source field; only `kind ∈ {concept, module_rationale}` and `status` discriminate
- `concept_synthesizer.py:262-281` — reads `module_rationale` rows as grounding, no fallback-awareness check

**User impact:** A consumer whose swarm synthesis times out (the documented failure mode is a cloud-model wall-time exhaustion; `synthesis_timeout_s` defaults to 600s at `concept_seeder.py:679`) gets an index silently built from unvetted per-module dumps. The run reports "success" and "N module rationale entries seeded"; the only signal is a log WARNING a user running via the app/MCP never sees. They cannot tell whether their concept index is synthesis-quality or fallback-quality, and it never self-heals.

**Suggested fix:**
1. Add `synthesis_failed: bool` / `fallback: bool` to the return dict (`concept_seeder.py:~1001`) and propagate it through the pipeline stage worker (`services/pipeline/workers/__init__.py:1631`) so the dashboard/MCP can show a degraded badge.
2. Write a swarm-synthesis manifest (analogous to `concept_synthesizer.py:702-708`'s `concept_synthesis_manifest.json`) recording `swarm_synthesis_failed: true` + `fallback_concepts` count; have `concept_synthesizer.py`'s grounding loader read it so the downstream synthesizer knows its input is degraded (and can warn or skip).
3. Add a `provenance` column to the concept schema (`concept_store.py` Concept dataclass + idempotent `ALTER TABLE` in `_create_tables`): values `swarm_synthesis` vs `swarm_fallback`. Set it on the fallback path. (See also C5.)
4. Retry the synthesis pass once before falling back — the failure mode is a wall-time timeout that may succeed on a second attempt with a warmed cache.

### C4 — `concept_generate_manifest.json` hides degraded runs and locks in the failure

**Files:** `src/prep/core/concept_generate_swarm.py`

**What happens:** The Generate swarm writes its freshness manifest with **no health field** and writes `completed_at` **unconditionally** — including when every worker failed (`candidates_after_dedup=0`) or when `save_many` raised. The `GenerateSwarmReport` dataclass carries `failed_workers` and `skipped_fresh`, and the `generate_swarm_complete` telemetry event records `failed_workers` — but none of these reach the manifest. Because the freshness short-circuit decides whether to skip the *next* run purely on `rationale_count` + `rationale_max_updated_at` + `prompt_revision`, a degraded run that wrote a fingerprint-matching manifest causes the next run to skip Generate entirely — locking in the degraded/empty concept set until the rationale layer changes or `force=True` is passed.

This contrasts with the sibling 125b writer (`concept_synthesizer.py:892`), which guards the manifest write on `report.saved > 0` and on LLM/parse failure returns early *without* writing the manifest. 125c has no equivalent guard.

**Evidence:**
- `concept_generate_swarm.py:319-326` — the only manifest write call site; six fields, none health-related
- `concept_generate_swarm.py:89-98` — `_write_gen_swarm_manifest` is a best-effort pass-through, no filtering
- `concept_generate_swarm.py:120,131` — `failed_workers` and `skipped_fresh` exist on the report but are not in the manifest payload
- `concept_generate_swarm.py:338-351` — `generate_swarm_complete` telemetry event *does* record `failed_workers`, proving the data exists at write time and is dropped
- `concept_generate_swarm.py:311-312` — `save_many` failure is logged but execution continues to write `completed_at` anyway
- `concept_generate_swarm.py:191-227` — freshness short-circuit skips on fingerprint match with no candidate-count or health check
- `concept_synthesizer.py:892-899` — the 125b guard 125c lacks

**User impact:** A degraded Generate run (cloud flake, worker timeouts, `save_many` `SQLITE_BUSY`) leaves the dashboard showing the stage as completed-clean, and the *next* run skips Generate because the rationale fingerprint is unchanged. The user sees no concepts and no error — only a stale `completed_at`. Recovery requires `force=True` or deleting the manifest, neither discoverable from the manifest itself.

**Suggested fix:** In `concept_generate_swarm.py` around line 317, mirror the 125b guard:
1. Add a `status` field: `"success"` when `candidates_after_dedup > 0` and save succeeded; `"degraded"` when `failed_workers` is non-empty or `save_many` raised; `"empty"` when `candidates_after_dedup == 0`.
2. Include `failed_workers` and `saved`/`skipped` in the payload.
3. Gate freshness eligibility on health — either (a) skip writing the manifest when `candidates_after_dedup == 0` (mirroring `concept_synthesizer.py:892`), so the next run retries; or (b) write the manifest with `status: "degraded"` and have the freshness check at `191-227` refuse to short-circuit when `manifest.get("status") != "success"`. Option (b) preserves the fingerprint for debugging while preventing stale-skip propagation.

---

## §2 Partial / loose-ends

### C2 — Clarifying questions are a near-orphan: persisted, barely consumable, never fed back

**Files:** `src/prep/core/concept_seeder.py`, `src/prep/services/concept_store.py`, `src/prep/api/routers/concepts.py`, `tests/test_concept_seeder_worker_questions.py`

**What happens:** The worker prompt (`concept_seeder.py:195-208`, `781-792`) invites 0-2 clarifying questions per module, stating they "are kept even if the downstream synthesis pass fails or times out." Questions **are** persisted (`concept_store.py:342-353` creates `concept_questions`; `concept_seeder.py:408-417` single-call, `980-991` swarm). A thin consumer **does** exist: a REST `GET /projects/{id}/concepts/questions` list endpoint and `POST /projects/{id}/concepts/questions/{qid}/answer` that promotes an answer to an `active` `kind="concept"` row (`routers/concepts.py:233-283`, calling `concept_store.answer_question` at `concept_store.py:1280-1296`).

But: there is **no MCP tool** to list or answer questions (see C3). There is **no feedback loop into generation** — `_assemble_seeding_context` (`concept_seeder.py:1096-1198`) reads only `atlas.json`, `trace_modules.jsonl`, and `audit/findings.json`; it never reads `concept_questions`, and neither worker prompt injects existing questions. So at swarm scale a run produces ~1000-1220 questions that land in the table and are reachable only via per-question HTTP POST. The only signal an MCP-attached user sees is a "1220 questions pending" count in the ambient block — noise, not an actionable backlog.

This is **PARTIAL** (not REFUTED) because the answer→concept REST endpoint is a genuine consumer. It is a loose-end because the loop is unwired from both the agent surface and the generation loop.

**Evidence:** `concept_seeder.py:195-199, 781-785` (prompt), `408-417, 980-991` (save), `concept_store.py:342-353, 1238-1296` (store + answer), `routers/concepts.py:233-283` (REST endpoints), `concept_seeder.py:1096-1198` (no read-back), `tests/test_concept_seeder_worker_questions.py:26-48` (tests emission only; no consumer test).

**User impact:** Hundreds-to-thousands of accumulated questions, actionable only via per-question HTTP POST, never sharpening later rationale extraction.

**Suggested fix:** Pick one direction and commit.
- **If the loop is a real feature:** add an MCP `prep_concepts action="questions"`/`"answer"` (see C3), and inject the N highest-priority unanswered questions into `_assemble_seeding_context` / the worker prompt so the act of asking feeds the next run.
- **If scaffolding:** cap or sample questions in the worker prompt (emit from the synthesizer, not per-module workers) so a 600-worker run does not dump 1200 rows nothing drains.

### C3 — No MCP surface for concept questions; the ambient trailer actively misleads

**Files:** `src/prep/mcp_tools.py`, `src/prep/mcp/server.py`, `src/prep/mcp_direct.py`, `src/prep/api/routers/concepts.py`

**What happens:** The single concept-domain MCP tool, `prep_concepts` (`mcp_tools.py:385-473`; dispatched `mcp/server.py:4490-4505`), exposes only `action ∈ {get, save}` on concept rows. Its `inputSchema` has no question/question_id/unanswered_only parameter; `tool_concepts` (`mcp/server.py:2014-2206`) never calls `store.list_questions` or `store.answer_question`. The two question REST endpoints (`routers/concepts.py:233, 248`) have zero MCP counterparts. The only question signal that reaches MCP is a bare **count** in the ambient trailer (`mcp/server.py:1408, 1446`): `"{N} questions pending. Use prep_concepts to explore."` — a tool that cannot explore questions. (The "Open Questions" block at `mcp/server.py:2987-3025` is a red herring — it draws from the goalposts API, not `concept_questions`.)

Secondary latent bug: `mcp_direct.py` advertises `prep_concepts` in `TOOLS` but its `handle_tools_call` (`419-461`) has no `prep_concepts` branch, so direct mode raises `MethodNotFoundError("Unknown tool")` — it can't even execute the concept get/save that server mode can.

**Evidence:** `mcp_tools.py:385-473` (action enum get/save only), `mcp/server.py:4490-4505, 2014-2206` (no question calls), `routers/concepts.py:5` (docstring claims MCP coverage), `:233-245, 248-283` (REST-only endpoints), `concept_store.py:1238, 1263, 1280` (implemented but REST-only), `mcp/server.py:1408, 1446` (misleading trailer), `mcp_direct.py:419-461` (no prep_concepts dispatch).

**User impact:** An MCP-attached agent sees "M questions pending. Use prep_concepts to explore" on every `prep()` call but cannot read or answer them through MCP. The agent must tell the user to open the dashboard, breaking the agentic loop. The trailer line is actively wrong.

**Suggested fix:** Extend `prep_concepts` with `action="questions"` (list, with `unanswered_only`) and `action="answer"` (POST to the existing endpoint, create an active concept). Add the dispatch in both `mcp/server.py` and `mcp_direct.py` (which currently has no `prep_concepts` branch at all). At minimum, correct the trailer copy at `mcp/server.py:1446` so it stops claiming question access via `prep_concepts` until the wiring lands. No store-layer changes needed — `list_questions`/`answer_question` already exist.

### C5 — No provenance field; `prep_search` L2/file-context surface fallback rationales undifferentiated

**Files:** `src/prep/services/concept_store.py`, `src/prep/core/concept_seeder.py`, `src/prep/mcp/server.py`, `src/prep/core/audit/antibody_derivation.py`

**What happens:** The concept record has **no provenance/origin field** — only `kind` (layer) and `status` (lifecycle). When synthesis fails, the fallback path saves raw worker outputs with the same `kind="module_rationale", status="seed"` as synthesis-success entries. The only record is a telemetry log, not a per-row field.

`triage_pending` is **not** a fallback marker — it is a promotion-gate result on `kind="concept"` (the curated layer): set by `run_pass4_gate` (`concept_promotion_pipeline.py:187-223`, confidence in [0.65, 0.90)) and by the Validate swarm (`concept_validate_swarm.py:154-162`, T1 verdict via `concept_validate_prompt.py:308`). Fallback rationales are `kind="module_rationale"` and never receive `triage_pending` unless separately lifted. **The `triage_pending` tags observed in the downstream consumer's `prep_concepts` output are synthesized `kind="concept"` entries that got a T1 Validate verdict — not fallback rationales. That part of the original observation was a misattribution.**

Consumer exposure is split:
- **Safe:** `prep_concepts` MCP and REST default `kind="concept"` (`concept_store.py:1010`, `routers/concepts.py:154`). Antibody derivation filters `kind="concept"` (`antibody_derivation.py:96-98`). Fallback rationales are invisible here.
- **Unsafe:** `concept_store.search` (`concept_store.py:1066`) and `get_for_anchors_directory` (`concept_store.py:1106`) have **no `kind` parameter** — confirmed in source: both return ALL concepts regardless of kind, filtering only on `status != 'archived'`. The MCP L2 scoped-context path (`server.py:1531-1538`) renders results as `- **{title}** ({category}): {preview}` with no kind/status tag, and the file-context path (`server.py:2593-2594`) surfaces titles with no provenance marker. Fallback rationales appear alongside active concepts with zero distinction. The synthesizer grounding (`concept_synthesizer.py:262-281`) reads all `module_rationale` rows including fallback ones.

**Evidence:** `concept_store.py:119-146` (no provenance field), `:88-98` (`triage_pending` is a Pass-3/Pass-4 result), `:1010` (`list_concepts` defaults `kind="concept"`), `:1066-1072` (`search` — no kind param), `:1106-1113` (`get_for_anchors_directory` — no kind param), `concept_seeder.py:889-916` (fallback), `concept_promotion_pipeline.py:187-223` (Pass4 triage band), `concept_validate_swarm.py:13-14, 154-162` (Validate T1 → triage_pending), `server.py:1531-1538, 2593-2594` (unfiltered rendering), `antibody_derivation.py:96-98` (safe path).

**User impact:** A user will not see fallback rationales in `prep_concepts` (safe). But when an agent calls `prep_search` with a `working_dir` (L2) or when file-context is assembled, fallback rationales surface as undifferentiated "Concepts for dir/" entries. In a large run where synthesis failed and 1699 raw rationales were merged, these paths can flood the agent with low-quality entries that look like authoritative design decisions, and those same rationales shape the curated layer as synthesizer grounding.

**Suggested fix:**
1. Add a `provenance` field to the concept schema (dataclass + idempotent `ALTER TABLE`): `synthesized` / `fallback_merge` / `manual` / `imported`. Set `provenance="synthesized"` on the success path (`concept_seeder.py:953-956`), `provenance="fallback_merge"` on the fallback path (`:889-916`). Lighter-touch alternative: tag `synthesis_fallback=1` in the `tags` array.
2. In the `prep_search` L2 path (`server.py:1531-1538`) and file-context path (`server.py:2593-2594`), either (a) filter to `kind="concept"` only, matching the `prep_concepts` surface, or (b) render a provenance/quality tag (e.g. `[rationale]` vs `[concept]`) so the agent can weight them differently.
3. Have `concept_synthesizer.py:262-281` weight or filter fallback rationales when loading grounding, or at minimum log how many grounding inputs are `fallback_merge` so synthesis-quality degradation is visible.

---

## §3 Refuted / by-design (recorded so it is not re-litigated)

### C6 — 1699 → 26 → 16 and "Pass4 0 gated" — REFUTED, by-design

**Verdict: REFUTED.** The counts are cleanly explained by the two-layer architecture and documented status semantics; nothing is mysteriously dropped.

- The **1699** are the `kind="module_rationale"` layer (capped at 2000/project, `concept_store.py:60-63`), **not** surfaced by `prep_concepts`.
- The **26** are `kind="concept"` rows saved after Validate. Validate's `reconcile_tier` (`concept_validate_prompt.py:288-310`) assigns only `active` / `triage_pending` / `archived` — never `seed`.
- The **16** surfaced by `prep_concepts` are the non-archived `kind="concept"` rows (`concept_store.py:1002-1055` defaults `kind="concept"`, `include_archived=False`). **26 − 16 = 10 archived** (Validate REJECT / parse-fail candidates).
- **"Pass4 0 gated: active=0, triage=0, archive=0"** is the expected no-op: `run_pass4_gate` defaults `status_filter="seed"` AND `kind="concept"` (`concept_promotion_pipeline.py:400-456`). Since Validate assigns no `seed` statuses, `load_concepts_for_clustering` returns 0 rows. Pass4 only usefully fires when Generate runs standalone (`save=True`, no Validate chain), leaving T1 concepts at `seed`. In the normal Generate→Validate flow, Validate is the primary gate and Pass4 correctly has nothing to do — defense-in-depth (LLM critique primary, deterministic gate backstop).

The "several `triage_pending`" observed downstream are the T1-validated candidates awaiting human review — the intended queue, not a bug.

**Minor doc blemish only:** `concept_promotion_pipeline.py:414-416` (`run_pass4_gate` docstring) implies Validate leaves concepts at `seed`; it does not. Suggested reword: *"Pass4 gates concepts left at `seed` by Generate when it runs without chaining into Validate; in the normal Generate→Validate pipeline, Validate resolves every candidate to active/triage_pending/archived and Pass4 is a no-op."*

---

## §4 Completeness critic — additional findings beyond C1–C6

### 4.1 `"tradeoff"` category silently remapped to `"technical"` — BUG
`concept_synthesizer.py:436, 542-546, 625-627, 101-110`; `concept_store.py:73-85, 609-611`; `concept_validate_swarm.py:252`; `mcp_tools.py:417`.
The synthesizer system prompt and `VALID_CATEGORY_LIST` advertise `"tradeoff"`, so the LLM emits it. A comment at `625-627` claims normalization happens before save — it doesn't. `concept_store.VALID_CATEGORIES` excludes `"tradeoff"`, so `save_many` silently clamps it to `"technical"`. Any concept tagged `tradeoff` loses its category signal. Fix: either add `"tradeoff"` to `VALID_CATEGORIES` + the MCP enum, or actually normalize `tradeoff → decision` in `parse_synthesis_response`/`to_save_dict` (the comment's stated intent).

### 4.2 Generate manifest written on 0 candidates → sticky failure — BUG
`concept_generate_swarm.py:298-328, 191-227`.
Distinct from C4's framing: this is the *retry-on-next-run* consequence. `synthesize_concepts_swarm` writes the freshness manifest unconditionally after dedup/save, including `candidates_after_dedup=0`. The next run's freshness short-circuit skips Generate whenever rationale fingerprint + prompt_revision match, with no candidate-count check. A failed/empty Generate is never retried until the rationale layer changes or `force=True`. The failure becomes sticky. Fix: gate the manifest write behind `if report.candidates_after_dedup > 0`, or write with `status:"degraded"/"empty"` and have the freshness check refuse to short-circuit on a non-success status.

### 4.3 `triage_pending` is a terminal state — no auto-promotion path — LOOSE-END
`concept_promotion_pipeline.py:400-455, 213-216`; `services/pipeline/workers/__init__.py:1751-1755`.
`run_pass4_gate` defaults `status_filter="seed"` and the production worker passes no override, so only `seed` concepts are ever gated. Concepts that land in `triage_pending` are never re-read by the gate on subsequent runs. The only promotion path is manual: the HTTP `/approve` endpoint (`concepts.py:347`) or a human in the dashboard. There is no MCP approve action. `triage_pending` concepts accumulate indefinitely as stale state unless a human acts. This is the mechanism behind the C6 "Pass4 0 active" symptom: the gate's triage band is a one-way valve. Fix: widen the gate's default `status_filter` to include `triage_pending`, or add an MCP `approve` action + surface `triage_pending` in the `prep()` ambient trailer so a session can act on them, or document `triage_pending` as human-only and add a dashboard queue.

### 4.4 Pipeline re-runs silently clobber human edits on title collision — LOOSE-END
`concept_store.py:696-725, 488-518`; `concept_validate_swarm.py:249-258`.
`save_many` dedups by `(project_id, title, kind)` against non-archived rows; on collision it UPDATEs content/category/status/confidence/anchors/tags/cluster_id/assertion/doc_links with **no guard** detecting a human edit. If a user curates a concept (edits content, approves `seed→active`, sets a custom assertion) and a later run re-emits the same title (`force=True`, or rationale changed so Generate re-runs), the human edits are silently replaced and an approved `active` concept can demote back to `seed`/`triage_pending`. Additionally, archived concepts are excluded from dedup matching, so a re-emitted title previously REJECT-archived by Validate creates a brand-new row alongside the archived one — the rejection is not "remembered." Fix: add a `user_edited` flag (or `last_curated_at`) set by `update()`/`approve`, and have `save_many` skip the overwrite when the existing row is user-edited / curated more recently than the run. For archived re-emission, match against archived rows too and re-archive rather than duplicate.

### 4.5 `.f67_pending` manifest backups never cleaned up — LOOSE-END
`services/pipeline/orchestrator.py:2608-2627`; `services/pipeline/manifest_store.py:102-141`; `api/routers/trace_routes/enrichment.py:1547-1561`.
At stage start the current manifest is renamed to `<file>.f67_pending` (after unlinking any prior backup). On successful stage completion, `write_provenance` writes a fresh manifest to the real path but never deletes the `.f67_pending` backup. The backup is only removed by the next stage-start unlink or a full project reset. **Verified on disk: `/Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep` contains 13 stale `*.f67_pending` files** (atlas, trace, knowledge, antibodies, validation, …). The orchestrator comment (line 2606) says `.f67_pending` is no longer restored from, so immediate corruption risk is low, but `enrichment.py:1552-1553` warns a future selfheal pass could restore them and cause wrong-stage resume. Fix: after `write_provenance` succeeds, unlink the matching `.f67_pending` in the same completion path (or have `write_provenance` remove it as the last step of its atomic write).

### 4.6 `dedupe_swarm_outputs` is non-deterministic across runs — ENHANCEMENT
`concept_generate_swarm.py:257-278`; `concept_generate_dedup.py:134-170`; `concept_clustering.py:305-309`.
`all_concepts` is assembled from `as_completed(future_to_scope)`, which yields futures in non-deterministic thread-completion order. `dedupe_swarm_outputs` assigns `id=str(i)` by list index, and the cluster winner is `max(cluster_items, key=(TIER_TO_CONFIDENCE, len(anchors), len(title)))` — first item on ties. The clusterer's own tie-break is by opaque id string. So when two candidates tie on (tier, anchor_count, title_length), the survivor depends on which worker finished first. Two back-to-back runs with identical LLM outputs can silently drop different concepts — undermining reproducibility of the curated layer. Fix: sort `all_concepts` by a stable key (`(tier, title, tuple(anchors))`) before `dedupe_swarm_outputs`, and make the clusterer's tie-break deterministic on a content key.

### 4.7 `prompt_revision` is a hand-bumped constant with no drift guard; legacy synth manifest has none — LOOSE-END
`concept_generate_swarm.py:62-73, 198-206`; `concept_synthesizer.py:692-699, 752-758, 893-899`.
`_GEN_PROMPT_REVISION` (line 73, currently 2) is hand-maintained with a comment "Bump when…". If a developer edits `SYNTH_SYSTEM_PROMPT` or the banned list and forgets to bump it, the freshness check keeps skipping on the stale revision and the prompt change never takes effect — silent prompt-version drift. No test/CI checks the revision was bumped alongside a prompt diff. Separately, the legacy synthesizer manifest (`concept_synthesis_manifest.json`, written `concept_synthesizer.py:893-899`) has **no `prompt_revision` field at all**, so the synth path (still public API, listed in `trace_routes/shared.py ALL_DATA_FILES`) has zero prompt-drift protection — a stale synth manifest could cause `synthesize_concepts` to short-circuit (`752-758`) even after `SYNTH_SYSTEM_PROMPT` changed. Fix: add a CI lint that hashes the relevant prompt strings and fails if the hash changed but `_GEN_PROMPT_REVISION` did not; add a `prompt_revision` field (with its own constant) to the synth manifest payload + freshness check.

### 4.8 Dead code: `concept_promotion.py` + `concept_store._evict_oldest` — LOOSE-END
`src/prep/core/concept_promotion.py:1-73`; `src/prep/services/concept_store.py:1352-1389`.
`suggest_promotion` and `build_concept_from_observation` are not imported anywhere in `src/prep` (grep-verified). They produce `status="proposed"` concepts with a title derived by splitting content on `.`, but nothing wires observations into promotion — the real path is the four-pass pipeline + Validate. `_evict_oldest` is defined but never called; the live eviction path is `_evict_over_cap_for_kind` (line 1300, called at 535 and 687). These are pre-125b leftovers that can mislead maintainers into thinking observation→concept promotion or the global eviction path is active. *(Corroborates `docs/INTENTIONALLY_DORMANT.md`, which already lists `concept_promotion.py` as 0 production callers as of 2026-05-01.)* Fix: delete or move under `deprecated/`, or add a TODO referencing the phase that will wire observation→concept promotion if still planned.

### 4.9 MCP `prep_concepts` exposes no approve/promote/answer action — ENHANCEMENT
`mcp_tools.py:396-399, 469-471`; `routers/concepts.py:347-355, 248-283`.
`prep_concepts` exposes only `get`/`save`. The HTTP API has richer endpoints — `PATCH /concepts/{cid}/approve` (`seed→active`), `PATCH /archive`, `POST /concepts/questions/{qid}/answer` — but none are surfaced as MCP actions. A Claude session cannot promote a `triage_pending`/`seed` concept to `active`, archive a bad one, or answer a clarifying question via MCP. This is the write-side complement to C3: the curation loop is human-only even though the product's stated model is AI-assisted curation. Combined with 4.3, `triage_pending` concepts are invisible-and-immutable from an MCP session. Fix: extend `prep_concepts` with `action="approve"` / `"archive"` / `"answer_question"`, mapping to the existing endpoints; add the corresponding `inputSchema` fields.

---

## §5 Suggested follow-up

- The two bugs (C1, C4 + 4.2) share a root cause — **degraded runs are neither recorded nor recovered**, so a single transient failure becomes a silent permanent regression. A single "run health" field threaded from `concept_seeder` / `concept_generate_swarm` through the manifest and the freshness check would close C1, C4, and 4.2 together.
- C2 + C3 + 4.9 share a root cause — **the question→answer→concept loop is fully built at the store/API layer and fully absent at the MCP layer**, and the ambient trailer advertises it. One MCP extension to `prep_concepts` (questions/answer/approve/archive) closes all three and makes the trailer honest.
- C5 + 4.1 + 4.6 share a root cause — **provenance and determinism of the curated layer are unenforced**, so fallback/low-quality/non-reproducible entries leak into surfaces that trust the layer. A `provenance` field + a stable sort order + a `kind` filter on the L2/file-context paths closes the leak.

---

*Audit produced 2026-07-11 by an external consumer of SourcePrep. All findings are source-cited; the three publish-critical claims (C1, C4, C5) were re-read in source before publishing. Verifier agents ran on `glm-5.2:cloud` (an `opus` override was requested but not honored by the workflow harness); findings stand on their `file:line` citations, not on the verifying model.*
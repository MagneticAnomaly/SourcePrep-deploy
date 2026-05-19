# Custodian — Safety verification

**File:** `src/prep/agents/custodian/prompts.py:5-44` (render at 5, SYSTEM at 41)
**Symbols:** `SAFETY_VERIFICATION_SYSTEM`, `render_safety_verification_prompt`
**Invoked by:** Digital Custodian Agent — once per candidate for archival
**Pipeline stage:** agent (custodian)
**Output schema:** strict JSON `{classification: keep|archive|delete, reason}`
**Status:** baseline

## Purpose
Conservative dead-code classification. The Custodian agent uses this to decide whether a flagged file/symbol is safe to archive or delete vs needs to stay.

## Grounding (inputs)
- Candidate file/symbol
- Its trace-graph context (dependents, recent commits, test coverage)
- Optional reason it was flagged

## Output schema
Strict JSON. Three classifications, mandatory reason string.

## Known issues / hypotheses
- **Conservatism vs precision**: "conservative" framing pushes the model toward `keep` for ambiguous cases — which is safe but defeats the purpose. Hypothesis: rebalance to "be specific about *why* you're picking keep, so we can act on the reason."
- **Reason quality**: outputs may produce reasons like "uncertain — keep." That's not actionable. Worth requiring reasons to cite specific evidence (e.g., "imported by `foo.py:bar()`").
- **Test-coverage signal**: if a candidate has no test coverage, that's a strong archive signal — but it must be in the grounding for the model to use it. Verify.

## Snapshot 2026-05-17
- Prompt source SHA: `1062afc416cd`
- Outputs captured: TBD

## Iterations

### 2026-05-19: B5 — structural review + corrects page schema and open-question

**Type:** analysis-only (no PowerMate output captured; structural review of prompt + caller-known mechanism)

**Read materials:**
- `render_safety_verification_prompt` + `SAFETY_VERIFICATION_SYSTEM` (`agents/custodian/prompts.py:5-43`).
- `render_archive_readme` (`agents/custodian/prompts.py:45-63`) — non-LLM template for the archive directory README, not part of the audit.

**Correction to page (line 7) — output schema is wrong.** Page says: `{classification: keep|archive|delete, reason}` — lowercase, three values including `archive`. The actual prompt (line 39) requires:

```
{"classification": "SAFE_TO_DELETE" | "NEEDS_REVIEW" | "KEEP", "reason": "..."}
```

UPPER_SNAKE_CASE, no `archive` classification. **The page open-question #2 ("Does ban on `delete` (vs `archive`) make sense — i.e., should the prompt only ever produce keep/archive?") is moot** because the schema is the inverse: there is no `archive` value, and `SAFE_TO_DELETE` is the actionable "go ahead and delete" verdict.

Recommend updating the page's `## Output schema`, `## Known issues` (the open-question), and the `## Open questions` block.

**Finding #1 — the conservative bias is engineered via question structure, not just framing.** The page's hypothesis ("Conservatism vs precision — 'conservative' framing pushes the model toward `keep` for ambiguous cases") understates the structure. The prompt asks SIX yes/no questions designed to catch dynamic/string-based reachability:

```
1. Could this file be imported dynamically (importlib, __import__, exec)?
2. Could this file be referenced via string-based paths (config files, env vars)?
3. Is this file a public API entry point (exposed via __init__.py, __all__)?
4. Is this file part of a plugin system or extension mechanism?
5. Could this file be a CLI entry point, test fixture, or script?
6. Is there any reason a human might want to keep this file?
```

Then enforces the bias via a hard rule:

```
If ANY answer is "yes" or "uncertain", classify as NEEDS_REVIEW.
If ALL answers are "no", classify as SAFE_TO_DELETE.
Never default to SAFE_TO_DELETE if uncertain.
```

This is grounding §9 (Caulfield "attack the answer") executed correctly — instead of asking "is this safe to delete?", it asks 6 ways the file could be alive, and any positive answer flips the verdict. The conservatism is *structural*, not just persona-tone.

Question #6 is particularly clever ("Is there any reason a human might want to keep this file?") — it gives the model permission to be conservative about social/historical reasons (preserved-for-reference docs, regulatory artifacts, legacy contracts) that questions 1-5 don't cover.

**Finding #2 — `KEEP` is a third classification but unspecified when it applies.** The schema includes `KEEP` as distinct from `NEEDS_REVIEW`, but the prompt's decision logic only describes two paths (any-yes → NEEDS_REVIEW, all-no → SAFE_TO_DELETE). There's no path that emits `KEEP`. Two reads:
- **(a) KEEP is dead-letter and the schema should drop it.** Cleaner — two classifications, both actionable.
- **(b) KEEP is for the model to use when it has strong-positive evidence a file is alive** (e.g., "this is the main entry point cited in README — definitely keep"). The prompt should describe this case to give KEEP semantic weight.

I lean (b) — the existing custodian likely uses KEEP to short-circuit further review on obviously-alive files, but the current prompt doesn't tell the model when to use it. Recommend adding:

```diff
+If you have strong positive evidence the file IS alive (e.g., explicit
+entry point cited in docs/README, public API used by consumers, or
+critical infrastructure), classify as KEEP with reason citing the
+evidence. KEEP is for obvious cases; use NEEDS_REVIEW for everything
+ambiguous.
```

**Finding #3 — `reason` field is unconstrained.** Page hypothesis #2 ("Reason quality: outputs may produce reasons like 'uncertain — keep.' That's not actionable.") is the real risk. The prompt asks for a reason but does not constrain its shape (length, what to cite, whether to quote evidence). Page recommendation ("requiring reasons to cite specific evidence (e.g., 'imported by `foo.py:bar()`')") is correct. Concrete edit:

```diff
+REASON RULES:
+- Cite specific evidence. Good: "imported by foo.py:bar()". Bad: "uncertain".
+- For NEEDS_REVIEW: quote which of questions 1-6 triggered the verdict
+  (e.g., "Q1: file_path is referenced as string in src/loader.py:42").
+- For SAFE_TO_DELETE: cite that ALL six questions returned 'no' and
+  give the strongest negative evidence (e.g., "no imports, no string
+  refs in any config, no __init__ export, no CLI entry").
+- For KEEP: cite the positive evidence (e.g., "main entry point per
+  README setup section").
```

**Finding #4 — `dependent_count` is reliably grounded but the model may not weight it.** The prompt feeds `Dependents (static imports): {dependent_count} (should be 0)` — telling the model the expected value. If dependent_count is 0, that's a signal toward SAFE_TO_DELETE. If it's nonzero (the file IS imported), the conservatism should keep it as NEEDS_REVIEW even though the prompt's question 1 is about *dynamic* imports. Worth verifying the model doesn't auto-flip to SAFE_TO_DELETE on dependent_count=0 while ignoring questions 2-6.

**Verdict:** `analysis (no edit shipped this iteration).` Three deferred actions:
1. **Update page stub** for correct schema (SAFE_TO_DELETE | NEEDS_REVIEW | KEEP).
2. **Specify when KEEP applies** in the decision logic.
3. **Add REASON RULES** to constrain reason quality.

**Capture follow-up:** Need real Custodian output to validate findings #2 and #3. PowerMate is small (~30 files) — likely has 0-3 candidates for Custodian, so it's a thin test. SourcePrep self has more dead-code candidates and would give a richer sample.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (Caulfield falsification: the 6-question structure is a model implementation of "attack the answer, do not verify it" — each question is an attack vector on the proposed deletion).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §2 (Few-shot: would benefit from 2-3 graded examples — file-truly-dead, file-actually-alive-via-string-ref, file-alive-via-test-fixture).

**Cross-references:** [`hr-agents-md.md`](./hr-agents-md.md) (sibling agent prompt), [`researcher-topic.md`](./researcher-topic.md) (sibling agent — same prompt-quality category). Phase 122 custodian dogfood design doc referenced in page header.

## Open questions
- Should the prompt have a "confidence threshold" gate (only act on high-confidence classifications)?
- Does ban on `delete` (vs `archive`) make sense — i.e., should the prompt only ever produce keep/archive?

## Cross-references
- Phase 122-related dogfood doc: [`../../docs/superpowers/specs/2026-05-13-phase122-custodian-dogfood-design.md`](../../superpowers/specs/2026-05-13-phase122-custodian-dogfood-design.md)
- Sibling: [hr-agents-md](./hr-agents-md.md) (HR-side agent), [researcher-topic](./researcher-topic.md)

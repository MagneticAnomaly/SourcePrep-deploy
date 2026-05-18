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

_(none yet)_

## Open questions
- Should the prompt have a "confidence threshold" gate (only act on high-confidence classifications)?
- Does ban on `delete` (vs `archive`) make sense — i.e., should the prompt only ever produce keep/archive?

## Cross-references
- Phase 122-related dogfood doc: [`../../docs/superpowers/specs/2026-05-13-phase122-custodian-dogfood-design.md`](../../superpowers/specs/2026-05-13-phase122-custodian-dogfood-design.md)
- Sibling: [hr-agents-md](./hr-agents-md.md) (HR-side agent), [researcher-topic](./researcher-topic.md)

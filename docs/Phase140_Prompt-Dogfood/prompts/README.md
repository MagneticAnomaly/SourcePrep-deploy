# Prompt site pages

One markdown file per prompt site. Each page is a living research log: snapshot at the top, dated iteration blocks below, verdicts at the bottom of each block.

## Page template

Copy this when creating a new site page (or filling a stub):

```markdown
# <Prompt Name>

**File:** `src/prep/.../prompts.py:LINES`
**Symbols:** `<SYSTEM_CONST>`, `<build_user_prompt>`
**Invoked by:** `<worker / orchestrator file:func>`
**Pipeline stage:** fast | deep | synth | enrichment | audit | agent | rules
**Output schema:** JSON (with schema link) | structured-text | plain prose
**Status:** baseline | iterating | stable

## Purpose
One to three sentences. What the LLM is asked to produce and why it matters downstream.

## Grounding (inputs)
What context the prompt is fed. Examples:
- Atlas summary
- File contents (with byte limits)
- Audit findings
- Concept candidates
- Prior-pass enrichment

## Output schema
What we expect back. If JSON, link to the schema (file:line). If prose, describe the structure (headers, bullets, etc.).

## Known issues / hypotheses
Each item should cite a memory record, a prior phase doc, or a user-reported incident. If we don't know, write "unknown — needs baseline capture before hypothesizing."

## Snapshot 2026-05-17
- Prompt source SHA: `<12 chars>` (matches snapshot baseline if unchanged)
- Outputs captured:
  - Slot A (SourcePrep self): `../snapshots/2026-05-17_baseline/outputs/<slug>/sourceprep.json`
  - Slot B (small Py lib): TBD
  - Slot C (TS React): TBD

## Iterations

### YYYY-MM-DD: <change name>
- **Hypothesis:** what failure mode this addresses
- **Diff:** link to git commit or inline `diff`
- **Outputs:** path to new snapshot directory
- **Compared to baseline:**
  - bullet point
  - bullet point
- **Verdict:** kept | reverted | partial
- **Follow-ups:** what's left

## Open questions
- ...

## Cross-references
- Other site pages affected by the same finding
- Memory records cited above
- Prior-phase docs referenced
```

## Conventions

- **One change per iteration block.** Don't combine "tightened instructions" with "added few-shot examples" in one block — split them.
- **Diff format.** Use ` ```diff ` fenced blocks for short diffs. For long ones, link to the commit SHA and quote only the relevant hunk.
- **Output comparison.** Don't paste full LLM outputs into the page. Quote the relevant 3-5 lines and link to the full file under `snapshots/`.
- **Verdict words are vocabulary, not synonyms.** `kept` means in `main` and the change improved outputs against at least 2 repos. `reverted` means rolled back. `partial` means the hypothesis was partly confirmed and a follow-up iteration is queued.

## Index

See [`../01_Inventory.md`](../01_Inventory.md) for the master table linking to every site page and their current status.

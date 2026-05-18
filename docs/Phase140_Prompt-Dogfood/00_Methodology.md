# Methodology

The five non-negotiables, the snapshot protocol, the iteration loop, and the verdict gate. Every audit in Phase 140 follows this. If a methodology step feels inconvenient on a specific site, the right move is to update this doc — not to skip the step.

## Five non-negotiables

### 1. Snapshot before mutating
Before any prompt is changed, capture its current outputs against every test repo and commit them. Without a baseline, "did this prompt get better?" is unanswerable. The baseline directory is immutable — new snapshots get new dated subdirectories.

### 2. One prompt at a time
Single-site edits, rebuild only the affected pipeline stage, re-capture. Batched changes destroy attribution: if you change `concept-synthesize` and `concept-validate` together and the output improves, you cannot tell which change caused it (and worse, you cannot tell if one regressed while the other improved).

### 3. Verdict gate
Every iteration ends with one of three verdicts:
- **kept** — change is in `main`, baseline is updated for future comparisons
- **reverted** — change is rolled back, the iteration record stays as a learning
- **partial** — some hypothesis confirmed, more work needed; the next iteration block names it explicitly

There is no "interesting, will revisit." That's how research logs rot.

### 4. Multi-repo discipline
At minimum 3 repos so prompts don't overfit to SourcePrep's shape. See [`02_TestRepos.md`](./02_TestRepos.md) for the curated set. A prompt that produces beautiful output on SourcePrep itself and incoherent output on a small Python lib is a failed prompt, not a generalist tool.

### 5. Output capture as files
Outputs go in `snapshots/<date>_<label>/outputs/<site>/<repo>.{json,md}`. No screenshots, no "I think it looked better," no relying on memory. If we can't diff two outputs mechanically, we can't make defensible decisions about them.

## The snapshot protocol

A snapshot is an immutable record of "what the pipeline produces today." Structure:

```
snapshots/
└── YYYY-MM-DD_<label>/
    ├── README.md              # git SHA, env, per-file prompt SHAs, what's captured
    └── outputs/
        ├── <site>/
        │   ├── <repo-1>.json
        │   ├── <repo-2>.json
        │   └── <repo-3>.json
        └── ...
```

**Labels:**
- `baseline` — the first capture (2026-05-17_baseline). Never modified.
- `<site>-<verdict>` — after an iteration with `kept` verdict, capture a new snapshot with the site name and verdict, e.g. `2026-05-22_atlas-segment-kept`. This becomes the new comparison baseline for that site.

**What to record in the snapshot README:**
- Git SHA of the SourcePrep repo at capture time.
- Environment (Python version, daemon mode, embedder, cloud LLM model + version).
- SHA-256 (first 12 chars) of every prompt source file. Lets you see at a glance which prompts changed between snapshots.
- For each test repo: repo URL/path, commit SHA, size (file count).
- Pointer to the output files.

## The iteration loop

For one prompt site:

1. **Open the site page** in `prompts/<site>.md`.
2. **Fill in the snapshot section** with hash of current prompt + paths to captured outputs.
3. **State the hypothesis** for the iteration in a new `### YYYY-MM-DD: <change name>` block. Hypothesis must name the failure mode it addresses (e.g., "outputs are listy and skip the `why` — try changing instruction order to put rationale first").
4. **Edit the prompt** (single site, single change).
5. **Rebuild the affected stage** on each test repo. See site page for the right command(s).
6. **Capture new outputs** into a fresh snapshot directory.
7. **Diff** new vs baseline outputs. Document what changed (1-3 bullet points). Use `diff` for plain text, `jq` for JSON, or a quick LLM-assisted review for structured prose.
8. **Verdict.** kept / reverted / partial. If kept, update the site's `Status` field and re-baseline the snapshot for that site.

## Output capture mechanics

Two paths, pick per site:

**Path A — full daemon rebuild.** Most realistic. Point the daemon at the test repo, run the relevant pipeline stage (fast / deep / synth / audit), wait, then export the artifacts that the prompt produced (atlas docs from `~/.local/share/sourceprep/projects/<id>/`, concepts from the concept store, etc.). Slow but truthful.

**Path B — direct prompt invocation.** A small Python harness that calls the prompt-building function with synthetic or canned grounding and prints the LLM response. Fast iteration, but the grounding is fake — outputs may not match what production would produce. Useful for early exploration, not for verdicts.

For each site page, declare which path is used. Most sites should default to A; B is for rapid prototyping.

## Cross-site analysis

Some patterns will repeat across sites (instruction ordering, tier rubrics, banned-output lists, JSON schema enforcement). When you see a pattern that affects ≥3 sites, write it up under [`findings/`](./findings/) (create the file when needed) and link from the affected site pages. Cross-cutting findings often suggest a shared utility or template that should land in `src/prep/core/prompt_utils.py` (does not exist yet — propose it in `findings/` when warranted).

## When to deviate

This methodology is rigid by design. Deviations:

- **You are exploring, not auditing.** That's fine — keep notes under `prompts/<site>.md` with no `Iteration` block, just an `Exploration` section. Don't claim verdicts you can't defend.
- **The prompt is fundamentally wrong** (wrong task, wrong place in pipeline). Stop iterating, file a separate doc under `findings/` arguing for the structural change, and bring it to discussion before touching code.
- **The test repos are exposing a pipeline bug, not a prompt bug.** Document the bug, link it out to the appropriate phase/issue, and move on. Phase 140 does not fix orchestration.

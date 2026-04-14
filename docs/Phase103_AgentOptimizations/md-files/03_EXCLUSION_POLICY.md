# 03 — Agent-Artifact Exclusion Policy

## The principle

**If a host agent loads a file automatically into its context, CoDRAG should not index it.**

Re-indexing agent-context files has three costs:
1. **Wasted embedding tokens.** These files are large, text-dense, and prompt-tuned — they embed well and rank well, but the content is not what users are searching for.
2. **Search noise.** A query like *"how does auth work"* returns `CLAUDE.md` because we told Claude about auth in there — but the user wanted the actual `auth.py`. The generated rules-file outranks the real code.
3. **Circular authority.** CoDRAG-generated content gets re-ingested as if it were a trustworthy source, then informs concepts and observations, which then drive more generated content. A Möbius strip of confident hallucination.

Today CoDRAG's walker does not know this class of file exists. Default exclusions are `node_modules`, `.git`, `venv`, `__pycache__`, `dist`, `build`, `target`. That's it. Every `.claude/`, `.cursor/`, `AGENTS.md`, and generated skill gets walked, parsed, embedded, and retrieved. This is a silent quality tax on every indexed project.

## What the user sees

Empty feature today. Target behavior:

- **File-tree UI in dashboard:** agent-artifact files render with a strikethrough and a muted background, un-selectable for focus-area inclusion. Tooltip on hover: *"Agent-context file — loaded directly by your AI client, excluded from CoDRAG index to prevent noise."*
- **Badge / icon:** small "AI" chip next to the filename so the user understands *why* it's excluded, not just *that* it is.
- **Override path:** a right-click "include anyway" option that adds the file to a per-project allow-list. Rare but valid (e.g., a team wants to index their own CLAUDE.md to search its history).
- **Summary line at folder level:** when a folder like `.claude/` contains only agent artifacts, the folder collapses to a single line: *"6 agent-context files (hidden)"*.

## Classification framework

Files fall into six categories. The first three are what this policy governs.

| Class | Definition | Default action |
|---|---|---|
| **AGENT_DIRECT** | Host loads automatically into every agent session | Exclude + UI strikethrough |
| **AGENT_ON_DEMAND** | Host loads when agent invokes a specific skill/command | Exclude + UI strikethrough |
| **AGENT_GENERATED** | CoDRAG's own managed block (splice-marked content) | Exclude *managed portion only*; index user-edited portion |
| **PROJECT_DOCS** | Human-written README, docs/, CONTRIBUTING | **Include** (valuable signal) |
| **DEPENDENCY_LOCK** | package-lock.json, Cargo.lock, uv.lock | Exclude (already handled) |
| **BUILD_OUTPUT** | dist/, .next/, compiled artifacts | Exclude (already handled) |

## Complete artifact inventory (AGENT_DIRECT + AGENT_ON_DEMAND)

### Universal / cross-IDE
- `AGENTS.md` — universal agent instructions standard
- `.agentignore`, `.aiignore` — agent-specific ignore lists (meta, exclude)

### Claude Code
- `CLAUDE.md`, `CLAUDE.local.md`
- `.claude/settings.json`, `.claude/settings.local.json`
- `.claude/mcp.json`
- `.mcp.json` (project-level MCP config)
- `.claude/skills/**/*.md` — SKILL.md files and references
- `.claude/commands/**/*.md` — slash commands
- `.claude/agents/**/*.md` — subagent definitions
- `.claude/hooks/**` — hook scripts
- `.claude/rules/**/*.md` — rule fragments (imported via `@`)
- `.claude/scheduled_tasks.lock` — runtime state
- `.claude/worktrees/**` — worktree metadata

### Cursor
- `.cursorrules` (legacy)
- `.cursor/rules/**/*.mdc`
- `.cursor/mcp.json`

### Windsurf
- `.windsurfrules` (legacy)
- `.windsurf/rules/**/*.md`

### GitHub Copilot
- `.github/copilot-instructions.md`
- `.github/prompts/**/*.md`
- `.github/chatmodes/**/*.md`

### Cline
- `.clinerules`
- `.clinerules/**/*.md`

### Roo Code
- `.roo/rules/**/*.md`
- `.roo/rules-*/**/*.md` (mode-specific)
- `.roomodes`

### Gemini CLI
- `GEMINI.md`
- `.gemini/**/*.md`
- `.gemini/settings.json`

### Zed
- `.zed/settings.json` (agent block)
- `.rules`

### Qwen Code
- `QWEN.md`
- `.qwen/**/*.md`

### Generic / emerging
- `AI.md`, `AIRULES.md` (some tools use these)
- `.ai/**` conventions

## Special case: CoDRAG's own managed content

When CoDRAG writes its block into CLAUDE.md / AGENTS.md using `<!-- codrag-managed-start -->` markers, we are *both* the writer and a consumer of that file (when we walk the tree). Three sub-cases:

1. **Whole file is the managed block (e.g., we created AGENTS.md fresh):** treat as AGENT_GENERATED, exclude entirely. We know this by checking that the splice markers span the full file.
2. **Mixed file (user had CLAUDE.md, we appended our block):** this is the interesting case. We want to index the *user-authored* portion so searches find their intended instructions, but skip our own managed block. Split on markers, hash only the user content, embed only the user content.
3. **User-edited managed block (rare, unsupported):** detect by comparing a stored hash of our last-written content. If it drifted, flag in audit, treat conservatively as mixed.

## Edge cases

### Read-me-likes that are also agent-context
Some teams put agent instructions in `README.md` (common in OSS). We should not exclude all README files. Heuristic: exclude only if the file matches one of the canonical agent-context names. If a team names their instructions unconventionally, the file gets indexed — that's acceptable.

### User imports a generated rule file
Claude Code supports `@.claude/rules/foo.md` imports inside CLAUDE.md. These imports can be user-authored or CoDRAG-generated. We need to distinguish:
- If the rule file has CoDRAG's splice markers → AGENT_GENERATED, exclude.
- If it doesn't → user-authored, AGENT_DIRECT class, still exclude (host loads it via `@`).

### Nested projects / monorepos
A monorepo may have `packages/frontend/CLAUDE.md` alongside root `CLAUDE.md`. Both are AGENT_DIRECT. Pattern must be recursive (`**/CLAUDE.md`), not just root-level.

### `.claude/skills/*/SKILL.md` vs `.claude/skills/*/references/*.md`
The SKILL.md itself is AGENT_ON_DEMAND. References are loaded lazily and could theoretically be indexed — but they were written *for* the agent, so they still produce the circular authority problem. Default: exclude the whole skill folder. Give users an opt-in to include references if they want them searchable.

### Worktrees
`.claude/worktrees/busy-swirles/` is runtime state, not content. Exclude. More subtly, if a worktree itself contains a checked-out copy of the repo, the walker could double-index. The `ignore` crate already avoids this via `.git` exclusion, but we should verify.

### User's own agent definitions
A user may hand-craft `.claude/agents/my-reviewer.md` with unique non-CoDRAG content. Exclude by default (it's AGENT_DIRECT), but the user override path lets them flip it.

## Implementation strategies

### Strategy A — Pattern-based exclusion (walker level)

Extend `engine/crates/codrag-walker/src/lib.rs` default `exclude_globs` to include every pattern from the inventory above. This is the cheapest path.

```rust
exclude_globs: vec![
    // existing
    "**/node_modules/**".into(),
    "**/.git/**".into(),
    "**/venv/**".into(),
    "**/.venv/**".into(),
    "**/__pycache__/**".into(),
    "**/dist/**".into(),
    "**/build/**".into(),
    "**/target/**".into(),
    // agent-direct files
    "**/AGENTS.md".into(),
    "**/CLAUDE.md".into(),
    "**/CLAUDE.local.md".into(),
    "**/GEMINI.md".into(),
    "**/QWEN.md".into(),
    "**/.cursorrules".into(),
    "**/.windsurfrules".into(),
    "**/.clinerules".into(),
    "**/.roomodes".into(),
    "**/.rules".into(),
    // agent-direct directories
    "**/.claude/**".into(),
    "**/.cursor/**".into(),
    "**/.windsurf/**".into(),
    "**/.roo/**".into(),
    "**/.gemini/**".into(),
    "**/.qwen/**".into(),
    // copilot
    "**/.github/copilot-instructions.md".into(),
    "**/.github/prompts/**".into(),
    "**/.github/chatmodes/**".into(),
],
```

**Pros:** simple, fast, one PR. **Cons:** binary — no classification reported to UI, no user override, no awareness of mixed files.

### Strategy B — Classification pass (recommended)

Introduce a `FileClassifier` stage after walk, before index. For each walked path, compute a `FileClass` enum. Store the classification in the file-manifest (the same SQLite table we use for hashes). This gives us:

1. **Rich UI data** — the dashboard can query `FileClass` and render strikethroughs with tooltips.
2. **Per-class action** — `AGENT_DIRECT` skips embedding entirely; `AGENT_GENERATED` with mixed content gets the splice-aware path.
3. **Future-proof** — adding new agent artifacts (Cline, new IDEs) is a classifier table update, not a rebuild.
4. **Auditability** — `codrag audit --classification` lists all excluded files with reasons. Users can see *why* a file was skipped.

```python
# Conceptual
class FileClass(Enum):
    USER_CONTENT = "user"
    PROJECT_DOCS = "docs"
    AGENT_DIRECT = "agent_direct"
    AGENT_ON_DEMAND = "agent_on_demand"
    AGENT_GENERATED = "agent_generated"
    AGENT_GENERATED_MIXED = "agent_generated_mixed"  # split at markers
    DEPENDENCY_LOCK = "lock"
    BUILD_OUTPUT = "build"

CLASSIFICATION_RULES: list[tuple[re.Pattern, FileClass]] = [
    (re.compile(r".*/AGENTS\.md$"), FileClass.AGENT_DIRECT),
    (re.compile(r".*/CLAUDE(\.local)?\.md$"), FileClass.AGENT_DIRECT),
    (re.compile(r".*/\.claude/skills/.*"), FileClass.AGENT_ON_DEMAND),
    # ... etc
]
```

**Pros:** flexible, surfaces rationale to user, supports mixed-content splitting. **Cons:** more code, a new schema column.

### Strategy C — Marker-aware indexer (incremental on top of B)

For AGENT_GENERATED_MIXED files, the indexer reads the file, splits on `<!-- codrag-managed-start -->` / `<!-- codrag-managed-end -->`, embeds only the outer portion. Reports two hashes in the manifest (user-content hash, managed-content hash) so rebuilds only fire when user content changes.

**Pros:** lets us preserve user-authored CLAUDE.md content as searchable. **Cons:** parser complexity, edge cases (nested markers, unclosed markers, user deletion of markers).

### Strategy D — Dashboard-only override layer

Independent of walker and indexer, the dashboard file-tree loads the classification from the manifest and renders accordingly. Right-click "include anyway" writes to `codrag_data/exclusions_override.json` (project-scoped). On next index, `FileClassifier` consults the override before applying default rules.

### Recommended rollout

1. **v1 (1 day):** ship Strategy A — pattern list only. Immediate quality improvement for every project.
2. **v2 (1 week):** ship Strategy B — classification pass, manifest column, basic `codrag audit --classification` CLI.
3. **v3 (1 week):** ship Strategy D — dashboard UI with strikethrough + tooltip + override.
4. **v4 (2 weeks):** ship Strategy C — marker-aware indexer, unlock searchable user-authored CLAUDE.md content.

## Migration for existing indexes

Users who have CoDRAG installed already have indexes full of AGENTS.md / CLAUDE.md noise. We need:

- **Auto-purge on upgrade:** when CoDRAG's version bumps past the exclusion-policy release, a one-time migration runs `codrag purge --agent-artifacts` that removes embeddings for classified-exclude files without forcing a full reindex.
- **Opt-in reindex prompt:** if >5% of the current index mass is classified-exclude content, prompt the user to reindex for best results.

## Metrics

| Metric | Today (est.) | Target after v2 |
|---|---|---|
| Indexed AGENT_DIRECT files per project (median) | 3–8 | 0 |
| Index size reduction on CoDRAG's own repo | baseline | −5% to −15% |
| Search queries returning AGENT_DIRECT file in top 5 | likely high | 0% |
| Dashboard UI — excluded files visible & labeled | 0% | 100% |

## Risks

| Risk | Mitigation |
|---|---|
| Over-exclusion — we skip a file a user wants indexed | Override path in UI (Strategy D) |
| Pattern list goes stale as new IDEs emerge | Classifier is table-driven, ships as data not code; quarterly review |
| User-authored CLAUDE.md content becomes invisible | Strategy C (mixed-content splitting) preserves it |
| False positives (README.md that contains "agent" word) | Patterns match filename + path, not content — safe |
| Circular authority already present in existing indexes | Migration purge (above) |

## Connection to other Phase 103 features

- **F1 (role-projected subagents):** emits `.claude/agents/*.md` files. Those files must be AGENT_DIRECT-classified automatically so we don't re-index our own output.
- **F2 (slash commands):** same — generated `.claude/commands/*.md` must be classified.
- **F4 (skills as folders):** `.claude/skills/codrag/**` must be classified.
- **F7 (runtime awareness):** `.claude/rules/codrag-runtime.md` must be classified.

Without this exclusion policy, every feature we ship in Phase 103 adds to the circular-authority problem. **Exclusion policy is a prerequisite, not an enhancement.**

## Open questions

1. Should the exclusion list be shipped as *code* (compiled into the walker) or as *data* (a `agent_artifacts.yaml` file users can override)? Data is more flexible; code is faster and tamper-resistant.
2. Do we expose classifications via MCP resources? (`@excluded-files` — "show me what CoDRAG isn't indexing"). Useful for debugging, but adds surface area.
3. When a user explicitly adds a `.claude/` path to focus areas, do we honor it or still exclude? Proposal: honor with a warning banner.
4. Should `docs/` be automatically classified as `PROJECT_DOCS` with its own visual treatment? Cheap win but orthogonal to this policy.

# Phase 50: Deferred Items -- Implementation Strategy & Dev Testing Workflows

> Concrete implementation plan for the remaining Phase 50 items that require
> hands-on IDE testing or cross-process infrastructure work.

**Created:** 2026-03-17
**Depends on:** Phase 50 audit (complete), all code changes shipped

---

## Verification Report: What We Just Built

Full reverse-engineering audit of every changed component. All items verified correct.

### V1: ISSUE-6 -- Adaptive prep response

**Files:** `mcp/server.py:154-219` (`_project_has_rules_file`, `_get_project_path_sync`), `mcp/server.py:656-667` (payload construction)

**Logic flow:**
1. `tool_context()` resolves project_id
2. Calls `_project_has_rules_file(project_id)` -- checks disk for `.cursor/rules/prep.mdc`, `.windsurf/rules/prep.md`, `AGENTS.md` (with Prep markers), `CLAUDE.md` (with Prep markers)
3. Result cached per project_id for session lifetime
4. If found: `include_atlas=False` -- atlas is in system prompt, budget goes to code
5. If not found: `include_atlas=True` -- atlas included in tool response

**Verified correct:** Cache uses `getattr` for lazy init (safe). Path resolution uses initialize roots then CWD (matches MCP client behavior). AGENTS.md check reads first 500 bytes only (cheap). Test mocks `_project_has_rules_file` to control behavior independently.

**One concern noted:** `_get_project_path_sync` returns `_initialize_roots[0]` which is the workspace root from the IDE. In multi-root workspaces, this could be the wrong root. Acceptable for now -- multi-root is rare and the cache means the check only runs once per session. If it misdetects, the consequence is including/excluding the atlas (non-fatal, just suboptimal).

### V2: OPP-2 -- Resource subscriptions

**Files:** `mcp/server.py:122` (`_notification_callback`), `mcp/server.py:231-248` (`notify_resource_changed`), `mcp/transport.py:45-49` (stdio wiring), `mcp/transport.py:150-153` (SSE wiring)

**Logic flow:**
1. Transport layer sets `server._notification_callback` to a transport-specific async function
2. stdio: writes JSON-RPC notification to stdout + flush
3. SSE: puts notification dict onto the session's asyncio.Queue
4. `notify_resource_changed(uri)` constructs `notifications/resources/updated` per MCP spec and calls the callback
5. Best-effort: if callback is None or throws, silently continues

**Verified correct:** Notification format matches MCP spec (jsonrpc 2.0, method, params with uri). SSE closure captures queue via default arg (`q=queue`) to avoid late-binding issues. Both transports handle the async callback correctly.

**Not yet wired to pipeline:** The notification method exists but nothing calls it yet. The pipeline orchestrator runs in a different process than the MCP server. Wiring this requires a cross-process bridge (see Deferred Item D1 below).

### V3: OPP-1 -- Parallel tool call hint

**File:** `rules_generator.py:380-385`

**Content:** "You can call `prep` and `prep_search` in parallel on your first prompt -- structural overview + targeted code lookup in one round-trip."

**Verified correct:** Placed after the long-task refresh hint, before the return. Clean wording. No risk -- hosts that don't support parallel calls just serialize them.

### V4: OPP-4 -- Observe write-through

**File:** `mcp/server.py:935-987`

**Logic flow:**
1. Save observation via `_api_post` to `/projects/{id}/observations`
2. On success, fetch lightweight ambient context (4000 char budget, same `include_atlas` logic as ISSUE-6)
3. If context fetch succeeds, append `---\n## Updated Context\n` + context to the markdown
4. If context fetch fails (non-fatal), just return the save confirmation

**Verified correct:** The context fetch is wrapped in try/except (non-fatal). Budget is 4000 chars (small, fast). Uses `_project_has_rules_file` for atlas decision (consistent with ISSUE-6). The `_to_markdown` key is set regardless of whether context was fetched (save message alone is valid markdown).

### V5: Roo Code mode-specific rules

**File:** `rules_generator.py:797-851`

**Generates 3 files:**
1. `.roo/rules/prep.md` -- full managed content (all modes)
2. `.roo/rules-architect/prep.md` -- architecture focus (prep + prep_audit + prep_search)
3. `.roo/rules-code/prep.md` -- change focus (prep_impact + prep_search + prep_observe)

**Verified correct:** Each directory created with `mkdir(parents=True, exist_ok=True)`. Mode-specific files are short and focused (3 lines each). Base file has full managed content. No marker management needed for mode-specific files since they're fully owned by Prep.

### V6: README reconciliation

Verified the key updates:
- "Tools only" -> "Tools + Resources + Prompts" with updated counts
- GAPs 1-4, 7 marked DONE with implementation details
- Protocol diagram: `[NOT IMPLEMENTED]` tags removed
- File reference table expanded with tool_hi.py, transport.py, rules_generator.py
- `.mdrule` -> `.mdc` in Appendix B

### V7: All `_to_markdown` responses

| Tool method | `_to_markdown` | Format |
|---|---|---|
| `tool_audit` | Lines 1116-1134 | `## Audit Results (N findings)` + severity + finding list + available reports |
| `tool_audit_check` | Lines 1168-1171 | `## Verify: N finding(s) remain` + finding list |
| `tool_audit_report` | Line 1194 | Raw report content or fallback message |
| `tool_save_observation` | Lines 976-986 | Save confirmation + optional `## Updated Context` |
| `tool_get_observations` | Lines 1026-1042 | `## Observations (N)` + formatted list or "No observations found." |

All verified to set `_to_markdown` on every return path. The dispatch in `handle_tools_call` (lines 1940-1947) checks for `_to_markdown` first, falls back to `json.dumps`.

### V8: Annotations

All 6 tool definitions verified:
- `prep`: `{"readOnlyHint": True, "openWorldHint": True}`
- `prep_search`: `{"readOnlyHint": True, "openWorldHint": True}`
- `prep_impact`: `{"readOnlyHint": True, "openWorldHint": True}`
- `prep_audit`: `{"readOnlyHint": True, "openWorldHint": True}`
- `prep_observe`: `{"readOnlyHint": False}` (write tool -- correct)
- `prep_context` (dev alias): `{"readOnlyHint": True, "openWorldHint": True}`

---

## Deferred Items: Implementation Strategy

### D1: Pipeline-to-MCP Resource Notification Bridge -- BUILT

**Status: COMPLETE.** Option A (file-based signal) implemented.

**How it works:**

1. **Orchestrator side** (`src/prep/services/pipeline/orchestrator.py`):
   - `_write_atlas_signal(idx_dir)` -- static method, writes `atlas_updated.signal` with `time.time()` to the project's index directory
   - Called after `_generate_preliminary_atlas_and_rules()` (Stage 1 complete)
   - Called after `_regenerate_rules_with_full_atlas()` (Stage 9 complete)

2. **MCP server side** (`src/prep/mcp/server.py`):
   - `_last_atlas_signal: Dict[str, float]` -- per-project mtime tracker (in `__init__`)
   - `_check_atlas_signal(project_id)` -- async method called at the top of `tool_context()`:
     - Resolves project path via `_get_project_path_sync()` (no HTTP call)
     - Checks `<project>/.runprep/atlas_updated.signal` and `<project>/atlas_updated.signal`
     - If mtime > last recorded: invalidates `_rules_file_cache`, sends `notifications/resources/updated` for atlas + structure resources
   - Cost: one `stat()` per `tool_context()` call (~0.1ms)

3. **Transport layer** (`src/prep/mcp/transport.py`):
   - stdio: `_stdio_notify()` writes JSON-RPC notification to stdout
   - SSE: `_sse_notify()` pushes to the session's asyncio.Queue
   - Both wired to `server._notification_callback` at transport startup

**Verification:** The signal file is only written after successful atlas + rules generation. If either fails, the signal is not written (non-fatal). The MCP server check is wrapped in try/except (non-fatal). Worst case: AI gets slightly stale data until next pipeline run.

---

### D2: Claude Code Skills -- BUILT

**Status: COMPLETE.**

**File:** `src/prep/core/rules_generator.py` -- `_write_claude_skill()`

Creates `.claude/skills/prep.md` with YAML frontmatter that registers a `/prep` slash command in Claude Code:

```yaml
---
description: Get structural codebase context from Prep
tools:
  - mcp__prep__prep
  - mcp__prep__prep_search
  - mcp__prep__prep_impact
---
```

- Only written when `.claude/` directory already exists (auto-detected)
- Won't overwrite if user has already customized the skill file
- Included in `_detect_targets()` and `all_targets` list

---

### D3: Empirical Test Plan (T1-T20)

These tests require hands-on interaction with each IDE. They cannot be automated -- they validate how each host processes MCP protocol features.

#### Test Environment Setup

```bash
# 1. Start Prep daemon with a test project
cd /path/to/test-project
prep add .
prep serve --port 8400

# 2. Start MCP server with logging
prep mcp --log-file ~/.runprep/mcp-test.log --debug

# 3. Verify MCP server is receiving connections
tail -f ~/.runprep/mcp-test.log
# Look for: "MCP client detected: name=... version=..."
```

#### T1: clientInfo.name capture (ALL HOSTS)

**Status:** Infrastructure done (logging at INFO level). Needs hands-on validation.

**Workflow per host:**
1. Configure MCP server in the host (see SETUP_GUIDE.md for per-tool config)
2. Open a project in the host
3. Send any message that triggers a tool call (e.g., "what is this codebase?")
4. Check `~/.runprep/mcp-test.log` for `MCP client detected: name=... version=...`
5. Record the exact string in the table below

| Host | Predicted `clientInfo.name` | Actual | Validated |
|------|---------------------------|--------|-----------|
| Cursor | `"cursor"` or `"Cursor"` | | [ ] |
| Windsurf | `"windsurf"` or `"cascade"` | | [ ] |
| Claude Code | `"claude-code"` or `"claude"` | | [ ] |
| Copilot (VS Code) | `"vscode"` or `"copilot"` | | [ ] |
| Gemini CLI | `"gemini-cli"` | | [ ] |
| Cline | `"cline"` | | [ ] |
| Roo Code | `"roo-code"` or `"roo-cline"` | | [ ] |

**Action after validation:** Update `_CLIENT_BUDGETS` dict in `server.py` if any names don't match the pattern-based matching.

#### T2-T5: MCP `instructions` field behavior

**What we're testing:** Does the host append our `instructions` text from the initialize response to the AI's system prompt?

**Workflow:**
1. Configure Prep MCP server in the host
2. Start a new session
3. Ask the AI: "What MCP servers are you using? What instructions did they provide?"
4. If the AI mentions Prep's instructions text ("Prep maps how your codebase is connected..."), the instructions field works
5. If the AI doesn't mention it, try: "Do you have any special instructions about Prep tools?"

| Host | Instructions visible? | Notes |
|------|---------------------|-------|
| Gemini CLI | Expected: YES | Confirmed in Gemini CLI docs |
| Claude Code | Expected: YES | MCP spec compliant |
| Cursor | Expected: UNKNOWN | May be ignored |
| Windsurf | Expected: UNKNOWN | May be ignored |

**Impact if ignored:** No problem. Rules files (.cursor/rules/prep.mdc, .windsurf/rules/prep.md) cover Cursor and Windsurf. The instructions field is belt-and-suspenders.

#### T6: AGENTS.md with markers

**What we're testing:** Do AI tools correctly parse AGENTS.md that contains our `<!-- prep-managed-start/end -->` HTML comment markers?

**Workflow:**
1. Generate AGENTS.md for a test project: `prep generate-rules --target agents_md`
2. Open the project in Cursor, Windsurf, Claude Code
3. Ask: "What does the AGENTS.md tell you about this project?"
4. Verify the AI reads the Prep section without being confused by the HTML markers

**Pass criteria:** AI quotes or paraphrases the Prep tool instructions from AGENTS.md. HTML markers are invisible (treated as comments).

#### T7-T8: Rules file injection

**T7 (Cursor):**
1. Generate `.cursor/rules/prep.mdc` for a test project
2. Open project in Cursor
3. Ask: "What rules or instructions do you have about Prep?"
4. Verify AI sees the `alwaysApply: true` content
5. Ask any coding question -- verify AI calls `prep` first

**T8 (Windsurf):**
1. Generate `.windsurf/rules/prep.md` for a test project
2. Open project in Windsurf
3. Same verification as T7 but with `trigger: always_on` frontmatter

#### T9: CLAUDE.md section append

1. Create a `CLAUDE.md` with existing user content
2. Run rules generation (which appends Prep section with markers)
3. Open project in Claude Code
4. Verify both user content AND Prep content are visible
5. Re-run rules generation -- verify user content below markers is preserved

#### T10-T12: Auto-approve

**T10 (Claude Code):**
```json
// .claude/settings.json
{"permissions": {"allow": ["mcp__prep"]}}
```
Verify: No confirmation prompts for any Prep tool call.

**T11 (Cursor):**
Settings > Features > MCP > enable auto-run for prep server.
Verify: No confirmation prompts.

**T12 (Copilot with sandboxing):**
```json
// .vscode/mcp.json
{"servers": {"prep": {"command": "prep", "args": ["mcp"], "sandboxEnabled": true, "sandbox": {"filesystem": {"allowWrite": []}, "network": {"allowedDomains": ["localhost"]}}}}}
```
Verify: Auto-approved on macOS/Linux. Manual approval on Windows.

#### T13-T20: Extended tests (lower priority)

Run these opportunistically when working in each tool:

**T13 -- Cline keyword triggers:**
```
1. Ensure .clinerules exists with Prep keyword section
2. Open project in Cline (VS Code extension)
3. Ask: "analyze the code structure of this project"
4. PASS: Cline activates Prep tools (you see prep tool calls in the chat)
5. FAIL: Cline uses only native tools (grep, read_file) without calling prep
```

**T14 -- Roo Code Architect mode:**
```
1. Ensure .roo/rules-architect/prep.md exists (generated by rules_generator)
2. Open project in Roo Code, switch to Architect mode
3. Ask: "give me an architecture overview"
4. PASS: AI references prep_audit and prep tools (from the architect rules)
5. FAIL: AI doesn't mention Prep or use structural tools
```

**T15 -- Roo Code AGENTS.md injection order:**
```
1. Ensure both AGENTS.md AND .roo/rules/prep.md exist
2. Add a unique marker to each: "MARKER_AGENTS" in AGENTS.md, "MARKER_ROO" in .roo/rules/
3. Ask AI: "what instructions do you have? list them in order"
4. PASS: MARKER_AGENTS appears BEFORE MARKER_ROO (matches Roo Code docs: AGENTS.md between mode-specific and general)
5. NOTE: This tests injection ORDER, not just presence
```

**T16 -- Claude Code Tool Search deferral:**
```
1. Configure 15+ MCP servers in Claude Code (can be dummy servers that fail)
2. Ensure CLAUDE.md has "call prep FIRST" instruction
3. Ask: "analyze the architecture of this codebase"
4. PASS: Claude finds and calls prep despite having 15+ servers (CLAUDE.md primes the search)
5. FAIL: Claude can't find prep tools (they were deferred and CLAUDE.md didn't help)
6. DIAGNOSTIC: Check if Claude mentions "searching for tools" in its thinking
```

**T17 -- MCP Resources in Gemini CLI:**
```
1. Start Prep MCP server connected to Gemini CLI
2. Type: @prep://[project_id]/atlas
3. PASS: Gemini shows the atlas content (module structure, hub files)
4. FAIL: Gemini doesn't recognize the resource URI
```

**T18 -- MCP Prompts in Gemini CLI:**
```
1. Start Prep MCP server connected to Gemini CLI
2. Type: /prep-analyze
3. PASS: Gemini populates the prompt template and Claude calls prep + prep_search
4. FAIL: Slash command not recognized
```

**T19 -- Local LLM tool calling via Cline:**
```
1. Configure Cline with Ollama running Llama 3.3 70B (or qwen3:14b)
2. Configure Prep MCP server
3. Ask: "what is the architecture of this project?"
4. PASS: The local LLM successfully calls prep tool (tool-calling works)
5. FAIL: LLM doesn't attempt tool calls or fails to format them correctly
6. NOTE: This tests whether small/medium local models can use MCP tools at all
```

**T20 -- Copilot on Windows (no sandbox):**
```
1. On a Windows machine, configure Prep in .vscode/mcp.json (note: servers key, NOT mcpServers)
2. Use Copilot agent mode, ask a coding question
3. PASS: Copilot shows approval dialog for Prep tool calls, user can approve
4. FAIL: Tool calls don't appear or crash
5. NOTE: sandboxEnabled auto-approve is NOT available on Windows
```

---

### D4: Windsurf Cascade Hooks for Analytics (DEFERRED -- Enterprise)

**What:** Use `pre_mcp_tool_use` / `post_mcp_tool_use` hooks to log Prep usage for product analytics.

**Implementation:** The hook config goes in the user's Windsurf MCP config, not in Prep's code. Prep could provide a template:

```json
{
  "hooks": {
    "post_mcp_tool_use": {
      "command": "prep",
      "args": ["log-mcp-call", "--tool", "${tool_name}"]
    }
  }
}
```

This requires a `prep log-mcp-call` CLI subcommand that appends to the audit log.

**Effort:** ~1 hour. Defer until enterprise tier is actively used.

---

## Summary: What's Built vs. What Needs Testing

### BUILT (code complete, tests passing)

| Item | Files Changed | Tests |
|------|--------------|-------|
| D1: Atlas signal bridge | `orchestrator.py` (signal write), `server.py` (signal check + cache invalidation), `transport.py` (notification callbacks) | 115/115 pass |
| D2: Claude Code Skills | `rules_generator.py` (_write_claude_skill + detection) | 115/115 pass |
| ISSUE-6: Adaptive atlas | `server.py` (_project_has_rules_file + include_atlas logic) | 115/115 pass |
| OPP-1: Parallel hint | `rules_generator.py` (template text) | 115/115 pass |
| OPP-2: Resource notifications | `server.py` (notify_resource_changed), `transport.py` (stdio + SSE callbacks) | 115/115 pass |
| OPP-4: Observe write-through | `server.py` (tool_save_observation context refresh) | 115/115 pass |
| Roo Code mode-specific | `rules_generator.py` (architect + code mode files) | 115/115 pass |
| annotations migration | `mcp_tools.py` (all 6 tool defs) | 115/115 pass |
| Markdown responses | `server.py` (5 tool methods + _to_markdown) | 115/115 pass |

### NEEDS HANDS-ON TESTING (cannot be automated)

**Recommended test day: Pick 3 hosts, ~90 minutes total.**

| Order | Test | Host | What you learn | Time |
|-------|------|------|---------------|------|
| 1 | T1 | ALL | Exact clientInfo.name strings | 5 min/host |
| 2 | T7-T8 | Cursor + Windsurf | Rules file injection works | 10 min/host |
| 3 | T2-T5 | Gemini CLI + Claude Code | Instructions field appended to system prompt | 10 min/host |
| 4 | T10-T11 | Cursor + Claude Code | Auto-approve eliminates friction | 5 min/host |
| 5 | T6 | Cursor | AGENTS.md markers parse cleanly | 5 min |
| 6 | T9 | Claude Code | CLAUDE.md append preserves user content | 5 min |

**After test day, update:**
1. The T1 results table in this document (fill in Actual column)
2. `_CLIENT_BUDGETS` in `server.py` if any pattern mismatches
3. T2-T5 results table (fill in "Instructions visible?" column)
4. If any host ignores instructions field: no action needed (rules files are the primary mechanism)

### DEFERRED (not yet needed)

| Item | When | Effort |
|------|------|--------|
| D4: Windsurf Cascade Hooks | Enterprise tier launch | 1h |
| T13-T20: Extended host tests | Opportunistic / when working in each tool | 10-15 min each |

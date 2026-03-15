# CoDRAG Integration Deep Dive: MVP Optimization & Edge Cases

> Tool-by-tool deep dive into optimization strategies, edge cases, and pitfalls.
> Focus: **universality first**, then tool-specific perfection for the majority of the market.

**Last updated:** 2026-03-14

---

## 0. MVP Target Classification

### "Must be perfect on day one" (80%+ of market)

| Tool | Why MVP | Market Position |
|------|---------|----------------|
| **Cursor** | Largest AI IDE user base | #1 IDE |
| **Windsurf** | #2 AI IDE, Cognition acquisition = growing | #2 IDE |
| **Claude Code** | Primary CLI tool, Anthropic's flagship | #1 CLI agent |
| **GitHub Copilot** | Largest installed base (via VS Code) | #1 by installs |
| **Gemini CLI** | Google's open-source CLI, fast-growing | #2 CLI agent |

### "Should work well" (next 15%)

| Tool | Why Important | Notes |
|------|--------------|-------|
| **Cline** | Huge VS Code extension, open-source community | Shares arch with Roo Code |
| **Roo Code** | Growing fast, Cline fork with modes | Same MCP impl as Cline |
| **Qwen Code** | Mirrors Gemini CLI exactly | Free ride from Gemini work |
| **OpenAI Codex** | OpenAI's CLI agent | AGENTS.md native |

### "Defer for now" (outliers, ~5%)

| Tool | Why Defer |
|------|-----------|
| **DeepAgents** | Framework, not end-user tool. Programmatic only. |
| **Aider** | No native MCP client. Static context only. |
| **Continue** | Unique config.yaml format. Small but loyal base. |
| **Cloud agents** (Jules, Devin, OpenHands) | Can't reach local daemon. AGENTS.md only. |

---

## 1. CRITICAL CORRECTIONS FROM DEEP RESEARCH

Several findings from this deep dive **invalidate assumptions** from the preliminary research. These must be addressed before implementation.

### CORRECTION 1: Windsurf rules are NOT `.windsurfrules` anymore

**Old assumption:** CoDRAG generates/appends to `.windsurfrules` in project root.

**Reality (from current Windsurf docs):**
- Rules now live in `.windsurf/rules/*.md` (one file per rule)
- Each rule has YAML frontmatter with a `trigger` field
- Activation modes: `always_on`, `model_decision`, `glob`, `manual`
- **12,000 character limit** per rule file
- **6,000 character limit** for global rules
- Root-level `AGENTS.md` is treated as always-on automatically
- `.windsurfrules` may still work as legacy but the new system is `.windsurf/rules/`

**CoDRAG must generate:** `.windsurf/rules/codrag.md` with frontmatter:
```markdown
---
trigger: always_on
description: CoDRAG structural codebase intelligence
---

[CoDRAG content here]
```

### CORRECTION 2: Windsurf has a 100-tool limit

**Old assumption:** No documented tool limit for Windsurf.

**Reality:** "Cascade has a limit of **100 total tools** that it has access to at any given time." Users can toggle individual tools on/off per MCP server.

**Implication:** CoDRAG's 5 consolidated tools are well within budget. But users with many MCP servers may hit 100 tools and need to disable some. CoDRAG should keep tool count minimal.

### CORRECTION 3: Windsurf has Cascade Hooks (pre/post MCP tool use)

**Discovery:** Windsurf supports `pre_mcp_tool_use` and `post_mcp_tool_use` hooks. These fire before/after any MCP tool call with full argument visibility.

**Opportunity:** A `post_mcp_tool_use` hook could log CoDRAG usage for analytics. A `pre_mcp_tool_use` hook could inject context or validate arguments. Low priority but interesting for enterprise users.

### CORRECTION 4: Cursor YOLO mode does NOT auto-approve MCP tools

**Old assumption:** Cursor's "Yolo mode" auto-runs MCP tools.

**Reality (from Cursor forum):** YOLO mode auto-runs terminal commands but does NOT auto-approve MCP tools. This is a known issue/feature request. Users must separately configure MCP auto-run per server.

**Implication:** CoDRAG setup docs must explicitly tell Cursor users: "YOLO mode is not enough. Go to Settings > Features > MCP > enable auto-run for the codrag server."

### CORRECTION 5: Claude Code has MCP Tool Search (deferred loading)

**Discovery:** When too many MCP tools are configured, Claude Code **defers** MCP tools -- it does NOT load them into context upfront. Instead, Claude uses an internal `MCPSearch` tool to discover relevant tools on-demand.

**How it works:**
1. MCP tools are deferred (not in initial context)
2. Claude uses a search tool to discover relevant MCP tools when needed
3. Only tools Claude actually needs are loaded

**Triggered when:** Total tools exceed a threshold (configurable via `ENABLE_TOOL_SEARCH=auto:<N>`)

**Critical implication for CoDRAG:** If the user has many MCP servers, CoDRAG tools may be **deferred and invisible** until Claude searches for them. The `instructions` field and `CLAUDE.md` become even more important -- they tell Claude "CoDRAG exists, search for it."

**For MCP server authors:** "Include in your server description: What category of tasks your tools handle, when Claude should search for your tools, key capabilities your server provides."

**CoDRAG action:** Our MCP server's `instructions` field should include search hints: "CoDRAG handles structural code intelligence, module architecture, dependency analysis, and codebase navigation."

### CORRECTION 6: Claude Code MCP output limit is 25,000 tokens

**Discovery:** Claude Code has a **default MCP output limit of 25,000 tokens**. Warning at 10,000 tokens. Configurable via `MAX_MCP_OUTPUT_TOKENS`.

**Implication:** CoDRAG's responses are well under this (~250-3000 tokens typically). But if a user requests a massive context dump or the project is huge, we should be aware. Our responses should stay compact by design.

### CORRECTION 7: Claude Code MCP permission syntax

**Confirmed exact syntax:**
```
mcp__codrag           -- matches ANY tool from the codrag server
mcp__codrag__*        -- wildcard, same effect
mcp__codrag__codrag   -- matches only the `codrag` tool
mcp__codrag__codrag_search  -- matches only `codrag_search`
```

**CoDRAG setup instruction for Claude Code:**
```json
{
  "permissions": {
    "allow": ["mcp__codrag"]
  }
}
```
This auto-approves ALL CoDRAG tools with a single rule.

---

## 2. TOOL-BY-TOOL DEEP DIVE

### 2A. Cursor

**Market position:** #1 AI IDE. Must be flawless.

#### Rules File: `.cursor/rules/codrag.mdc`

**Format confirmed:**
```yaml
---
description: CoDRAG structural codebase intelligence
alwaysApply: true
---

[content]
```

**Edge cases:**
- `.mdc` extension required for YAML frontmatter support (`.md` works but no frontmatter)
- `alwaysApply: true` is the critical flag -- without it, Cursor may not inject on every prompt
- Team Rules > Project Rules > User Rules precedence -- CoDRAG's rules are project-level
- If a team rule conflicts with CoDRAG's rule, the team rule wins

**Auto-approve pitfall:**
- YOLO mode does NOT auto-approve MCP tools (confirmed from forum)
- Must use: Settings > Features > MCP > per-server auto-run toggle
- CoDRAG setup docs must be explicit about this

**Tool competition strategy:**
Cursor has powerful native tools: `codebase_search`, `read_file`, `grep_search`. The AI defaults to these.

To make CoDRAG win:
1. Rules file says "Call `codrag` FIRST before using codebase_search or grep_search"
2. Tool description differentiates: "structural relationships and module architecture" vs. "text search"
3. Response includes value the native tools can't provide: module map, hub connectivity, blast radius

**AGENTS.md interaction:**
Cursor reads AGENTS.md (confirmed on agents.md site). Both `.cursor/rules/codrag.mdc` and `AGENTS.md` can coexist. The `.mdc` file takes precedence (it's Cursor-native with `alwaysApply`). AGENTS.md provides fallback for when the `.mdc` isn't generated yet.

**Parallel tool calls:**
Cursor's agent mode supports parallel tool calls. Rules file should encourage:
"You can call `codrag` and `codrag_search` in parallel on your first prompt."

**Unknown:**
- Does Cursor support MCP server `instructions` field? (needs empirical test)
- What is `clientInfo.name` in initialize? (likely `"cursor"`)

---

### 2B. Windsurf / Cascade

**Market position:** #2 AI IDE. Cognition acquisition makes this strategically important.

#### Rules File: `.windsurf/rules/codrag.md` (CORRECTED)

**Format (updated from deep dive):**
```markdown
---
trigger: always_on
description: CoDRAG structural codebase intelligence
---

[content]
```

**Key differences from Cursor:**
- `trigger: always_on` instead of `alwaysApply: true`
- File in `.windsurf/rules/` directory, not `.cursor/rules/`
- 12,000 character limit per rule (generous -- CoDRAG's ~700 tokens = ~2,800 chars)
- Windsurf also reads `AGENTS.md` natively (root = always-on, subdir = auto-glob)

**AGENTS.md behavior (critical discovery):**
Windsurf treats root-level `AGENTS.md` as **always-on** (same as `trigger: always_on`). This means:
- If CoDRAG generates `AGENTS.md` with atlas in project root, Windsurf injects it on every message
- This is IDENTICAL behavior to a `.windsurf/rules/codrag.md` with `trigger: always_on`
- **We might not need a Windsurf-specific file at all** -- AGENTS.md covers it

**Strategy decision:** Generate both:
1. `AGENTS.md` section (universal, also works in Windsurf natively)
2. `.windsurf/rules/codrag.md` (Windsurf-specific, with proper frontmatter)

The Windsurf-specific file ensures CoDRAG works even if the user doesn't have AGENTS.md. Belt and suspenders.

**100-tool limit:**
Windsurf allows toggling individual tools per MCP server. If a user is near 100 tools, they can disable `codrag_audit` or `codrag_observe` and keep only the core 3 (`codrag`, `codrag_search`, `codrag_impact`).

**Cascade Hooks opportunity:**
```json
{
  "hooks": {
    "pre_mcp_tool_use": {
      "command": "echo",
      "args": ["CoDRAG tool call detected"]
    }
  }
}
```
Future: CoDRAG could provide a hook script that logs usage analytics.

**MCP config location:**
`~/.codeium/windsurf/mcp_config.json` (NOT `~/.codeium/mcp_config.json` -- path changed)

---

### 2C. Claude Code

**Market position:** #1 CLI agent. Anthropic's flagship. Must be flawless.

#### Rules File: `CLAUDE.md`

**Confirmed behavior:**
- `CLAUDE.md` in project root is loaded at session start
- First 200 lines of `MEMORY.md` also loaded (CoDRAG should NOT touch MEMORY.md)
- Hierarchy: `~/.claude/CLAUDE.md` (global) > `./CLAUDE.md` (project) > `./subdir/CLAUDE.md` (directory)

**MCP Tool Search (critical edge case):**
When many MCP servers are configured, Claude Code defers tools. CoDRAG's tools become invisible until Claude searches for them.

**Mitigation strategy (layered):**
1. `CLAUDE.md` says "Call `codrag` FIRST" -- always in context, even when tools are deferred
2. MCP `instructions` field says "CoDRAG handles structural code intelligence" -- primes Claude to search
3. Tool descriptions include category hints: "structural code intelligence, module architecture, dependency analysis"
4. If user has few MCP servers (common case), tools load normally -- no issue

**Permission setup (exact syntax):**
```json
// .claude/settings.json or project .claude/settings.json
{
  "permissions": {
    "allow": ["mcp__codrag"]
  }
}
```

This is a single rule that auto-approves ALL CoDRAG tools. Much better than listing each tool individually.

**Alternative:** `--allowedTools "mcp__codrag"` on command line.

**MCP output limit:**
Default 25,000 tokens, warning at 10,000. CoDRAG responses are typically 250-3,000 tokens. No issue. But if we implement a "dump all hub file content" mode in the future, we must respect this limit.

**Skills integration (future):**
A CoDRAG skill at `.claude/skills/codrag.md`:
```markdown
---
description: Get structural codebase context from CoDRAG
tools: ["mcp__codrag__codrag", "mcp__codrag__codrag_search"]
---
Call `codrag` to get the structural overview, then use that context to inform your approach.
```

This creates a `/codrag` slash command in Claude Code. Low priority but high polish.

**Subagent access:**
Claude Code subagents can be configured with `mcpServers` in their definition. CoDRAG tools CAN be made available to subagents explicitly. This is important for complex multi-agent workflows.

**Context compaction:**
`/compact` summarizes older messages. CoDRAG tool responses from turn 1 will be summarized. Mitigations:
1. Atlas in CLAUDE.md survives compaction (reloaded each session)
2. MCP `instructions` survives compaction (system prompt level)
3. Response nudges remind AI to re-call `codrag` on long tasks

---

### 2D. Gemini CLI

**Market position:** Google's open-source CLI. Fast-growing. #2 CLI agent.

#### MCP Server Instructions (CONFIRMED)

This is Gemini CLI's killer feature for CoDRAG:
```
"MCP server instructions will be appended to the system instructions."
```

CoDRAG's `instructions` field in the initialize response is **automatically injected into every prompt**. No rules file needed for basic activation.

**What to put in instructions (keep brief, ~60 tokens):**
```
CoDRAG provides structural codebase context via trace graph analysis.
ALWAYS call `codrag` at the start of every coding task for module structure,
hub files, and focus areas. Use `codrag_search` for specific code queries
with structural trace expansion. Use `codrag_impact` before making changes.
```

**What NOT to put in instructions:**
- The full atlas (too long, goes in AGENTS.md/GEMINI.md)
- Focus areas (dynamic, changes per session)
- Detailed tool parameter docs (already in tool descriptions)

#### Rules File: `GEMINI.md` or `AGENTS.md`

Gemini CLI reads a context file configured in `.gemini/settings.json`:
```json
{
  "context": {
    "fileName": "AGENTS.md"
  }
}
```

**Strategy:** CoDRAG generates AGENTS.md (universal). Users who want Gemini-specific can point to it. No need for a separate GEMINI.md unless the user has conflicting content.

#### Schema Sanitization (edge case)

Gemini CLI strips:
- `$schema` property
- `additionalProperties` property
- `anyOf` with `default` values

CoDRAG's tool schemas should NOT use any of these. Current schemas are simple and safe.

#### Tool Name Conflicts

If another MCP server has a tool named `codrag` (unlikely but possible), Gemini CLI resolves via `serverName__toolName` prefix. CoDRAG's unique naming makes this a non-issue.

#### Trust Configuration
```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"],
      "trust": true
    }
  }
}
```

**`trust: true`** bypasses all confirmation dialogs for CoDRAG. Safe because all tools are read-only.

#### Resources

Gemini CLI discovers resources automatically. User references via `@resource` in chat. CoDRAG should implement:
- `codrag://atlas` -- structural overview
- `codrag://health` -- index freshness

These give Gemini CLI users quick metadata checks without tool calls.

#### Prompts as Slash Commands

Gemini CLI exposes MCP prompts as `/slash_commands`. CoDRAG should implement:
- `/codrag-overview` -- "Give me a structural overview"
- `/codrag-review` -- "Review using structural context"

---

### 2E. GitHub Copilot (UPDATED)

**Market position:** Largest installed base. Agent mode is newer but growing fast.

#### Two Products, Two Strategies

**Copilot Agent Mode (VS Code):**
- MCP tools available in chat via agent mode
- **Config:** `.vscode/mcp.json` with `servers` key (NOT `mcpServers`)
- Full MCP support: tools, resources, prompts, apps
- Transports: stdio, SSE, Streamable HTTP
- Rules: `.github/copilot-instructions.md` + AGENTS.md

**Copilot Coding Agent (Cloud):**
- Runs asynchronously in GitHub cloud
- Cannot access local CoDRAG daemon
- Reads AGENTS.md from the repo
- AGENTS.md atlas is the ONLY structural context source

**Strategy:**
1. For agent mode: standard MCP + `.github/copilot-instructions.md` + AGENTS.md
2. For coding agent: AGENTS.md atlas must be self-sufficient (no live tools)

#### CORRECTION 8: Copilot config uses `servers` key, NOT `mcpServers`

Every other tool uses `mcpServers`. Copilot (VS Code) uses `servers`:
```json
{
  "servers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    }
  }
}
```
This **will** trip up users who copy-paste from other tools' configs.

#### CORRECTION 9: Copilot has sandboxing = auto-approve (macOS/Linux)

VS Code supports `"sandboxEnabled": true` for stdio MCP servers.
Sandboxed servers restrict filesystem/network access to explicit allowlists.
**When sandboxed, tool calls are auto-approved** -- no manual confirmation.

CoDRAG sandboxed config:
```json
{
  "servers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"],
      "sandboxEnabled": true,
      "sandbox": {
        "filesystem": { "allowWrite": [] },
        "network": { "allowedDomains": ["localhost"] }
      }
    }
  }
}
```

**NOT available on Windows.** Windows users must approve each call.

**Edge case: cloud agent and atlas quality**
The Copilot coding agent running in GitHub's cloud has NO access to CoDRAG's daemon. It can only read files from the repo. This makes the atlas in AGENTS.md critical -- it must contain enough structural information for the AI to make good architectural decisions without any tool calls.

Atlas content for cloud agents should include:
- Module relationships (not just names, but "A depends on B")
- Hub file paths with dep counts
- Key architectural patterns
- Entry points and data flows

---

### 2F. Cline + Roo Code (shared architecture, UPDATED)

**Market position:** Top VS Code extensions for open-source AI coding.

#### Shared MCP Implementation
Roo Code is a fork of Cline. Their MCP implementations are functionally identical:
- Full tool support
- Resource support
- stdio transport
- Per-tool auto-approve
- Cline config: `cline_mcp_settings.json`
- Roo Code config: `mcp_settings.json`

#### CORRECTION 10: Cline has keyword-based MCP activation via .clinerules

From Cline docs: "When you have a lot of MCP servers enabled, it can be useful to define
when to use each server. Utilize a `.clinerules` file to support intelligent MCP server
activation through keyword-based triggers."

CoDRAG's `.clinerules` should include:
```markdown
When asked about code structure, architecture, dependencies, modules,
hub files, or blast radius, use the CoDRAG MCP tools.
```

#### CORRECTION 11: Roo Code system prompt injection order is documented

Roo Code's exact injection order (confirmed from docs):
1. Language preference
2. Global instructions (Prompts tab)
3. Mode-specific instructions (Prompts tab)
4. Mode-specific rules: `.roo/rules-{modeSlug}/` (recursive, alphabetical)
5. Fallback: `.roorules-{modeSlug}`
6. `.rooignore` instructions
7. **AGENTS.md** (workspace root)
8. General rules: `.roo/rules/` (recursive, alphabetical)
9. Fallback: `.roorules`

AGENTS.md sits between mode-specific and general rules. CoDRAG rules in
`.roo/rules/codrag.md` load AFTER AGENTS.md, so they can reinforce it.

#### CORRECTION 12: Roo Code supports mode-specific CoDRAG rules

Mode-specific rules directories: `.roo/rules-{modeSlug}/`
- `.roo/rules-architect/codrag.md` -- Architect mode specific
- `.roo/rules-code/codrag.md` -- Code mode specific

This enables CoDRAG to give different guidance per mode:
- Architect: "call `codrag` first, use `codrag_audit`"
- Code: "call `codrag_impact` before changes"

#### Local LLM Edge Case (CRITICAL)

Cline and Roo Code have a large user base running **local LLMs** (Ollama, LM Studio). This creates unique challenges:

**Problem 1: Tool-calling quality varies wildly**
- Claude Sonnet 4: excellent tool selection
- GPT-4o: good
- Llama 3.3 70B: adequate
- Qwen3 14B: sometimes struggles with tool selection
- Smaller models (7B): unreliable tool calling

**CoDRAG mitigation:**
- Rules file instructions must be **simple and direct** (no nuance, no conditional logic)
- Tool descriptions must be **short and unambiguous**
- The "call codrag FIRST" instruction should be bold and clear
- Avoid complex tool parameters -- keep schemas minimal

**Problem 2: Small context windows**
- Local LLMs often run with 4K-16K context
- CoDRAG's 5 tool descriptions (~1,400 tokens) consume 10-35% of a 4K context
- Atlas in rules file (~500 tokens) adds more
- Combined: potentially 50% of context on tooling alone

**CoDRAG mitigation:**
- Atlas Tier 1 (minimal, ~150 tokens) for small-context models
- Host detection: if CoDRAG detects a local LLM host, use compact descriptions
- Consider: offer a "lite" mode with only 2-3 tools exposed

**Problem 3: JSON response parsing**
Smaller models struggle with JSON. Another reason to use clean markdown responses.

#### Roo Code Modes (unique opportunity)

Roo Code's **Architect Mode** is a natural fit for CoDRAG:
- Read-only mode focused on planning and design
- Users in Architect Mode actively want structural understanding
- CoDRAG's `codrag` ambient context is exactly what architects need

Mode-specific files are cleaner than embedding hints in one file:
- `.roo/rules/codrag.md` -- general (all modes)
- `.roo/rules-architect/codrag.md` -- architecture focus
- `.roo/rules-code/codrag.md` -- change impact focus

---

## 3. UNIVERSAL OPTIMIZATION STRATEGIES

### 3A. The Universal Rules File Content

All rules files (regardless of format) share the same core. Here is the definitive template:

```markdown
You have access to CoDRAG, a structural code intelligence system that
understands this codebase through a trace graph of imports, calls, and
structural relationships.

ALWAYS call `codrag` (no arguments) at the START of every task. This gives you:
- Module structure (which groups of files work together and their dependencies)
- Hub files (most connected/important files with full content)
- User's selected focus areas from the knowledge base

For specific code lookups, use `codrag_search` with a natural language query.
Before making changes, use `codrag_impact` to understand blast radius.

CoDRAG's tools are read-only and safe to auto-approve.

## Codebase Atlas
[auto-generated from atlas.json -- IDENTITY, STACK, ARCHITECTURE, SUBSYSTEMS, FLOW]

## Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [node_count] nodes, [edge_count] edges | [coverage]% coverage
```

**Token cost:** ~400-700 depending on atlas size. Under 3,000 characters (within all limits).

### 3B. Format Wrapper Per Tool

The core content above is wrapped differently per tool:

| Tool | Wrapper | File |
|------|---------|------|
| Cursor | YAML frontmatter: `alwaysApply: true` | `.cursor/rules/codrag.mdc` |
| Windsurf | YAML frontmatter: `trigger: always_on` | `.windsurf/rules/codrag.md` |
| Claude Code | Plain markdown section | append to `CLAUDE.md` |
| Copilot | Plain markdown | `.github/copilot-instructions.md` |
| AGENTS.md | Plain markdown | `AGENTS.md` section |
| Gemini CLI | Brief directive | MCP `instructions` field + AGENTS.md |
| Cline | Plain markdown | `.clinerules` |
| Roo Code | Plain markdown with mode hints | `.roo/rules/codrag.md` |

### 3C. The Universal Tool Description

Every MCP host sees tool descriptions. They must work across ALL models:

```
codrag: Get structural codebase context -- module map, hub files (most
connected code with full content), and user-selected focus areas. Call this
FIRST at the start of every coding task to understand how files connect to
each other before reading or searching code. Returns compact architecture
overview (~250 tokens). Read-only.
```

Key elements that work universally:
- **"FIRST"** -- activation signal that works in every system prompt
- **"module map, hub files"** -- concrete deliverables
- **"how files connect"** -- differentiates from grep/search
- **"~250 tokens"** -- cost signal reassures AI it's cheap
- **"Read-only"** -- safety signal for auto-approve

### 3D. The Universal MCP Instructions Field

For hosts that support it (Gemini CLI confirmed, Claude Code likely):

```
CoDRAG provides structural codebase context via trace graph analysis.
Call `codrag` at the start of every coding task for module structure,
hub files, and focus areas. Use `codrag_search` for code queries with
structural expansion. Use `codrag_impact` before changes. All tools
are read-only. Categories: code intelligence, architecture, dependencies.
```

The "Categories:" line at the end is specifically for Claude Code's MCP Tool Search -- it helps Claude find CoDRAG tools when they're deferred.

### 3E. Response Format (Universal Markdown)

Every response from every CoDRAG tool must be clean markdown:

```markdown
## CoDRAG: ProjectName (547 nodes, 656 edges)

### Modules
- **Core Engine** (89 files): indexing, search, trace graph -> API Layer
- **API Layer** (24 files): REST endpoints -> Core Engine, Dashboard

### Hub Files
1. `src/core/index.py` (42 deps) [SELECTED]
2. `src/core/trace.py` (38 deps)
3. `src/server.py` (35 deps)

### Focus Areas
- `src/core/` (89 files selected)
- `docs/ARCHITECTURE.md` (selected)

### Health
Index: fresh (12m ago) | Watch: active | Coverage: 92%
```

**Why this specific format works universally:**
- `##` headers: every model uses these to organize scanning
- `**Bold**` for module names: attention anchor
- `->` for dependencies: universally understood as "connects to"
- Backtick paths: every coding model recognizes these as file paths
- `[SELECTED]` label: tells AI this has double significance (user chose + hub)
- Compact: ~250 tokens regardless of project size (hub list is capped)

---

## 4. EDGE CASES & PITFALLS

### 4A. User has AGENTS.md with existing content

**Problem:** CoDRAG generates AGENTS.md section, but user already has AGENTS.md with their own instructions.

**Solution:** Marker-based section management:
```markdown
<!-- CODRAG:BEGIN (auto-generated, do not edit between markers) -->
## CoDRAG Integration
[content]
<!-- CODRAG:END -->
```

CoDRAG only touches content between markers. Everything else is preserved.

### 4B. User has both .cursor/rules/codrag.mdc AND AGENTS.md

**Problem:** Duplicate CoDRAG instructions. AI sees the same content twice.

**Not actually a problem:** Redundancy is cheap (~400 tokens) and beneficial. If one mechanism fails, the other catches it. The AI handles duplicate instructions gracefully -- it just reinforces the behavior.

### 4C. CoDRAG index not built yet

**Problem:** Rules file says "call codrag FIRST" but index doesn't exist. First tool call fails.

**Solution (from PLAN.md):** Return helpful markdown instead of error:
```markdown
## CoDRAG: ProjectName (setup in progress)

The codebase index hasn't been built yet. To build:
1. Open CoDRAG dashboard (http://localhost:8400)
2. Click "Rebuild Knowledge Base"

For now, work with read_file and grep_search until the index is ready.
```

Critical: `isError: false` -- this is a successful response, not a failure.

### 4D. Multiple projects in workspace

**Problem:** User has a monorepo or multiple projects. Which project does CoDRAG serve context for?

**Solution:** CoDRAG's MCP server already has `_resolve_project_id()` logic. The rules file can include the project identifier:
```markdown
CoDRAG project: MyProject (id: abc123)
If working on a different project, specify: codrag_search(project="other_project", query="...")
```

### 4E. Stale atlas in rules file

**Problem:** Atlas was generated 3 days ago. Code has changed significantly.

**Solution:**
1. Timestamp in rules file: `Last indexed: 2026-03-14T17:30Z`
2. AI sees the timestamp and can assess staleness
3. Rules file includes: "If the index seems stale, the `codrag` tool call returns fresh data."
4. Atlas is regenerated on every pipeline completion

### 4F. Tool response exceeds Claude Code's output limit

**Problem:** Very large project, many hub files, response exceeds 25K tokens.

**Solution:** CoDRAG already has LOD compression and budget management. The `_assemble_ambient_context()` function caps output. We should add an explicit token budget cap (~5K tokens for ambient context, ~10K for search results) that respects the lowest common denominator across hosts.

### 4G. Claude Code defers CoDRAG tools (Tool Search)

**Problem:** User has 20+ MCP servers. Claude Code defers CoDRAG tools. AI doesn't know to search for them.

**Solution (layered):**
1. `CLAUDE.md` says "Call `codrag` FIRST" -- always in context regardless of tool deferral
2. MCP `instructions` field includes category hints for Tool Search
3. User can set `ENABLE_TOOL_SEARCH=false` to disable deferral (if they have few servers)
4. CoDRAG is unlikely to be deferred in practice -- most users have <10 MCP servers

### 4H. Local LLM doesn't support tool calling

**Problem:** User runs a small local model via Cline that doesn't support function calling.

**Solution:** This is outside CoDRAG's control. The rules file still works (it's in the system prompt), but the AI can't call tools. The atlas in the rules file provides structural context even without tool calls. This is the "graceful degradation" path.

### 4I. Conflicting instructions from multiple rules files

**Problem:** User has AGENTS.md saying "call codrag first" AND `.cursor/rules/codrag.mdc` saying the same. Plus their own rules saying "never call external tools."

**Solution:** CoDRAG can't control user rules. Our rules should be assertive but not aggressive. Use "ALWAYS" for the initial call, but don't repeat instructions excessively. If a user explicitly disables CoDRAG in their rules, that's their choice.

---

## 5. IMPLEMENTATION PRIORITY (UNIVERSAL FIRST)

### Phase 1: Universal (works for ALL tools, ~4h)

| # | Action | Reaches |
|---|--------|---------|
| 1 | Add `instructions` field to MCP initialize | Gemini CLI, Claude Code, Qwen Code |
| 2 | Generate `AGENTS.md` section with atlas | 20+ tools including Windsurf, Cursor, Copilot |
| 3 | Switch tool responses from JSON to markdown | ALL tools |
| 4 | Improve tool descriptions (self-contained, with cost/safety signals) | ALL tools |
| 5 | Host detection via `clientInfo.name` | ALL tools (enables adaptive behavior) |

### Phase 2: Top 3 (Cursor, Windsurf, Claude Code, ~3h)

| # | Action | Reaches |
|---|--------|---------|
| 6 | Generate `.cursor/rules/codrag.mdc` | Cursor |
| 7 | Generate `.windsurf/rules/codrag.md` | Windsurf |
| 8 | Append section to `CLAUDE.md` | Claude Code |
| 9 | Marker-based section management (don't overwrite user content) | All file-based |

### Phase 3: Extended (Copilot, Cline, Roo Code, ~2h)

| # | Action | Reaches |
|---|--------|---------|
| 10 | Generate `.github/copilot-instructions.md` | Copilot |
| 11 | Generate `.clinerules` section | Cline |
| 12 | Generate `.roo/rules/codrag.md` with mode hints | Roo Code |

### Phase 4: Polish (~2h)

| # | Action | Reaches |
|---|--------|---------|
| 13 | Implement MCP Resources (atlas, health) | Gemini CLI, Claude Code, Cursor |
| 14 | Implement MCP Prompts (slash commands) | Gemini CLI, Claude Code |
| 15 | Adaptive atlas tiers (compact for local LLMs) | Cline, Roo Code |
| 16 | Auto-approve setup instructions in generated files | ALL tools |

---

## 6. VERIFICATION MATRIX

### What to test for each tool

| Test | Cursor | Windsurf | Claude Code | Gemini CLI | Copilot | Cline |
|------|--------|----------|-------------|-----------|---------|-------|
| Rules file injected on every prompt | `.mdc` | `.windsurf/rules/` | `CLAUDE.md` | `AGENTS.md` | `.github/` | `.clinerules` |
| AGENTS.md read correctly | ? | YES | YES | YES | YES | ? |
| MCP `instructions` appended to system prompt | ? | ? | likely | **YES** | ? | ? |
| `codrag` called on first prompt | test | test | test | test | test | test |
| Auto-approve works | per-server | per-server | `mcp__codrag` | `trust:true` | ? | per-tool |
| Parallel `codrag` + `codrag_search` | test | test | test | test | ? | test |
| Markdown response renders correctly | test | test | test | test | test | test |
| `clientInfo.name` value | capture | capture | capture | capture | capture | capture |
| Tool Search deferral behavior | N/A | N/A | test | N/A | N/A | N/A |
| Local LLM tool calling works | N/A | N/A | N/A | N/A | N/A | test |

---

## 7. EMPIRICAL TEST PLAN

Before implementation, these items MUST be validated hands-on. Organized by priority.

### Priority 1: Blocking (must validate before Phase 1 implementation)

| # | Test | Tool | Method | Expected |
|---|------|------|--------|----------|
| T1 | `clientInfo.name` value | ALL | Add logging to MCP server's initialize handler | Capture exact strings |
| T2 | MCP `instructions` field appended to system prompt | Gemini CLI | Add instructions, check if AI behavior changes | Instructions guide first tool call |
| T3 | MCP `instructions` field behavior | Cursor | Same test | Unknown -- may be ignored |
| T4 | MCP `instructions` field behavior | Windsurf | Same test | Unknown -- may be ignored |
| T5 | MCP `instructions` field behavior | Claude Code | Same test | Likely appended (full MCP spec) |
| T6 | AGENTS.md with markers doesn't break tool reading | ALL | Create AGENTS.md with CODRAG:BEGIN/END markers, verify tools parse it | Clean load, no errors |

### Priority 2: Important (validate before Phase 2)

| # | Test | Tool | Method | Expected |
|---|------|------|--------|----------|
| T7 | `.cursor/rules/codrag.mdc` with `alwaysApply: true` injected every prompt | Cursor | Create file, ask AI "what rules do you see?" | Content visible in system prompt |
| T8 | `.windsurf/rules/codrag.md` with `trigger: always_on` injected | Windsurf | Same | Content visible every message |
| T9 | CLAUDE.md section append doesn't break existing content | Claude Code | Create CLAUDE.md with user content + CoDRAG markers | Both sections present |
| T10 | `mcp__codrag` permission auto-approves all tools | Claude Code | Set permission, call tools | No confirmation prompts |
| T11 | Cursor MCP auto-run per server | Cursor | Enable for codrag, call tool | No confirmation |
| T12 | Copilot sandboxing auto-approve | Copilot (macOS) | Config with `sandboxEnabled: true` | Auto-approved calls |

### Priority 3: Nice-to-have (validate before Phase 3)

| # | Test | Tool | Method | Expected |
|---|------|------|--------|----------|
| T13 | `.clinerules` keyword triggers work | Cline | Add keyword content, test with structural query | CoDRAG tools called |
| T14 | `.roo/rules-architect/codrag.md` loads in Architect mode | Roo Code | Create mode-specific file, switch to Architect | Content visible |
| T15 | Roo Code AGENTS.md loading order | Roo Code | Both AGENTS.md and .roo/rules/ present | Correct injection order |
| T16 | Claude Code MCP Tool Search deferral | Claude Code | Configure 15+ MCP servers, check if codrag is deferred | Verify CLAUDE.md mitigates |
| T17 | MCP Resources discoverable | Gemini CLI | Implement codrag://atlas, check `@codrag://atlas` | Resource content returned |
| T18 | MCP Prompts as slash commands | Gemini CLI | Implement /codrag-overview, test in Gemini CLI | Slash command works |
| T19 | Local LLM tool calling via Cline | Cline + Ollama | Connect Llama 3.3 70B, test codrag tool call | Tool selected and called |
| T20 | Copilot Windows (no sandbox) manual approve | Copilot (Windows) | Test without sandbox | Confirmation dialog works |

### Test Environment Setup

```bash
# Add logging to MCP server for T1
# In src/codrag/mcp/server.py, log clientInfo from initialize request
import logging
logger = logging.getLogger("codrag.mcp")
# In initialize handler:
# logger.info(f"Client: {request.client_info}")
```

### clientInfo.name Predictions

| Tool | Predicted `clientInfo.name` | Confidence |
|------|---------------------------|------------|
| Cursor | `"cursor"` or `"Cursor"` | Medium |
| Windsurf | `"windsurf"` or `"cascade"` | Medium |
| Claude Code | `"claude-code"` or `"claude"` | Medium |
| Copilot (VS Code) | `"vscode"` or `"copilot"` | Low |
| Gemini CLI | `"gemini-cli"` | Medium |
| Cline | `"cline"` | High |
| Roo Code | `"roo-code"` or `"roo-cline"` | Medium |

---

## 8. KEY TAKEAWAYS (UPDATED)

### Corrections Summary (12 total)

| # | Correction | Impact |
|---|-----------|--------|
| 1 | Windsurf rules are `.windsurf/rules/*.md` not `.windsurfrules` | Rules generation target changed |
| 2 | Windsurf 100-tool limit | CoDRAG's 5 tools safe; users near limit need awareness |
| 3 | Windsurf Cascade Hooks (pre/post MCP tool use) | Future analytics opportunity |
| 4 | Cursor YOLO mode does NOT auto-approve MCP | Setup docs must be explicit |
| 5 | Claude Code MCP Tool Search defers tools | CLAUDE.md + instructions field mitigate |
| 6 | Claude Code 25K token MCP output limit | CoDRAG responses are safe (250-3K) |
| 7 | Claude Code `mcp__codrag` permission syntax | Single rule auto-approves all tools |
| 8 | Copilot config uses `servers` key, NOT `mcpServers` | Copy-paste trap for users |
| 9 | Copilot sandboxing = auto-approve (macOS/Linux only) | Best auto-approve path for Copilot |
| 10 | Cline keyword-based MCP activation via .clinerules | Include trigger keywords in rules |
| 11 | Roo Code system prompt injection order documented | AGENTS.md before general rules |
| 12 | Roo Code mode-specific rules directories | Architect/Code mode CoDRAG variants |

### Top 10 Takeaways

1. **AGENTS.md is the single highest-ROI file.** 20+ tools read it. Root-level = always-on in Windsurf. Stewarded by the Linux Foundation (Agentic AI Foundation). 60,000+ open-source projects use it. It's the universal fallback for everything.

2. **MCP `instructions` field is free money.** Zero user setup, protocol-level injection. Confirmed working in Gemini CLI. Implement immediately.

3. **Cursor YOLO mode trap.** Users will assume YOLO auto-approves MCP. It doesn't. Setup docs must be explicit.

4. **Claude Code Tool Search trap.** Many MCP servers = deferred tools. CLAUDE.md and instructions field mitigate.

5. **Windsurf rules location changed.** `.windsurfrules` is legacy. New path: `.windsurf/rules/*.md` with YAML frontmatter.

6. **Copilot config key trap.** `.vscode/mcp.json` uses `servers` key, not `mcpServers`. Users copying from other tools' docs will fail silently.

7. **Copilot sandboxing is the best auto-approve.** `sandboxEnabled: true` auto-approves safely. CoDRAG is read-only = perfect sandbox candidate. But Windows users are excluded.

8. **Local LLM users are a real segment.** Cline + Roo Code serve them. Compact atlas + simple descriptions critical. Keyword trigger phrases in `.clinerules` help weaker models.

9. **Roo Code Architect Mode is a CoDRAG showcase.** Mode-specific rules (`.roo/rules-architect/codrag.md`) let us give architecture-focused guidance. This is a differentiation opportunity.

10. **Redundancy is a feature.** AGENTS.md + tool-specific file + instructions field + tool descriptions = 4 layers. Each catches tools the others miss. Cloud agents (Jules, Copilot coding agent, Devin) only get AGENTS.md, making atlas self-sufficiency critical.

# Prep Integration Research: AI Coding Tool Landscape

> Comprehensive research into how each AI coding tool consumes MCP, interprets context, and what Prep must do to deliver universal structural intelligence across the entire ecosystem.

**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Why This Research Matters

Prep's MCP server delivers structural codebase context (trace graph, modules, hub files, atlas) to AI coding tools. But "MCP support" is not uniform -- each tool has:

- **Different MCP implementation maturity** (full spec vs. tools-only vs. partial)
- **Different system prompts** that shape how the AI interprets external context
- **Different rules/instruction file formats** (.cursor/rules/*.mdc, CLAUDE.md, AGENTS.md, .windsurf/rules/*.md, GEMINI.md, etc.)
- **Different context window sizes and management strategies** (compaction, summarization, truncation)
- **Different approval/trust models** for MCP tool execution
- **Different native tools** that Prep competes with for attention

Understanding these differences is critical for:
1. **Universal context format** -- Prep's markdown output must read well regardless of which AI interprets it
2. **Rules file generation** -- Prep must auto-generate the right instruction file for each tool
3. **Tool description optimization** -- descriptions must activate correctly across different system prompts
4. **Atlas design** -- the structural overview must prime diverse AI models effectively

---

## 2. Tool Classification

### Tier 1: Primary Targets (large user base, full MCP support)

| Tool | Type | MCP Support | Rules File | Vendor |
|------|------|-------------|------------|--------|
| **Cursor** | IDE (VS Code fork) | Full (tools, resources, prompts, roots, elicitation, apps) | `.cursor/rules/*.mdc` | Anysphere |
| **Windsurf** | IDE (VS Code fork) | Full (tools, resources), 100-tool limit | `.windsurf/rules/*.md` (frontmatter) + `AGENTS.md` | Codeium (now Cognition) |
| **Claude Code** | CLI agent | Full (tools, resources, prompts) | `CLAUDE.md` + `AGENTS.md` | Anthropic |
| **GitHub Copilot** | IDE extension + agent | Tools + agent mode | `.github/copilot-instructions.md` + `AGENTS.md` | GitHub/Microsoft |
| **Gemini CLI** | CLI agent | Full (tools, resources, prompts, instructions) | `GEMINI.md` + `AGENTS.md` | Google |

### Tier 2: Growing Ecosystem (significant adoption, good MCP support)

| Tool | Type | MCP Support | Rules File | Vendor |
|------|------|-------------|------------|--------|
| **Cline** | VS Code extension | Full (tools, resources) | `.clinerules` | Community (open source) |
| **Roo Code** | VS Code extension | Full (tools, resources) | `.roo/rules/` + `AGENTS.md` | Roo Code Inc |
| **Continue** | VS Code/JetBrains extension | Full (tools, resources) | `config.yaml` rules | Continue.dev |
| **Zed** | Native editor | Tools + partial resources | `.rules` files + `AGENTS.md` | Zed Industries |
| **Qwen Code** | CLI agent | Full (tools, resources, prompts) | `AGENTS.md` | Alibaba |

### Tier 3: Emerging / Specialized

| Tool | Type | MCP Support | Rules File | Vendor |
|------|------|-------------|------------|--------|
| **DeepAgents** | Python agent harness | Via langchain-mcp-adapters | N/A (programmatic) | LangChain |
| **Aider** | CLI pair programmer | Via MCP servers (consumer) | `.aider.conf.yml` `read:` + `AGENTS.md` | Community |
| **Amp** | CLI/IDE agent | Full MCP | `AGENTS.md` | Sourcegraph |
| **Google Jules** | Async cloud agent | API-based (MCP via wrapper) | `AGENTS.md` | Google |
| **OpenHands** | Cloud agent platform | Partial | Custom config | All Hands AI |
| **Devin** | Cloud agent | Partial | `AGENTS.md` | Cognition |
| **Kilo Code** | VS Code extension | Full MCP | `AGENTS.md` | Kilo Code |
| **Junie** | JetBrains IDE agent | MCP support | `.junie/guidelines.md` + `AGENTS.md` | JetBrains |
| **OpenAI Codex** | CLI agent | Full MCP | `AGENTS.md` | OpenAI |

---

## 3. Research Framework

For each tool, we investigate these dimensions:

### A. MCP Implementation
- **Spec version** supported (2024-11-05, 2025-03-26, 2025-06-18)
- **Primitives**: Tools / Resources / Prompts / Roots / Sampling / Elicitation
- **Transport**: stdio / SSE / Streamable HTTP
- **Tool limit**: max tools before degradation
- **Schema processing**: what gets stripped/sanitized from tool definitions
- **Confirmation model**: auto-approve options, trust settings
- **MCP server instructions**: does the host read `instructions` from server capabilities?

### B. System Prompt & Context Architecture
- **Base system prompt characteristics**: length, tone, built-in tool awareness
- **How MCP tool descriptions are injected**: inline in system prompt vs. separate tool section
- **Context window size**: model default, compaction strategy
- **Native tools**: what built-in tools compete with Prep (file read, grep, search, etc.)
- **How the AI ranks tool priority**: native vs. MCP, familiar vs. unknown

### C. Rules/Instruction File
- **File name and location**: exact path the tool reads
- **Format**: YAML frontmatter, plain markdown, structured config
- **Injection behavior**: always-on vs. conditional vs. on-demand
- **Scope**: global, project, directory-level
- **AGENTS.md support**: does the tool read the emerging standard?
- **Prep generation target**: what file should Prep auto-generate?

### D. Context Interpretation
- **Markdown rendering**: does the AI see raw markdown or parsed structure?
- **JSON handling**: does the AI parse JSON tool responses well?
- **Code block treatment**: how does the AI handle code in tool responses?
- **Token efficiency**: what response format minimizes waste for this tool's model?
- **Multi-turn decay**: how quickly does tool response context scroll out?

### E. Prep-Specific Considerations
- **Optimal response format**: markdown vs. JSON vs. hybrid
- **Rules file template**: exact content for this tool
- **Auto-approve recommendation**: how to configure trust for read-only Prep tools
- **Parallel tool calls**: does this tool support calling `prep` + `prep_search` simultaneously?
- **Known quirks**: anything that breaks or degrades Prep's output

---

## 4. The AGENTS.md Standard (Critical Discovery)

**AGENTS.md** is an open standard stewarded by the **Agentic AI Foundation** under the **Linux Foundation**. Used by **60,000+ open-source projects** on GitHub. Think of it as a README for AI agents.

Emerged from collaborative efforts across OpenAI Codex, Amp, Jules (Google), Cursor, and Factory.ai.

### Who reads AGENTS.md (confirmed, 22+ tools):
- OpenAI Codex
- Google Jules
- Google Gemini CLI
- GitHub Copilot (coding agent)
- Factory.ai
- Aider (via `read:` directive in `.aider.conf.yml`)
- Goose (Block)
- opencode
- Zed
- Warp
- VS Code (native -- includes Copilot agent mode)
- Devin (Cognition)
- Junie (JetBrains)
- Amp (Sourcegraph)
- Cursor
- Roo Code (default on, disableable via `roo-cline.useAgentRules: false`)
- Kilo Code
- Windsurf (root = always-on, subdirectory = auto-glob)
- Augment Code
- Semgrep
- UiPath (Autopilot & Coded Agents)
- Phoenix

### Who does NOT read AGENTS.md:
- **Claude Code** -- reads `CLAUDE.md` (but also reads `AGENTS.md` as of recent updates)
- **Cline** -- reads `.clinerules`
- **Continue** -- reads `config.yaml` rules
- **DeepAgents** -- programmatic configuration only

### Implication for Prep:
Prep should generate **both** `AGENTS.md` (universal) **and** tool-specific files (`CLAUDE.md`, `.cursor/rules/prep.mdc`, `.windsurf/rules/prep.md`) for maximum coverage. The AGENTS.md content can be a subset focused on Prep tool instructions.

---

## 5. MCP Server Instructions (Critical Discovery)

The MCP spec (2025-06-18) includes an `instructions` field in the server's `initialize` response. This text gets appended to the host's system instructions.

### Who supports MCP server instructions:
- **Gemini CLI** -- confirmed: "will be appended to the system instructions"
- **Claude Code** -- supported via MCP spec compliance
- **Qwen Code** -- likely (mirrors Gemini CLI architecture closely)

### Who likely ignores them:
- **Cursor** -- not documented
- **Windsurf** -- not documented

### Implication for Prep:
Prep's MCP server should include an `instructions` field in its initialize response:

```json
{
  "serverInfo": { "name": "prep", "version": "2.0.0" },
  "instructions": "Prep provides structural codebase context. Call `prep` at the start of every task for module structure and hub files. Use `prep_search` for specific code queries.",
  "capabilities": { "tools": {}, "resources": {} }
}
```

This is a **zero-cost always-on mechanism** for tools that support it -- no rules file needed, the instruction is injected automatically via the MCP protocol itself.

---

## 6. Cross-Tool Comparison Matrix

### MCP Primitive Support

| Tool | Tools | Resources | Prompts | Roots | Instructions | Elicitation |
|------|-------|-----------|---------|-------|-------------|-------------|
| Cursor | YES | YES | YES | YES | ? | YES |
| Windsurf | YES | YES | ? | YES | ? | ? |
| Claude Code | YES | YES | YES | YES | YES | ? |
| Gemini CLI | YES | YES | YES | YES | **YES** | ? |
| Qwen Code | YES | YES | YES | YES | likely | ? |
| Copilot | YES | ? | ? | ? | ? | ? |
| Cline | YES | YES | ? | YES | ? | ? |
| Roo Code | YES | YES | ? | YES | ? | ? |
| Continue | YES | YES | ? | ? | ? | ? |
| Zed | YES | partial | ? | ? | ? | ? |
| Aider | consumer | ? | ? | ? | ? | ? |
| DeepAgents | via adapter | ? | ? | ? | ? | ? |

### Rules File Landscape

| Tool | Primary File | Secondary | AGENTS.md | Prep Should Generate |
|------|-------------|-----------|-----------|----------------------|
| Cursor | `.cursor/rules/*.mdc` | -- | YES | `.cursor/rules/prep.mdc` |
| Windsurf | `.windsurf/rules/*.md` | -- | YES (root=always-on) | `.windsurf/rules/prep.md` |
| Claude Code | `CLAUDE.md` | `MEMORY.md` (auto) | YES | section in `CLAUDE.md` |
| Gemini CLI | `GEMINI.md` | `.gemini/settings.json` | YES | `GEMINI.md` section |
| Copilot | `.github/copilot-instructions.md` | -- | YES | `.github/copilot-instructions.md` |
| Qwen Code | -- | `settings.json` | YES | `AGENTS.md` |
| Cline | `.clinerules` | -- | ? | `.clinerules` section |
| Roo Code | `.roo/rules/*.md` | -- | YES | `.roo/rules/prep.md` |
| Aider | `.aider.conf.yml` read: | -- | YES | `AGENTS.md` |
| Amp | -- | -- | YES | `AGENTS.md` |
| Zed | `.rules` | -- | YES | `AGENTS.md` |
| Universal | **`AGENTS.md`** | -- | -- | **ALWAYS generate** |

### Confirmation/Trust Models

| Tool | Default | Auto-approve option | Prep recommendation |
|------|---------|--------------------|-----------------------|
| Cursor | Confirm each | Per-server auto-run in settings | Enable auto-run for prep server |
| Windsurf | Confirm each | Per-server allow in settings | Enable auto-run for prep |
| Claude Code | Confirm each | `"allow": ["mcp__prep"]` in permissions | `"allow": ["mcp__prep"]` (covers ALL tools) |
| Gemini CLI | Confirm each | `trust: true` per server | `"trust": true` for prep |
| Qwen Code | Confirm each | `trust: true` per server | `"trust": true` for prep |
| Cline | Confirm each | Auto-approve per tool | Enable for prep tools |
| Copilot | Confirm each | Sandboxing (`sandboxEnabled: true`, macOS/Linux) | Sandbox for auto-approve (not on Windows) |
| Roo Code | Confirm each | Auto-approve per server | Enable for prep |

---

## 7. Context Format Universality Analysis

### What format works best across ALL tools?

**Markdown is the universal winner.** Every tool's underlying LLM processes markdown natively:
- Headers (`##`) create scannable structure
- Code blocks (`` ``` ``) preserve formatting
- Lists convey structured data concisely
- Bold/emphasis highlights critical info

**JSON is universally worse** for AI consumption:
- Every model must parse JSON structure to extract content
- JSON metadata (keys like `chunks_used`, `total_chars`) wastes tokens
- JSON doesn't benefit from markdown-aware processing in system prompts

**Code blocks with metadata headers** are the optimal format for Prep responses:

```
## Prep: ProjectName (547 nodes, 656 edges)

### Modules
- **Core Engine** (89 files): indexing, search, trace graph
  -> API Layer, Dashboard
- **API Layer** (24 files): REST endpoints, middleware
  -> Core Engine

### Hub Files
1. `src/core/index.py` (42 deps) -- search index, context assembly
2. `src/core/trace.py` (38 deps) -- trace graph, structural queries

### Health
Index: fresh (12m ago) | Watch: active | Coverage: 92%
```

This format:
- Is ~250 tokens (compact)
- Scans well in any model's context window
- Contains zero diagnostic noise
- Uses the same vocabulary the AI already understands (files, deps, modules)
- Works identically in Cursor, Claude Code, Gemini CLI, and every other tool

---

## 8. The Universal Rules File Strategy

Prep should generate **multiple files** from a single template, adapting format per tool:

### Always Generate:

**1. `AGENTS.md` section** (universal -- 20+ tools read this):
```markdown
## Prep Integration

This project is indexed by Prep for structural code intelligence.

### MCP Tools Available
- `prep` -- Call FIRST on every task. Returns module structure, hub files, focus areas.
- `prep_search` -- Natural language code search with structural trace expansion.
- `prep_impact` -- Blast radius analysis. Call before making changes.
- `prep_audit` -- Codebase health audit and refactor guidance.

### Codebase Atlas
[auto-generated structural overview here]

### Focus Areas
[user-selected file paths here]
```

**2. `.cursor/rules/prep.mdc`** (Cursor-specific, `alwaysApply` frontmatter):
```yaml
---
description: Prep structural codebase intelligence
alwaysApply: true
---
[same content as AGENTS.md section]
```

**3. `CLAUDE.md` section** (Claude Code):
```markdown
## Prep
[same content -- Claude Code reads CLAUDE.md at session start]
```

### Conditionally Generate (if tool detected):

**4. `.windsurf/rules/prep.md`** (Windsurf)
**5. `GEMINI.md` section** (Gemini CLI)
**6. `.github/copilot-instructions.md`** (GitHub Copilot)
**7. `.clinerules` section** (Cline)
**8. `.roo/rules/prep.md`** (Roo Code)

### Detection Logic:
```python
def detect_tools(project_path: Path) -> List[str]:
    tools = ["agents_md"]  # Always
    if (project_path / ".cursor").exists():
        tools.append("cursor")
    if (project_path / ".windsurf").exists():
        tools.append("windsurf")
    if (project_path / "CLAUDE.md").exists():
        tools.append("claude_code")
    if (project_path / "GEMINI.md").exists():
        tools.append("gemini_cli")
    if (project_path / ".github").exists():
        tools.append("copilot")
    if (project_path / ".clinerules").exists():
        tools.append("cline")
    if (project_path / ".roo").exists():
        tools.append("roo_code")
    return tools
```

---

## 9. Key Findings That Change Our Strategy

### Finding 1: MCP Server Instructions are underutilized
Gemini CLI (and likely Claude Code, Qwen Code) will append our `instructions` field to the system prompt automatically. This is a **free always-on mechanism** that requires zero file generation. We should implement this immediately.

### Finding 2: AGENTS.md is the new universal standard
With 20+ tools reading AGENTS.md, this is the single highest-reach file we can generate. It supersedes tool-specific files for most of the ecosystem.

### Finding 3: Qwen Code mirrors Gemini CLI architecture
Qwen Code's MCP docs are structurally identical to Gemini CLI's (same sections, same architecture descriptions). This strongly suggests they forked the same codebase. Any behavior we confirm in Gemini CLI likely applies to Qwen Code.

### Finding 4: Tool approval friction is solvable per-tool
Every major tool has a trust/auto-approve mechanism. Prep's setup docs should include per-tool auto-approve instructions. The rules file itself should include a comment with setup instructions.

### Finding 5: Sub-agent architectures need different context
Claude Code (skills, subagents), DeepAgents (task delegation), and Amp (librarian subagent) can spawn sub-agents with isolated context windows. Prep's compact ambient response (~250 tokens) is ideal for sub-agent injection -- small enough to include in every sub-agent's context without waste.

### Finding 6: Context compaction destroys tool responses first
Claude Code's `/compact` and Gemini CLI's context management summarize older messages. MCP tool responses from early turns get compressed or dropped. The atlas in the rules file (always-on, never compacted) is the solution -- it persists across all turns.

---

## 10. Updated Priority Actions

| # | Action | Impact | Effort | Reach |
|---|--------|--------|--------|-------|
| 1 | Add `instructions` field to MCP server `initialize` response | HIGH | 30min | Gemini CLI, Claude Code, Qwen Code |
| 2 | Generate `AGENTS.md` with Prep section + atlas | **CRITICAL** | 2h | 20+ tools |
| 3 | Generate `.cursor/rules/prep.mdc` with `alwaysApply: true` | HIGH | 1h | Cursor |
| 4 | Append Prep section to `CLAUDE.md` | HIGH | 1h | Claude Code |
| 5 | Switch all tool responses from JSON to markdown | HIGH | 3h | All tools |
| 6 | Generate `.windsurf/rules/prep.md` (with frontmatter) | MEDIUM | 30min | Windsurf |
| 7 | Generate `GEMINI.md` section | MEDIUM | 30min | Gemini CLI |
| 8 | Generate `.github/copilot-instructions.md` | MEDIUM | 30min | Copilot |
| 9 | Implement MCP Resources (structure, atlas, files) | MEDIUM | 4h | Cursor, Claude Code |
| 10 | Implement MCP Prompts (slash commands) | LOW | 2h | Gemini CLI, Claude Code |

---

## 11. Per-Tool Deep Dives

Detailed research for each tool is in the `integrations/` subdirectory:

| File | Tool |
|------|------|
| `integrations/cursor.md` | Cursor |
| `integrations/windsurf.md` | Windsurf / Cascade |
| `integrations/claude-code.md` | Claude Code |
| `integrations/gemini-cli.md` | Gemini CLI |
| `integrations/qwen-code.md` | Qwen Code |
| `integrations/copilot.md` | GitHub Copilot |
| `integrations/cline.md` | Cline |
| `integrations/roo-code.md` | Roo Code |
| `integrations/continue.md` | Continue.dev |
| `integrations/deepagents.md` | DeepAgents (LangChain) |
| `integrations/aider.md` | Aider |
| `integrations/amp.md` | Amp (Sourcegraph) |
| `integrations/zed.md` | Zed |
| `integrations/emerging.md` | Jules, OpenHands, Devin, Junie, Kilo Code, OpenAI Codex |

---

## 12. Open Research Questions

- **Q1**: Does Cursor actually append MCP server `instructions` to the system prompt? (needs empirical test)
- **Q2**: How does Windsurf handle AGENTS.md? (confirmed in agents.md site but Windsurf docs don't mention it)
- **Q3**: What is the effective tool limit in Gemini CLI before model degradation?
- **Q4**: Does Claude Code's `/compact` preserve MCP tool responses or summarize them?
- **Q5**: How do sub-agent systems (Claude Code skills, DeepAgents task) handle MCP tool availability? Do sub-agents inherit MCP access?
- **Q6**: What is the `clientInfo.name` string each tool sends in MCP `initialize`? (needed for host detection)
- **Q7**: Does Copilot's coding agent support MCP resources or only tools?
- **Q8**: How does Aider handle MCP tool responses differently from other tools (it's not an LLM-native agent)?

---

## Appendix A: The Full Tool Ecosystem (as of March 2026)

### IDE-Based
- Cursor, Windsurf, Zed, VS Code (native Copilot), JetBrains (Junie)

### VS Code Extensions
- Cline, Roo Code, Continue, Kilo Code, Augment Code

### CLI Agents
- Claude Code, Gemini CLI, Qwen Code, Aider, OpenAI Codex, Amp, OpenCode, Goose

### Cloud/Async Agents
- Google Jules, Devin, OpenHands, Factory.ai, GitHub Copilot (coding agent)

### Agent Frameworks (Prep as MCP server)
- DeepAgents (LangChain), CrewAI, AutoGen, Semantic Kernel

### Emerging Standards
- AGENTS.md (LF project, universal)
- MCP server instructions (protocol-level)
- Tool description quality (arXiv:2602.14878)

# Aider Integration Research

> How Aider consumes MCP, its git-native architecture, and Prep optimization.

**Status:** PRELIMINARY
**Last updated:** 2026-03-14

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | CLI pair programmer (terminal-based) |
| **Vendor** | Community (open source) |
| **Model** | Any (Claude, GPT, Gemini, DeepSeek, local -- user-configurable) |
| **MCP Spec** | Consumer via MCP server wrappers (not native MCP client) |
| **Transport** | N/A (Aider is typically used as an MCP *server*, not client) |
| **Rules File** | `.aider.conf.yml` + `AGENTS.md` (via `read:` directive) |
| **AGENTS.md** | YES (via `read: AGENTS.md` in `.aider.conf.yml`) |
| **Unique Feature** | Git-native -- every change is a commit |

---

## 2. MCP Relationship: Aider as Server, Not Client

### Important Distinction
Aider's relationship with MCP is **inverted** from other tools:
- Most tools (Cursor, Claude Code, etc.) are **MCP clients** that call Prep's MCP server
- Aider is typically wrapped as an **MCP server** itself, allowing other tools (like Claude Code) to delegate coding tasks to Aider

### Aider as MCP Consumer (Indirect)
Aider doesn't have native MCP client support. To use Prep with Aider:
1. **Via `read:` directive**: Aider can read files into context. Prep could generate a static context file that Aider reads.
2. **Via AGENTS.md**: Aider reads AGENTS.md when configured with `read: AGENTS.md`
3. **Via shell commands**: Aider can run shell commands. A `prep context` CLI command could pipe output into Aider's context.

### Integration Pattern
```yaml
# .aider.conf.yml
read:
  - AGENTS.md          # Prep atlas + instructions
  - .prep/context.md # Static context snapshot (optional)
```

---

## 3. Static Context Strategy for Aider

Since Aider can't call MCP tools dynamically, Prep should support a **static context export**:

```bash
# Prep CLI generates a static context file
prep export --format markdown --output .prep/context.md
```

This file contains:
- Atlas (structural overview)
- Module map
- Hub file list (paths + connectivity)
- Focus areas

Aider reads this at session start via `.aider.conf.yml`:
```yaml
read:
  - .prep/context.md
```

### Regeneration
The static file is regenerated after each Prep pipeline run. Could be added to `.gitignore` (local only) or committed (shared with team).

---

## 4. AGENTS.md Integration

Aider reads AGENTS.md when configured. The Prep section in AGENTS.md provides:
- Atlas for structural awareness
- Instructions for the AI about the project structure
- Focus areas

This is the **primary integration path** for Aider -- no MCP, just file-based context injection.

---

## 5. Prep Optimization Checklist

- [ ] Implement `prep export` CLI command for static context file
- [ ] Document `.aider.conf.yml` setup with Prep
- [ ] Test AGENTS.md reading in Aider
- [ ] Explore: can Aider run shell commands mid-session to refresh Prep context?
- [ ] Consider: Aider MCP client support (feature request to Aider project?)

---

## 6. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| No dynamic MCP tool calls | HIGH | Static context only. Stale data risk. |
| Static context becomes outdated mid-session | MEDIUM | AGENTS.md atlas + export file are snapshots. |
| Aider users are power users who expect CLI workflows | LOW | `prep export` fits their workflow. |

# Amp (Sourcegraph) Integration Research

> How Amp consumes MCP, its Librarian sub-agent architecture, and Prep optimization.

**Status:** PRELIMINARY
**Last updated:** 2026-03-14

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | CLI agent + IDE (VS Code extension) |
| **Vendor** | Sourcegraph |
| **Model** | Claude Sonnet (primary), others configurable |
| **MCP Spec** | Full MCP support |
| **Transport** | stdio |
| **Rules File** | `AGENTS.md` |
| **AGENTS.md** | YES (confirmed on agents.md site) |
| **Unique Feature** | Librarian sub-agent for cross-repo code understanding |

---

## 2. Key Architecture: Librarian Sub-Agent

Amp's distinguishing feature is the **Librarian** -- a specialized sub-agent that:
- Searches code across the default branch of repositories
- Provides cross-repo code understanding
- Can be explicitly invoked by the main agent

### Prep Implications
- The Librarian overlaps with `prep_search` for code discovery
- However, Prep provides *structural* relationships (trace graph, module dependencies) that the Librarian cannot
- Prep's `prep_impact` (blast radius) is entirely unique -- no Librarian equivalent
- **Positioning**: Prep complements the Librarian by adding structural intelligence to its content search

### Sub-Agent Context
Amp's sub-agents have isolated context windows. Prep's compact 250-token ambient response is ideal for injection into sub-agent contexts.

---

## 3. MCP Implementation

### Full MCP Support
Amp supports MCP tools alongside its built-in tools and Librarian. Configuration follows standard MCP patterns.

### AGENTS.md
Amp reads AGENTS.md as its primary instruction file. The Prep section in AGENTS.md is the primary integration path.

---

## 4. Prep Strategy for Amp

### Differentiation from Librarian
The AGENTS.md instructions should highlight what Prep adds beyond Amp's built-in search:

```markdown
## Prep Integration

Prep provides *structural* code intelligence that complements Amp's Librarian:
- `prep` -- module-level architecture map showing how file groups connect
- `prep_search` -- search with trace expansion (shows structural neighbors, not just text matches)
- `prep_impact` -- blast radius analysis before changes (what depends on what)

Call `prep` first for structural overview. Use `prep_search` when you need
to understand relationships between files, not just find content.
```

---

## 5. Prep Optimization Checklist

- [ ] Test Prep MCP integration in Amp
- [ ] Verify AGENTS.md reading behavior
- [ ] Test Prep alongside Amp's Librarian (complementary, not conflicting)
- [ ] Test in both CLI and VS Code extension modes

---

## 6. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Librarian overlaps with prep_search | MEDIUM | Prep adds structure. Position as complementary. |
| Amp's sub-agent can't access MCP tools | MEDIUM | Needs empirical test. |
| Sourcegraph's code intelligence may make Prep seem redundant | LOW | Prep is local-first, project-scoped, structural. Different value prop. |

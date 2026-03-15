# Amp (Sourcegraph) Integration Research

> How Amp consumes MCP, its Librarian sub-agent architecture, and CoDRAG optimization.

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

### CoDRAG Implications
- The Librarian overlaps with `codrag_search` for code discovery
- However, CoDRAG provides *structural* relationships (trace graph, module dependencies) that the Librarian cannot
- CoDRAG's `codrag_impact` (blast radius) is entirely unique -- no Librarian equivalent
- **Positioning**: CoDRAG complements the Librarian by adding structural intelligence to its content search

### Sub-Agent Context
Amp's sub-agents have isolated context windows. CoDRAG's compact 250-token ambient response is ideal for injection into sub-agent contexts.

---

## 3. MCP Implementation

### Full MCP Support
Amp supports MCP tools alongside its built-in tools and Librarian. Configuration follows standard MCP patterns.

### AGENTS.md
Amp reads AGENTS.md as its primary instruction file. The CoDRAG section in AGENTS.md is the primary integration path.

---

## 4. CoDRAG Strategy for Amp

### Differentiation from Librarian
The AGENTS.md instructions should highlight what CoDRAG adds beyond Amp's built-in search:

```markdown
## CoDRAG Integration

CoDRAG provides *structural* code intelligence that complements Amp's Librarian:
- `codrag` -- module-level architecture map showing how file groups connect
- `codrag_search` -- search with trace expansion (shows structural neighbors, not just text matches)
- `codrag_impact` -- blast radius analysis before changes (what depends on what)

Call `codrag` first for structural overview. Use `codrag_search` when you need
to understand relationships between files, not just find content.
```

---

## 5. CoDRAG Optimization Checklist

- [ ] Test CoDRAG MCP integration in Amp
- [ ] Verify AGENTS.md reading behavior
- [ ] Test CoDRAG alongside Amp's Librarian (complementary, not conflicting)
- [ ] Test in both CLI and VS Code extension modes

---

## 6. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Librarian overlaps with codrag_search | MEDIUM | CoDRAG adds structure. Position as complementary. |
| Amp's sub-agent can't access MCP tools | MEDIUM | Needs empirical test. |
| Sourcegraph's code intelligence may make CoDRAG seem redundant | LOW | CoDRAG is local-first, project-scoped, structural. Different value prop. |

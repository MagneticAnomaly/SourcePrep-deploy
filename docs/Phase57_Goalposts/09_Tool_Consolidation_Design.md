# Phase 57B: Tool Consolidation — Audit + Spaghetti + Goalposts → 2 Tools

> Research document for the consolidation of three overlapping CoDRAG analysis features
> into two distinct tools: **Health Scanner** and **Advisor**.
> 
> See the full implementation plan at the conversation artifact.

## Summary

Three features overlap significantly:
- **Audit** (Phase 43): 11 graph analyzers + LLM synthesis → findings
- **Spaghetti** (Phase 52): 7 weighted signals → per-file refactor urgency scores
- **Goalposts** (Phase 57): LLM planner → forward-looking proposals

**Consolidated into:**
1. **Health Scanner** 🩺 — Audit + Spaghetti (graph-derived diagnostics + file scoring)
2. **Advisor** 🧭 — Goalposts evolved (LLM-powered forward-looking intelligence)

## Key Design Decisions

1. **Shared `ActionItem` model** replaces `Finding`, `FileScore`, and `GoalpostProposal`
2. **Unified "Run Fix / Copy for AI" handoff** on every actionable item
3. **User notes field** on every item (not just Advisor questions)
4. **Clean dependency**: Advisor reads Health Scanner output — no circular dependency
5. **MCP**: `codrag_audit` keeps its name — Advisor is a new `action=advise` sub-action. **Zero new tools** (stays at 6 total)

## Status

- [x] Research & overlap analysis complete
- [x] Consolidation architecture designed
- [ ] User review of plan
- [ ] Implementation (separate phase)

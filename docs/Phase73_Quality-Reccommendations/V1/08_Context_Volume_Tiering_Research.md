# Phase 73.2b — Context Volume Tiering Strategy

> Date: 2026-04-05 | 2.5-tier context budget strategy for the 2026 model landscape

---

## The 2026 Model Landscape

| Tier | Models | Context Window | Our Budget (steady) | Our Budget (orient) | Window % Used |
|------|--------|---------------|--------------------|--------------------|--------------|
| **1** | Claude Opus 4, Gemini 2.5 Pro | **1M tokens** | 50K chars (~12.5K tok) | 75K chars (~18.8K tok) | **1.3-1.9%** |
| **2** | Claude Sonnet 4, GPT-4o, Qwen3 | **200-250K tokens** | 30K chars (~7.5K tok) | 45K chars (~11.3K tok) | **3-5.6%** |
| **2.5** | Local models (Qwen3, Llama 4, etc.) | **250K+ tokens** (floor) | 20K chars (~5K tok) | 30K chars (~7.5K tok) | **2-3%** |

### Key Design Decisions

**Sub-250K models are dropped.** Models with <250K context windows are not useful for agentic coding tasks in 2026. We don't optimize for them.

**Claude Code gets Tier 1.** Claude Code sends `clientInfo.name="claude-code"` for both Opus and Sonnet — we can't distinguish them at the MCP transport level. Since even Sonnet (200K) handles 50K chars easily (6.25% of its window), we give all Claude Code clients the Tier 1 budget. This is a forward-looking bet: Opus is the default for serious work, and Sonnet's window will only grow.

**IDE integrations get Tier 2.** Cursor, Windsurf, and Copilot typically use Sonnet or GPT-4o under the hood. Their context windows are 200K+, but the IDE layer adds its own context (file contents, cursor position, etc.) that competes with our budget. 30K is generous without crowding out IDE context.

**Local models get Tier 2.5.** Cline/Roo/Continue users running Qwen3, Llama 4, or similar. We assume a 250K floor — anyone running a smaller model is already making quality tradeoffs that our budget can't fix. 20K gives them solid structural context.

---

## First-Call Orientation Boost

The first `prep` call in a session gets **50% more context** automatically.

```
Session start → Agent calls prep (first time)
  → Budget = base × 1.5    ← Agent building mental model, needs more
  → Hub files: top 8-12 instead of 5-8
  → Neighbors: LOD 1 (signatures + docstrings) instead of LOD 2 (just signatures)
  → Richer structural graph

Subsequent prep calls
  → Budget = base            ← Agent has orientation, needs less
  → Standard hub/neighbor balance
```

This is the **cheapest form of adaptive delivery** because:
- Zero user configuration needed
- No new tool to learn
- No extra API call overhead
- The boost is exactly when it matters most (first orientation)

### Why NOT a `prep_verbose` tool

We considered and rejected adding a separate verbose tool:

1. **Tool proliferation tax**: Every additional tool costs tokens for the AI to read its description. With 6 tools already, a 7th "same as #1 but bigger" adds confusion.
2. **The AI won't know when to use it**: Without clear task-type detection, agents either always use verbose (wasting tokens on simple tasks) or never use it (falling back to habits).
3. **`max_chars` already exists**: Users and agents can already call `prep(max_chars=60000)` for more context. The parameter is there; it just wasn't well-publicized.
4. **Auto-scaling is smarter**: The first-call boost delivers the right amount at the right time without asking the user to think about it.

---

## Budget Table (Final)

```
MAX_CONTEXT_CHARS = 80,000 (hard cap, raised from 20K)

┌──────────────────────────────────────────────────────────────┐
│ Client              │ Tier │ Orient  │ Steady  │ Max Window │
├──────────────────────────────────────────────────────────────┤
│ Claude Code         │  1   │ 75,000  │ 50,000  │   1M tok   │
│ Gemini CLI          │  1   │ 75,000  │ 50,000  │   1M tok   │
├──────────────────────────────────────────────────────────────┤
│ Cursor              │  2   │ 45,000  │ 30,000  │  200K tok  │
│ Windsurf            │  2   │ 45,000  │ 30,000  │  200K tok  │
│ Windsurf Cascade    │  2   │ 45,000  │ 30,000  │  200K tok  │
│ GitHub Copilot      │  2   │ 36,000  │ 24,000  │  200K tok  │
│ Qwen Code           │  2   │ 36,000  │ 24,000  │  256K tok  │
├──────────────────────────────────────────────────────────────┤
│ Cline (local)       │ 2.5  │ 30,000  │ 20,000  │  250K+ tok │
│ Roo Code (local)    │ 2.5  │ 30,000  │ 20,000  │  250K+ tok │
│ Continue (local)    │ 2.5  │ 30,000  │ 20,000  │  250K+ tok │
├──────────────────────────────────────────────────────────────┤
│ Unknown client      │  2   │ 36,000  │ 24,000  │  unknown   │
└──────────────────────────────────────────────────────────────┘
```

---

## What More Budget Buys (Tier 1 vs Tier 2.5)

At 50K steady, Tier 1 models receive:

| Content | Tier 2.5 (20K) | Tier 2 (30K) | Tier 1 (50K) |
|---------|---------------|-------------|-------------|
| Module hierarchy | Full tiered | Full tiered | Full tiered |
| Hub files (LOD 0) | Top 3-4 | Top 5-6 | Top 8-10 |
| Neighbor files | ~6 at LOD 2 | ~8-10 at LOD 2 | ~15 at LOD 1 |
| Architecture annotations | 1,500 chars | 1,500 chars | Full (no truncation) |
| Concept summaries | Stats only | Stats only | Content available |
| Cross-module chains | — | — | Top 5 import paths |

The extra hub and neighbor coverage at Tier 1 means Opus/Gemini agents can plan multi-file refactors in a single shot instead of needing 3-5 `prep_search` follow-ups.

---

## Future Considerations

### When context windows hit 2-10M (2027+)

The current architecture scales naturally:
- Add new patterns to `_CLIENT_BUDGETS` for 2M+ models
- Raise `MAX_CONTEXT_CHARS` as needed
- The LOD system already has levels 0-4 that can serve more content at higher fidelity

### What we should NOT do even with infinite context

- **Never dump raw source** without LOD compression. Even 10M tokens can't make up for irrelevant content hurting attention.
- **Never include all modules at LOD 0**. A 1400-file codebase at full resolution is ~2M chars. At 1M context, that's 50% of the window with raw code, leaving no room for the agent's own reasoning.
- **Keep curated > comprehensive**. The value of Prep is that it SELECTS the right context, not that it provides ALL context. More budget should mean *richer* context for the same selection, not *broader* selection.

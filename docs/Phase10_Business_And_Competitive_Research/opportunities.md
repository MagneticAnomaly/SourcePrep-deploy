# Opportunities — Phase 10 (Business Plan & Competitive Research)

## Purpose
Track competitive opportunities that should influence roadmap bets.

## Opportunities
- **Treat “local-first + MCP” as table stakes**: ChunkHound exists and is OSS. Prep must win on trust UX, freshness, and product polish.
- **Differentiation to emphasize**:
  - inspectable retrieval UI (status + citations + errors)
  - freshness-first trust loop (stale signals + recovery)
  - trace-assisted grounding for structural questions
- **Watch list**: if ChunkHound ships a polished desktop UI or multi-project registry, the competitive gap narrows.

## Opportunities (product + control-surface implications)
- **Make “trust” measurable**: ensure the product can answer:
  - right project selection
  - freshness
  - verifiability
  as concrete UI primitives and diagnostics, not just marketing claims.
- **Compete on operational polish**: defaults and settings that prevent common failures (batch size, timeouts, watcher fallback) are a durable advantage.
- **Pricing-tier UX hooks**: make “why upgrade?” visible as product affordances:
  - trace-enabled workflows gated behind Pro
  - team policy + config provenance gated behind Team
  - "1-repo limit" friction in Free tier driving the "Starter" upgrade
- **Viral Growth Mechanics**:
  - **"Team Discovery"**: In-app prompt "Is your whole team using Prep?" to drive multi-seat adoption.
  - **"Limited Time" Discount**: Capability to trigger 48h "Founder's Edition" offers during viral spikes.
  - **MCP-first onboarding**: Ensure "1-click connect" for Cursor/Windsurf users to capture viral traffic.

## Opportunities (Emerging Tech Moats)
- **Small Language Models (SLMs)**: Local re-ranking using ~2B param models (Phi-4, Llama 3) to beat cloud RAG quality at zero marginal cost.
- **GraphRAG / Structural Trace**: Move beyond chunk-based retrieval to "relationship-based" answers (Cross-repo imports, function calls).
- **Context Compression**: (LLMLingua) Prune context to save user tokens and improve agent focus.
- **LSP Integration**: Real-time semantic freshness (rename variable = instant index update).

## Opportunities (meaningful visualization)
- **Differentiation demo dashboards**: simple, inspectable “before/after” visuals for:
  - stale vs fresh index state
  - bounded context output vs overflow
  - trace-assisted expansion vs embedding-only
- **Competitive watch list checklist**: maintain a living matrix of “table stakes vs differentiators” and surface it as a planning artifact (not public UI).

## Hazards
- **Copycat positioning**: if we position only on “local-first + MCP”, we’ll blend into existing OSS tools.
- **Over-claiming enterprise readiness**: claiming SSO/audit while it’s not implemented damages trust.
- **Feature creep driven by competitor parity**: chasing every competitor feature can destabilize MVP; maintain strict evaluation criteria.
- **Misaligned incentives**: adding complex features without improving the core loop (add → build → search → context) slows adoption.

## References
- `COMPETITOR_LANDSCAPE.md` (ChunkHound entry)
- https://github.com/chunkhound/chunkhound
- `docs/WORKFLOW_RESEARCH.md` (trust invariants + MVP boundaries)
- `docs/Phase12_Marketing-Documentation-Website/COPY_DECK.md`

# Secondary Pages & Portals UX Audit & Gap Analysis

> **Status**: Audit complete. Resolved items implemented. Remaining items tracked in `MASTER_TODO.md` and `MARKETING_MASTER_TODO.md`.

## 1. Secondary Marketing Pages

### `/pricing` — ✅ FIXED
- **Before**: Free tier listed wrong features. Starter said "3 projects". "100% local" overstated. Code Graph badged as "Pro".
- **After**: Free = 1 project + manual only. Starter = full Pro with 4-month time limit. Trust strip says "Local-first" + BYOK. Path weights and Atlas available to all tiers.

### `/security` & `/privacy` — No changes needed
- Solid, aligned with local-first ethos. No telemetry, privacy policy merged.

### `/about` — ✅ FIXED
- **Before**: Old copy ("structural context layer for AI-assisted development", "100% locally").
- **After**: Rewritten to emphasize multiple retrieval methods, MCP backend, BYOK option.

### `/faq` — Minor TODO
- Content is solid (token budgets, "lost in the middle", context size research).
- TODO: Add Atlas Routing FAQ once Phase 29B confirms token savings. Added to `MARKETING_MASTER_TODO.md`.

### `/download` — No changes needed
- Platform cards, quick start, feature grid. No account required messaging is implicit.

---

## 2. Support & Payments Sites

### Support Portal (`support.codrag.io`) — TODOs Added
- Current: Headless GitHub integration (Discussions/Issues). Read-only.
- TODO: Define private/SLA support for paid tiers. Scope unknown, may not be MVP. Added to `MARKETING_MASTER_TODO.md`.

### Payments Portal (`payments.codrag.io`) — TODO Added
- Current: Lemon Squeezy checkout, recovery, success.
- TODO: Investigate Lemon Squeezy post-purchase flow. Determine if custom offline license delivery copy needed. Added to `MARKETING_MASTER_TODO.md`.

---

## 3. Resolved Answers

1. **Path Weights & Atlas on pricing**: Available to **all tiers** (verified from `feature_gate.py`). No need to list as Pro-exclusive.
2. **Starter tier**: Keep as-is. It's Pro with a 4-month time limit and an impulse-buy price point. Not a separate persona.
3. **Atlas FAQ**: Only add if Phase 29B confirms it actually reduces token usage. Uncertain — added as conditional TODO.
4. **Ollama FAQ**: Do NOT change to "No Ollama required". Ollama is the recommended LLM path for enrichment (far cheaper than BYOK). `nomic-embed-text-v1.5` ONNX built-in is the default embedder. Keep current Ollama-positive messaging.
5. **Private Support**: Needs research — guidance on best plan unknown. Added to `MARKETING_MASTER_TODO.md`.
6. **Debug log export**: YES — add to Security/Privacy page AND FAQ. Added to both `MASTER_TODO.md` and `MARKETING_MASTER_TODO.md`.
7. **License delivery**: Depends on Lemon Squeezy process. Needs investigation. Added to `MARKETING_MASTER_TODO.md`.

---

## 4. Remaining Gaps

- **Support portal scope**: Private/SLA support for paid tiers undefined. (`MARKETING_MASTER_TODO.md`)
- **Debug log export guide**: Needed in Security + FAQ + Troubleshooting. (`MASTER_TODO.md` + `MARKETING_MASTER_TODO.md`)
- **Lemon Squeezy post-purchase flow**: Needs investigation. (`MARKETING_MASTER_TODO.md`)
- **Atlas FAQ**: Conditional on Phase 29B confirming token savings. (`MARKETING_MASTER_TODO.md`)


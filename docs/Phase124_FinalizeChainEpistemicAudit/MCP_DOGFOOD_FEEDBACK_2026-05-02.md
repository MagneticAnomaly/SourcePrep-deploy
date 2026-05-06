# MCP Dogfood Feedback — 2026-05-02

Source: a single `prep` call made at the start of the Phase 125 security audit kickoff.

Call:

```python
prep(
    project_id="f1636374-abc6-410d-99ee-822120379e79",
    task="conduct a full security audit of the SourcePrep codebase — backend (FastAPI, MCP server, daemon), file/SQLite state, and any user-facing surfaces",
    role="security",
)
```

The call was net-positive — it surfaced two prior audit docs (`TEAM_ENTERPRISE_CODE_AUDIT.md`, `SECURITY_DESIGN_DECISIONS.md`), mapped the security surface across three modules (~56 files), and called out concrete attack-surface configs (`tauri.conf.json`, VS Code webview `helper.ts`). The three issues below are the gaps observed in that single response.

---

## 1. Concept promotion pipeline appears stuck — `0 active / 1590 seeds`

**Observed.** Trailer of the response read:

> `[Concepts: 0 active, 1590 seeds — architecture: 350, technical: 235, product: 204, process: 203, +7 more.]`

**Why this matters.**
- 1,590 seeded concepts and zero promoted to `active` strongly suggests the seed → active promotion path is not running, not gating, or has regressed.
- `active` concepts are the substrate for the immune system: constraint concepts with assertions + anchors are what derive antibodies. Zero active concepts ⇒ zero (or stale) antibodies.
- For a security audit specifically, antibodies are the most valuable signal `prep` can produce — runtime defenses derived from "X must never import Y" / "service Z must not call the network" style constraints. We are getting none.
- Cross-references the existing `[Audit/spaghetti pipeline migration]` memory (`run_health_scan` exists unwired). Possible related symptom of the same migration debt.

**What to investigate.**
- Is the promotion job scheduled? Does it run during Finalize? (Phase 124 is Finalize-chain — directly in scope.)
- If it ran, what blocked promotion — missing assertions, missing anchors, confidence thresholds set too high?
- Is the 1,590-seed count growing monotonically (write path works) while active stays at 0 (promotion path broken)?

**Suggested next step.** Add a Finalize-stage assertion that `concepts.active > 0` once the project has been enriched at least once. A persistent 0/N ratio should surface as an alert in `prep`'s ambient context, not be a quiet line in the trailer.

---

## 2. `role="security"` projection leaks unrelated modules into "Modules in scope"

**Observed.** With `role="security"`, the "Modules in scope" section still listed:

- Guerrilla Marketing Copy Engine (13 files)
- Community-Driven User Acquisition Campaign Engine (12 files)
- Developer Community Launch Campaign Engine (10 files)
- Prep Product Go-to-Market Content Engine (9 files)
- Developer-Facing Marketing Content Pipeline (6 files)

…among others, all clearly marketing/content modules with no plausible security relevance.

**Why this matters.**
- The "Relevant Files" block at the bottom *was* correctly weighted (security audit docs, license/payment, Tauri config, webview CSP). So the role weights *are* being applied somewhere in the assembly — just not to the module-list pruning.
- This produces a confused signal for an agent: the most prominent section of the response (the long modules list) is uniform across roles, while only the trailing files-list reflects the role projection. Agents that don't read all the way down will form a generic mental model.
- Token waste: the marketing modules consume a meaningful fraction of the response budget on a security-framed call.

**What to investigate.**
- `src/prep/core/atlas/` — confirm whether role weighting is plumbed into module-list emission or only into the file-ranking layer.
- If by design (separation of "structural map" vs "role-weighted slice"), the trailer should label the modules section as role-agnostic so agents don't over-weight it.

**Suggested next step.** Either (a) apply the role weights to module ordering and truncate below a threshold, or (b) explicitly label the modules section as "uniform / role-independent" so consumers know not to interpret it as a security-scoped index.

---

## 3. No antibody / immune-system alerts surfaced on a security-framed `prep` call

**Observed.** The response contained no immune-system / antibody alerts, despite:

- `role="security"`
- A task string explicitly framed as "conduct a full security audit"
- The presence of an `Enterprise Security & Licensing Governance` module (22 files) that is the natural home for constraint concepts (e.g. "license verification must be Ed25519 only", "S3 calls must hit allowlist")

**Why this matters.**
- Antibodies are advertised in `CLAUDE.md` and `AGENTS.md` as a first-class feature of `prep` ambient context: *"Alerts surface in `prep()` ambient context."*
- A security-role call is the highest-value moment to surface them. If they are silent here, agents will assume there are no constraint violations — a false sense of safety.
- This is likely a downstream consequence of issue #1 (no active concepts ⇒ no antibodies derived). If so, the two should be tracked together.

**What to investigate.**
- Confirm the causal chain: are antibodies in fact derived from `active`-status concepts only? (If yes, this is a duplicate symptom of #1.)
- If antibodies do exist independently of active concepts, why didn't a security-framed call surface them?
- Is there a path where `prep_audit(action="antibodies")` returns rows but `prep(role="security")` shows none? That divergence would itself be a bug.

**Suggested next step.** On any `prep` call where `role="security"` *or* the task string matches security keywords, force-include the antibody summary block — even if empty, render `Immune system: 0 active antibodies (X concepts seeded but not promoted)` so the absence is visible signal, not silence.

---

## Cross-cutting note

Issues #1 and #3 plausibly share a root cause (broken promotion → no active concepts → no antibodies). Issue #2 is independent (atlas module-list emission). All three are observable from a single `prep` call, which is itself a positive: dogfooding works as a feedback channel when an agent is asked to evaluate the tool. Recommend filing #1 as a Phase 124 / Finalize-chain bug and #2 / #3 as Phase 125-adjacent product backlog items.

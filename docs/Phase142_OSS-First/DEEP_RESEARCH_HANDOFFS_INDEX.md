# Deep-Research Handoffs — Index (2026-07-19)

Follow-up AI deep-research pass over the legal+security+message audit
docket. Four **dedicated, self-contained** sessions, grouped by nature,
run in parallel where independent. Each session reads only its own handoff
doc (+ the audit doc for background) and executes.

**Audit:** `LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md`
**Decision:** grouped dedicated sessions (not one mega-doc, not 6 tiny
ones) — the DR items are heterogeneous in type (research / tooling /
code-mutation), so one session can't hold all without compacting.

## The four sessions

| Session | Handoff doc | Items | Type | Mutates? | Parallel? |
|---|---|---|---|---|---|
| **A — Legal research** | `DEEP_RESEARCH_HANDOFF_A_LEGAL.md` | DR-2 trademark, DR-3 Apache §4, + ED-2 Terms gaps, ED-3 Plausible/Resend posture | legal/web research | no | yes |
| **B — Security engineering** | `DEEP_RESEARCH_HANDOFF_B_SECURITY.md` | DR-4 support auth, DR-5 bug-report CORS | code mutation | **yes — worktree, review-gated** | yes (worktree) |
| **C — SBOM scan** | `DEEP_RESEARCH_HANDOFF_C_SBOM.md` | DR-1 scancode + npm/cargo/pip license scan | tool-heavy scan | config files only | **runs first — public-mirror gate** |
| **D — codrag.key history** | `DEEP_RESEARCH_HANDOFF_D_CODRAG_KEY.md` | DR-6 history scan + ED-6 rotation/CI-gate plan | read-only git history | no | yes |

## How to dispatch

1. Open four fresh AI sessions.
2. Paste the contents of each handoff doc into its session as the first
   message. Each doc IS the starter prompt — self-contained.
3. Run A, C, D in parallel. Run B in parallel too, but B works in a
   worktree and is review-gated (Eric merges it himself).
4. Each session writes its findings to a `DEEP_RESEARCH_<X>_*_FINDINGS.md`
   doc and commits locally (no push — `[deploy]` gate).
5. When all four return, a short synthesis session rolls the four findings
   into a closure doc + the consolidated Eric-decision docket.

## Cross-session notes

- **B depends on nothing** but is the only mutating session; keep it
  worktree-isolated.
- **A's ED-3 Resend disclosure** + **B's DR-5 Resend disclosure** overlap —
  A drafts the privacy-policy text; B drafts the bug-report-route disclosure.
  Coordinate via this index: A owns the privacy-policy disclosure text, B
  owns the route-level disclosure, both surface to Eric for the single
  sign-off.
- **C is the public-mirror gate** — do not push the public mirror until C
  returns CLEAR.
- **D's CI-gate plan (ED-6) + C's gate** both concern
  `build_public_mirror.py`; D covers the secret-history + rotation side, C
  covers the license-scan side. They don't conflict.

## Hard rules (all sessions)

No Co-Authored-By · commit per logical unit locally, never push without
`[deploy]` · never `git commit --amend` on main (concurrent sessions
collide — verify `git log -1` is yours first) · license-neutral · no
attorney budget (research + frame decisions, don't decide) · don't trust
memory for code claims, verify against the repo · SourcePrep=brand/prep=code
· no image input · prep project_id in `.sourceprep/AGENT_CONTEXT.md`.
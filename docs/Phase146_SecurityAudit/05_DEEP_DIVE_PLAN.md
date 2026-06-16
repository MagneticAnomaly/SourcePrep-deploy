# 05 — Deep-Dive Plan & Orchestration

The actual audit. Eight workstreams, each scoped to **real, verified files**, each
producing confirmed/refuted verdicts with evidence. Run order is risk-first.

**Guardrails for every workstream (carried from the Provenance Policy):**
- Cite `file:line` for every claim; confirm every path exists.
- Produce a verdict per candidate: `confirmed | refuted | partial`, with a PoC or a
  proof-of-non-exploitability. Adversarially try to *refute* before promoting.
- State the threat-model assumption used (Decision D-3: loopback vs exposed daemon).
- No invented CVSS — derive from a vector or cite the prior audit's estimate.
- Log new discoveries back into `STATUS.md` + `04_CANDIDATE_FINDINGS.md`.

---

## Workstreams

### Phase 1 — Auth & Daemon Boundary  *(risk-first; do this first)*
- **Files:** `server.py:227-262` (CORS + `verify_ipc_token`), `api/routers/license.py:502` (`dev-override`), `mcp/transport.py:121` (Origin middleware), `mcp/server.py` (token attach), `cli.py` (`serve` host default), launcher/installer/docker entrypoints.
- **Candidates:** C-1, C-2, C-5. **Prior:** FULL-1 (CORS), FULL-4 (rate limiting).
- **Key questions:** Is a token ever auto-generated/set by any launch path? Browser-reachability of the API (CORS + DNS-rebinding)? MCP HTTP transport bind/port and no-Origin reachability? Is `dev-override` shippable?
- **Methods:** read the launch paths end-to-end; spin the daemon and curl without a token; attempt a cross-origin call; check `security_health` Check 8/9/10 against reality.

### Phase 2 — License & Feature-Gate
- **Files:** `core/feature_gate.py:126-257`, `core/licensing.py` (Ed25519, placeholder key `:22`), `core/lemon_squeezy.py`, `api/routers/license.py` (`activate`/`validate`/`dev-override`), packaging/build scripts.
- **Candidates:** C-2, C-7. **Prior:** CRIT-1.
- **Key questions:** Does the shipped build inject a production public key? Reject vs warn on unsigned/expired? Can dev-mode shortcuts be reached at runtime? Machine-binding / replay?

### Phase 3 — Outbound / SSRF / Team Sync
- **Files:** `services/remote_sync.py:71,102-131,211`, `services/s3_storage.py:163-170,268-329`, `api/routers/llm.py:159-195`, `api/routers/pm_push.py`, `core/team_config.py` (validating loader).
- **Candidates:** C-3 (is_safe_url gaps), C-7-adjacent. **Prior:** CRIT-2, HIGH-2, MED-3, FULL-2.
- **Key questions:** DNS-rebinding/TOCTOU between validate and connect? Redirect-following to internal hosts? `provider=ollama` arbitrary-URL bypass? Does `team_config.py` validate *every* outbound-driving field? Should index content-hash mismatch abort (MED-3) not warn?

### Phase 4 — LLM Prompt-Injection & Data Exposure
- **Files:** `core/llm_client.py:692-747` (sanitize + audit), `core/content_sanitizer.py`, `core/layered_index.py:217` (context assembly), `core/audit_log.py:148-187`, `core/epistemic_enrichment.py`, `core/augmenter.py`.
- **Candidates:** C-4 (audit redaction). **Prior:** MED-4 (context fence escape).
- **Key questions:** Can indexed file content break out of the data block (code-fence/marker injection) and steer the agent? Any `audit_log.record` caller leaking secrets/credential-URLs? Is sanitization applied on *every* path that reaches an LLM (incl. enrichment, augmenter, swarm)?

### Phase 5 — File / Path / Process Surface
- **Files:** `api/routers/projects/files.py:27-300` (read + listing), `api/routers/pipeline.py:1495-1527` (snapshot restore), `agents/shared/git_client.py`, `core/git_evidence.py`, `core/watcher.py`.
- **Candidates:** C-6 (git arg injection). **Prior:** HIGH-1, HIGH-4.
- **Key questions:** Symlink handling in directory listing (a child symlink listed by name)? Snapshot-restore traversal guard complete? Any user/config-controlled branch/path reaching git without `--`? Watcher on attacker-writable trees?

### Phase 6 — Rust Engine
- **Files:** `engine/crates/prep-walker`, `prep-parser` (tree-sitter), `prep-graph`, `prep-sanitize`, `prep-selfheal`; the maturin/PyO3 boundary.
- **Prior:** Phase36 claimed "no `unsafe`, no panics" — **stale, re-verify against current crates.**
- **Key questions:** `unsafe` blocks today? Panics across the FFI boundary (poisoned locks, `unwrap` on parse)? Resource bounds on walking/parsing hostile inputs (deeply nested dirs, pathological files)? `prep-sanitize` actually filtering what it claims?

### Phase 7 — Frontend / Webview
- **Files:** `src/prep/dashboard/` (React/Vite), `packages/vscode/` + `webview-ui/`, `tauri.conf.json` (CSP/updater).
- **Key questions:** XSS via rendered search results / event-log / concept content (any `dangerouslySetInnerHTML`)? Webview message-passing trust? Tauri CSP + auto-updater integrity? Does the dashboard talk to the daemon assuming no auth (reinforcing C-1)?

### Phase 8 — Tooling & Process Hardening
- **Scope:** the gap list in `03_TOOLING_BASELINE.md`.
- **Deliverables:** add bandit + ruff `S` rules; run semgrep & CodeQL and **dogfood** them through `prep_audit(findings=...)`; add gitleaks; add Dependabot; add cargo-deny + a license/SBOM gate; write `tests/test_security_health.py`; pin the Dockerfile Ollama install (LOW-3); quiet CI model-name logging (MED-2). Then **seed the immune-system constraint concepts** from `03`'s list via `prep_concepts`.

---

## Orchestration design (how to run it)

Each workstream is a self-contained **understand → probe → adversarially-verify →
synthesize** unit, well-suited to a Workflow per phase (not one mega-run — stay in
the loop between phases, per Decision D-1).

**Per-phase workflow shape:**
```
phase('Map')      → 1 agent: enumerate the real call paths in scope (file:line)
phase('Probe')    → N agents (one per candidate/route): build the exploit case OR
                    the reachability proof; default to "not exploitable" unless shown
phase('Verify')   → for each probe hit, 2–3 independent skeptics try to REFUTE it
                    (perspective-diverse: reachability / auth-precondition / real-impact)
phase('Synthesize')→ 1 agent: confirmed[] + refuted[] + residual-questions[],
                    each with file:line + PoC + severity vector
```
A finding is promoted only if it survives the refute panel (majority "real").
Refuted candidates are written back to `04_` marked `refuted` with reasoning.

**Dogfooding is mandatory** (CLAUDE.md): each phase records where a `prep` /
`prep_search` / `prep_impact` call helped or failed. Known live issue to work
around: `prep_search` is biased toward planning `.md` files and missed both
`team_config.py` and `is_safe_url` on 2026-06-16 — use `prep()` role-view +
`prep_impact` for code, and grep as the floor. File misses as product findings.

**Cross-cutting note — `server.py` is a 30-dependent hub** (`prep_impact`,
2026-06-16). Auth lives in exactly one middleware there, which is good for the
audit: a single chokepoint to reason about. But it also means the daemon has no
defense-in-depth if that one gate is mis-set (reinforces C-1's blast radius).

---

## Definition of done (per phase)
1. Every in-scope candidate has a `confirmed | refuted | partial` verdict with evidence.
2. Every prior-finding ❓ in `02_` for that area is re-confirmed against live code.
3. New discoveries logged to `STATUS.md` + `04_`.
4. Dogfood notes recorded.
5. `STATUS.md` phase row flipped to ✅ with a one-line outcome.

## Definition of done (whole audit)
- All eight phase rows ✅ in `STATUS.md`.
- A consolidated findings report (confirmed only) with severities + remediation.
- Immune-system constraint concepts seeded (Phase 8) so invariants are guarded going forward.
- `SECURITY.md` disclosure policy reviewed against what the audit actually found.

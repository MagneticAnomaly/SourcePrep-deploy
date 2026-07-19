export const meta = {
  name: 'legal-security-message-audit',
  description: 'Cross-surface legal + security + message-clarity audit of all public sites + repo metadata vs the still-proprietary LICENSE; classify fix-now / flag-for-AI-deep-review / Eric-decision',
  phases: [
    { title: 'Discovery', detail: '6 agents: 5 public surfaces + repo-metadata, plus 1 code-posture ground-truth extractor (phone-home/license-headers/dep-licenses/secret-grep)' },
    { title: 'Find', detail: '3 lens agents (legal/security/message) consume all discovery, surface contradictions + falsehoods' },
    { title: 'Verify', detail: 'adversarial re-check each finding against the actual working tree (read-only, no worktree)' },
    { title: 'Classify', detail: 'classify fix-now / flag-deep-review / eric-decision; produce synthesis docket' },
  ],
}

const PID = 'f1636374-abc6-410d-99ee-822120379e79'

const RULES = `
You are auditing the SourcePrep PUBLIC surface (websites/apps/{docs,marketing,support,payments} + root repo metadata) for LEGAL, SECURITY, and MESSAGE-CLARITY defects. This is ORTHOGONAL to the 4 prior code-accuracy passes (those checked docs-vs-code; you check cross-surface consistency + legal + security).

HARD RULES:
- Read-only audit. NO git operations, NO file mutation, NO worktree. Read the actual working tree at /Volumes/4TB-BAD/HumanAI/CoDRAG.
- You MAY use prep MCP (prep_search/prep_impact, project_id="${PID}") to verify code behavior, but the primary instrument is Read + grep for copy/legal-text.
- RELICENSE LANDED (commit 99315988): root LICENSE is now Apache-2.0. VERIFY the relicense is complete/consistent (LICENSE text correct/complete? NOTICE/CONTRIBUTING/SECURITY aligned and no longer "All Rights Reserved"? copyright holder + year correct? DCO/CLA present?). Do NOT flag "metadata=Apache, LICENSE=commercial" as a contradiction — that is RESOLVED. Marketing's present-tense "Apache 2.0" claims are now TRUE (not false); docs' conservatism (not asserting Apache) is now under-stating but still safe. License-neutral edits still required: do not assert a specific OSS license in NEW copy; you may flag remaining inconsistencies in the relicense rollout (e.g., a copyright line still "All Rights Reserved", a stale proprietary header in a file).
- No codename leaks: never propose adding CoDRAG/RunPrep/~/.runprep to public copy (the audit may FLAG existing leaks to remove, never add).
- Do NOT trust memory/notes for code claims — verify against the repo.

CLASSIFICATION (critical — the user has NO attorney budget):
- fix-now: straightforward, license-neutral, no Eric product/legal decision, no forward-looking assertion. Apply immediately.
- flag-deep-review: needs deeper research by another AI pass (e.g., GPL-vendored-scan, full SBOM compatibility matrix, trademark clearance, privacy-law compliance, patent preflight). Describe what the follow-up AI should research.
- eric-decision: needs Eric's product/business/legal-act call (e.g., the actual LICENSE relicense text, tier-gating decisions, pricing). Describe the decision Eric must make.

KNOWN/DECIDED — do NOT re-flag as new (extend only if a NEW surface contradicts):
- Root LICENSE is now Apache-2.0 (commit 99315988 landed mid-session). The "metadata vs LICENSE commercial" contradiction is RESOLVED. Instead VERIFY relicense completeness (NOTICE/CONTRIBUTING/SECURITY/copyright-line/year still consistent with Apache? any stale "All Rights Reserved" / proprietary header left behind?).
- License crypto forgeable: licensing.py:22 DEFAULT_PUBLIC_KEY_HEX = RFC 8032 test vector; Phase 146 CHANGE_PLAN_ed25519_crypto_fix.md has the fix plan. Flag any PUBLIC copy claiming "Ed25519 secure license" present-tense (e.g., enterprise-deploy).
- GPL deps resolved (igraph/leidenalg -> networkx). The OPEN legal gap is the source-vendored-GPL/LLM-generated scan (scancode-toolkit not installed) — flag for deep review, do not attempt.
- codrag.key is a known secret on origin; public mirror (tools/build_public_mirror.py, allowlist+denylist gate) not yet built. Flag the mirror build as the gate, do not re-scan history.
- Marketing says "Apache 2.0" present-tense on ~14 pages; docs correctly stays more conservative. The contradiction is known — extend to support/payments surfaces if they mirror it.
- 2026-07-19 66-agent OSS audit found "12 internal contradictions" — do not duplicate; surface NEW ones or ones on surfaces that audit didn't cover.
- Pricing restructure 2026-07-18 (Teams $9, Enterprise $24/seat, Pro $29 one-time) — check ALL surfaces match this ladder; flag mismatches.
- Pass-4 (commit e5d74fb7) already fixed: ONNX-GPU, audit-logging-Available, LOD 2.5, compression dropdown, codebase-audit pipeline-connection cluster, Anthropic-structured-output, byok subdivision, mcpSetup Windsurf path, AIModelsSettings LLMLingua-2, Roo/CodeGPT. Do not re-report these.

THREE LENSES:
- LEGAL: license-header sweep; SBOM (pip/npm/cargo) license compatibility; vendored/attribution + NOTICE completeness; cross-surface LICENSE-claim consistency (package.json says Apache-2.0, LICENSE says commercial, marketing says Apache-2.0 — contradictions); trademark/copyright-holder consistency (Magnetic Anomaly LLC vs SourcePrep, year); DCO/CLA setup; privacy/terms/ToS existence + match code.
- SECURITY: secret/PII/internal-hostname leakage in public copy; verify EVERY security claim ("no telemetry / offline / Ed25519 / BYOK / encrypted / SOC2 / GDPR") on EVERY surface against code; phone-home/telemetry truth vs privacy policy; internal architecture leakage (hostnames, paths, endpoint names, team tooling); advertised-dep CVE posture.
- MESSAGE: cross-surface claim matrix (same claim across docs/marketing/support/payments/README/LICENSE); pricing/tier consistency; forward-looking-claim conservatism (is each surface >= conservative?); first-visitor "what is it" clarity.
`

const CLAIM_SCHEMA = {
  type: 'object',
  properties: {
    surface: { type: 'string' },
    claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          category: { type: 'string', enum: ['legal', 'security', 'pricing', 'product', 'forward-looking', 'privacy'] },
          claim: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          notes: { type: 'string' },
        },
        required: ['category', 'claim', 'file', 'line'],
      },
    },
    posture: { type: 'string', description: 'for code-posture agent: the actual code behavior (phone-home paths, license-header coverage %, dep licenses, secret-grep hits, internal hostnames)' },
  },
  required: ['surface', 'claims'],
}

const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    lens: { type: 'string', enum: ['legal', 'security', 'message'] },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          claim: { type: 'string', description: 'the public claim as written' },
          reality: { type: 'string', description: 'what the code/LICENSE/other surfaces actually say; cite evidence + settling file:line' },
          contradiction_surfaces: { type: 'array', items: { type: 'string' }, description: 'other surfaces that disagree (e.g., LICENSE, marketing, package.json)' },
          verdict: { type: 'string', enum: ['confirmed-contradiction', 'confirmed-falsehood', 'ok', 'uncertain'] },
          severity: { type: 'string', enum: ['blocker', 'high', 'med', 'low'] },
          classification: { type: 'string', enum: ['fix-now', 'flag-deep-review', 'eric-decision'] },
          suggested_action: { type: 'string', description: 'for fix-now: the exact edit; for flag-deep-review: what the follow-up AI should research; for eric-decision: the question for Eric' },
        },
        required: ['file', 'line', 'claim', 'reality', 'verdict', 'severity', 'classification', 'suggested_action'],
      },
    },
  },
  required: ['lens', 'findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    line: { type: 'integer' },
    claim: { type: 'string' },
    verdict: { type: 'string', enum: ['CONFIRMED-CONTRADICTION', 'CONFIRMED-FALSEHOOD', 'TRUE', 'UNCERTAIN'] },
    reality: { type: 'string', description: 'settled reality with file:line evidence from the actual working tree' },
    classification: { type: 'string', enum: ['fix-now', 'flag-deep-review', 'eric-decision'] },
    severity: { type: 'string', enum: ['blocker', 'high', 'med', 'low'] },
    action: { type: 'string', description: 'the concrete next step (exact edit / research brief / Eric question)' },
    notes: { type: 'string' },
  },
  required: ['file', 'line', 'claim', 'verdict', 'reality', 'classification', 'severity', 'action'],
}

phase('Discovery')

const SURFACES = [
  { id: 'docs', label: 'docs site', paths: ['websites/apps/docs/src/app/**/*.tsx', 'websites/apps/docs/src/**/*.tsx'], note: 'Already deeply audited for CODE accuracy (4 passes). Here extract ONLY legal/security/pricing/forward-looking/privacy CLAIMS — do not re-audit code accuracy.' },
  { id: 'marketing', label: 'marketing site', paths: ['websites/apps/marketing/src/app/**/*.tsx', 'websites/apps/marketing/src/**/*.tsx'], note: 'Primary public marketing. Watch for present-tense "Apache 2.0", pricing ladder, security/privacy claims, "no telemetry" type assertions.' },
  { id: 'support', label: 'support site', paths: ['websites/apps/support/src/app/**/*.tsx', 'websites/apps/support/src/**/*.tsx'], note: 'Support/auth/bug-tracking surface. Watch for security claims, auth flow claims, data-handling claims.' },
  { id: 'payments', label: 'payments site', paths: ['websites/apps/payments/src/app/**/*.tsx', 'websites/apps/payments/src/**/*.tsx'], note: 'License-management / payments. Watch for Lemon Squeezy claims, pricing, license-crypto claims, present-tense "for sale" (Pro not sellable today).' },
  { id: 'repo-meta', label: 'repo metadata', paths: ['LICENSE', 'NOTICE', 'README.md', 'SECURITY.md', 'CONTRIBUTING.md', 'package.json', 'pyproject.toml', 'engine/Cargo.toml', 'websites/apps/*/package.json', 'packages/*/package.json'], note: 'The "what the project legally is" surface. package.json/pyproject/Cargo say Apache-2.0; root LICENSE says COMMERCIAL. Flag the contradiction + every other metadata-vs-LICENSE mismatch, copyright-holder/year, DCO/CLA, NOTICE completeness.' },
]

const discovered = await parallel(SURFACES.map(s => () => agent(
  `${RULES}

DISCOVERY — surface: ${s.label} (${s.id})
Read these files (glob the repo, then Read the highest-signal ones):
${s.paths.join('\n')}
Note: ${s.note}

Extract EVERY claim a visitor would read as a statement of fact about: licensing/legal, security, privacy, pricing/tiers, product capabilities, and forward-looking commitments. For each: category, the claim text, file:line. Do NOT judge truth yet — just extract. Include claims that are present-tense assertions about future things (Apache 2.0, Pro tier, "coming soon"). Include pricing figures. Include any security/privacy posture claim ("no telemetry", "offline", "encrypted", "BYOK", "Ed25519", compliance names like SOC2/GDPR). Return up to ~40 highest-signal claims (skip pure marketing prose that makes no factual claim).`,
  { label: `disc:${s.id}`, phase: 'Discovery', schema: CLAIM_SCHEMA }
)))

// code-posture ground truth (read-only)
const posture = await agent(
  `${RULES}

CODE-POSTURE ground-truth extraction. The public sites make claims; you establish what the CODE/LICENSE actually does, so finders can compare. Investigate (use prep_search + Read + grep):

1. PHONE-HOME / TELEMETRY: find every outbound network call the daemon/app makes (license validation, lemon_squeezy, crash reports, analytics). Cite file:line + the destination host + frequency.
2. LICENSE CRYPTO: confirm licensing.py:22 DEFAULT_PUBLIC_KEY_HEX value + the test-vector comment; confirm whether unsigned license.json is warn-but-accept; list every PUBLIC-facing claim surface that asserts Ed25519/offline-licensing as a current guarantee.
3. LICENSE HEADERS: sample-sweep — do source files carry license headers? What %? Any file with a GPL/proprietary header contradicting the Apache-2.0 metadata?
4. DEP LICENSES: run \`pip-licenses\` (via .venv/bin/pip-licenses if present) OR read the Phase142 LICENSE-AUDIT.md table; note any non-permissive license (GPL/AGPL/LGPL/MPL/CC-BY-SA). Confirm pathspec MPL-2.0 is the only weak-copyleft.
5. SECRETS: grep the working tree for private-key markers (BEGIN PRIVATE KEY, BEGIN OPENSSH PRIVATE KEY, codrag.key, api_key=, sk-, token=) in NON-test, NON-example files. Do NOT install gitleaks/trufflehog (not available) — grep is fine. Report any real-looking secret.
6. INTERNAL ARCHITECTURE LEAKAGE: grep public copy for internal hostnames/paths (localhost:8400/8401/5174/6006 are fine for dev docs, but anything like internal team URLs, /.sourceprep/, dev-only endpoint names exposed as if public).
7. PRIVACY: is there a privacy policy / terms page? Does it match the phone-home reality from (1)?

Return a single 'posture' string summarizing all 7 with file:line citations. This is the ground truth finders check claims against.`,
  { label: 'disc:code-posture', phase: 'Discovery', schema: CLAIM_SCHEMA }
))

discovered.push(posture)
const valid = discovered.filter(Boolean)
log(`Discovery: ${valid.length}/${SURFACES.length+1} agents returned; ${valid.reduce((a,d)=>a+(d.claims?.length||0),0)} raw claims`)

phase('Find')

const LENSES = [
  { lens: 'legal', prompt: `LEGAL lens. Compare every extracted claim against the code-posture ground truth, root LICENSE (still proprietary commercial), package.json/pyproject/Cargo (Apache-2.0), NOTICE, and across surfaces. Surface: (a) cross-surface LICENSE contradictions (metadata=Apache, LICENSE=commercial, marketing="Apache 2.0" present-tense), (b) license-header gaps, (c) trademark/copyright-holder/year inconsistencies (Magnetic Anomaly LLC vs SourcePrep), (d) DCO/CLA/CONTRIBUTING gaps, (e) privacy/terms page existence + match-code, (f) any GPL/weak-copyleft dep not disclosed, (g) NOTICE attribution completeness. For each finding give verdict/severity/classification/action. Mark GPL-vendored-source-scan as flag-deep-review (scancode not installed).` },
  { lens: 'security', prompt: `SECURITY lens. Verify EVERY security/privacy claim on EVERY surface against the code-posture ground truth. Surface: (a) false "no telemetry / offline / no phone-home" claims (the license router phones home to api.lemonsqueezy.com every 7d), (b) false "Ed25519 secure license" present-tense claims (placeholder key), (c) secret/PII/internal-hostname leakage in public copy, (d) compliance-name dropping (SOC2/GDVR) without backing, (e) "Pro tier for sale" present-tense (not sellable today), (f) BYOK/encryption claims vs code. For each: verdict/severity/classification/action.` },
  { lens: 'message', prompt: `MESSAGE-CLARITY / cross-surface lens. Build the cross-surface claim matrix: same claim (pricing, license, tier-features, "coming soon", security posture) across docs/marketing/support/payments/README/LICENSE. Surface: (a) pricing-ladder mismatches across surfaces (Teams $9, Enterprise $24/seat, Pro $29 one-time are the 2026-07-18 truth), (b) tier-feature contradictions (what's free vs paid across surfaces), (c) forward-looking conservatism — any surface less conservative than docs (which is the most conservative), (d) "what is it" clarity — does a first-time visitor on each surface get a consistent one-line answer about what SourcePrep is. For each: verdict/severity/classification/action.` },
]

const lensResults = await parallel(LENSES.map(l => () => agent(
  `${RULES}

${l.prompt}

DISCOVERY OUTPUT (all surfaces + code-posture, as JSON):
${JSON.stringify(valid, null, 2)}

Return findings for your lens only. Cite file:line. For 'reality', cite the settling evidence (code file:line, LICENSE line, package.json field, other-surface file:line). Prefer CONFIRMED-CONTRADICTION / CONFIRMED-FALSEHOOD over 'uncertain' where evidence is clear. Classify each fix-now / flag-deep-review / eric-decision per the rules.`,
  { label: `find:${l.lens}`, phase: 'Find', schema: FINDING_SCHEMA }
)))

const allFindings = lensResults.filter(Boolean).flatMap(r => (r.findings || []).map(f => ({ ...f, lens: r.lens })))
log(`Find: ${allFindings.length} raw findings (legal/security/message)`)

phase('Verify')

const verified = await parallel(allFindings.map(f => () => agent(
  `${RULES}

ADVERSARIAL VERIFICATION. A finder flagged this public-surface claim as a legal/security/message defect. Refute or confirm by reading the ACTUAL working tree at /Volumes/4TB-BAD/HumanAI/CoDRAG (no worktree, read-only). Use prep_search/prep_impact (project_id="${PID}") + Read + grep. Default to skepticism on both sides. Settle the reality with a real file:line citation.

FINDING:
- lens: ${f.lens}
- file: ${f.file}
- line: ${f.line}
- claim: "${f.claim}"
- finder reality: ${f.reality}
- contradiction_surfaces: ${(f.contradiction_surfaces||[]).join(', ')}
- finder verdict: ${f.verdict}
- finder severity: ${f.severity}
- finder classification: ${f.classification}
- finder action: ${f.suggested_action}

Confirm the claim text is actually present at file:line in the working tree (if not, it may be stale — mark UNCERTAIN with note). Then settle the reality. Then re-classify (fix-now / flag-deep-review / eric-decision) and re-grade severity. Remember: the user has NO attorney — fix-now must be license-neutral and require no legal-act; flag-deep-review must describe exactly what the follow-up AI should research; eric-decision must state the precise question.`,
  { label: `verify:${f.lens}:${f.file.split('/').pop()}:${f.line}`, phase: 'Verify', schema: VERDICT_SCHEMA }
).then(v => ({ ...v, original: f }))))

const settled = verified.filter(Boolean)
const confirmed = settled.filter(v => v.verdict === 'CONFIRMED-CONTRADICTION' || v.verdict === 'CONFIRMED-FALSEHOOD')
const fixNow = confirmed.filter(v => v.classification === 'fix-now')
const flagDeep = confirmed.filter(v => v.classification === 'flag-deep-review')
const eric = settled.filter(v => v.classification === 'eric-decision')
const refuted = settled.filter(v => v.verdict === 'TRUE')
log(`Verify: ${confirmed.length} confirmed (${fixNow.length} fix-now, ${flagDeep.length} flag-deep-review, ${eric.length} eric), ${refuted.length} refuted-TRUE, ${settled.length - confirmed.length - refuted.length} uncertain`)

phase('Classify')

const synthesis = await agent(
  `${RULES}

You are the synthesizer. A cross-surface legal+security+message-clarity audit ran: 6 discovery agents (5 surfaces + code-posture), 3 lens finders, then per-finding adversarial verification. Produce a markdown addendum for a NEW doc at docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md with sections:

1. SUMMARY — counts, the 3-lens breakdown, the single biggest cross-surface contradiction.
2. FIX-NOW — confirmed, license-neutral, no Eric/legal-act. Each: file:line — claim — reality (cite) — exact edit. These will be applied immediately by the orchestrator.
3. FLAG-FOR-AI-DEEP-REVIEW — needs a follow-up AI research pass (no attorney budget). Each: a research brief — what the follow-up AI should investigate, what files/tools (e.g., scancode-toolkit), what the open question is. Numbered DR-1, DR-2...
4. ERIC-DECISION — needs Eric's call (product/business/legal-act). Each: the precise question, the options, the recommended default. Numbered ED-1, ED-2... (continue from the existing E1-E19 where conceptually the same item; use ED- prefix for new ones to avoid collision).
5. REFUTED — settled TRUE (no change); brief.
6. CROSS-SURFACE CLAIM MATRIX — a table of the most important claims (license, pricing per tier, "no telemetry", Ed25519, Pro-for-sale, "Apache 2.0") × surfaces (docs/marketing/support/payments/README/LICENSE/package.json) showing where each surface stands and the contradictions.
7. DOGFOODING — did prep MCP help vs grep+Read for legal/security/message (vs the code-accuracy passes)? Legal-text comparison is outside prep's graph — note that.

Deduplicate. Be concise. The orchestrator will apply the FIX-NOW set and commit, then surface FLAG + ERIC to the user.

VERIFIED FINDINGS JSON:
${JSON.stringify(settled, null, 2)}
`,
  { label: 'synthesize', phase: 'Classify' }
)

return {
  raw_findings: allFindings.length,
  verified: settled.length,
  confirmed: confirmed.length,
  fix_now: fixNow.length,
  flag_deep_review: flagDeep.length,
  eric_decision: eric.length,
  refuted_true: refuted.length,
  synthesis,
}

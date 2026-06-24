/**
 * Phase 145 §9.3 #30/#31 — structural pin tests for stats-IIFE coercion.
 *
 * Background: PR-C made i3SafeStageState coerce a stage's *state* to
 * 'complete' when its group phase === 'completed'. The badge turned green
 * but each row's *stats text* was still computed from the raw state and
 * continued to say 'Not run' (and the catalogue % could exceed 100, the
 * 5501% Fast Catalogue class). PR-D switched every stats IIFE / inline
 * stats expression to compute a safeState via i3SafeStageState and check
 * that instead, plus added a Math.min(100, ...) clamp to the catalogue %.
 *
 * These tests pin the structure of GraphEnrichmentPipeline.tsx so that a
 * future edit which forgets the safeState pattern or removes the clamp
 * fails loudly here instead of silently regressing the dashboard.
 *
 * Pattern mirrors the inspect-source pins added in PR-B's
 * test_phase145_run_session.py.
 */

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SRC = readFileSync(
  resolve(__dirname, '..', 'GraphEnrichmentPipeline.tsx'),
  'utf-8',
);

// §9.3 #33 PR-F F2 — Balanced-paren walk to extract every i3SafeStageState
// call's argument string. Regex-only approaches were either too loose (the
// bare `, 'id',` literal false-positive-matched stage-id array literals like
// FAST_STAGE_ORDER, undercounting safeState const removals) or too strict
// (`[^)]*?` cannot pass over the `)` inside nested calls such as
// `i3SafeStageState(promoteForRebuild(finStageState('rules', rulesDone)), 'rules', …)`,
// failing for the 4 finalize stages). A small parser handles both.
function findI3SafeStageStateArgs(src: string): string[] {
  const calls: string[] = [];
  const opener = /\bi3SafeStageState\s*\(/g;
  let m: RegExpExecArray | null;
  while ((m = opener.exec(src)) !== null) {
    const argsStart = m.index + m[0].length;
    let depth = 1;
    let i = argsStart;
    while (i < src.length && depth > 0) {
      const ch = src[i];
      if (ch === '(') depth++;
      else if (ch === ')') depth--;
      if (depth === 0) break;
      i++;
    }
    if (depth === 0) calls.push(src.slice(argsStart, i));
  }
  return calls;
}

const I3_SAFE_STAGE_STATE_CALLS = findI3SafeStageStateArgs(SRC);

// §9.3 #34 PR-G addenda — Balanced-brace walk to extract every IIFE body
// (`(() => { ... })`). Used to scope assertions to a single IIFE rather
// than the line-as-unit approach the PR-G sweep originally used (which the
// PR-G scrutiny found could be defeated by multi-line conditionals or by
// removing the 'running' literal entirely from a single line).
function findIIFEBodies(src: string): string[] {
  const bodies: string[] = [];
  const opener = /\(\(\)\s*=>\s*\{/g;
  let m: RegExpExecArray | null;
  while ((m = opener.exec(src)) !== null) {
    const bodyStart = m.index + m[0].length;
    let depth = 1;
    let i = bodyStart;
    while (i < src.length && depth > 0) {
      const ch = src[i];
      if (ch === '{') depth++;
      else if (ch === '}') depth--;
      if (depth === 0) break;
      i++;
    }
    if (depth === 0) bodies.push(src.slice(bodyStart, i));
  }
  return bodies;
}

const IIFE_BODIES = findIIFEBodies(SRC);

// Stages whose stats IIFE/expression had a literal `'Not run'` return
// before PR-D. Each must now be preceded by a safeState pattern.
const STAGE_IDS = [
  'structural',
  'inferred_edges',
  'catalogue',
  'validation',
  'enrichment',
  'group_reasoning',  // §9.3 #34 PR-G addenda — brought into safeState scope
  'clustering',
  'atlas',
  'deepening',
  'knowledge',
  'deep_knowledge',
  'rules',
  'concepts',
  'audit',
  'antibodies',
] as const;

describe('GraphEnrichmentPipeline stats safe-state coercion (§9.3 #30)', () => {
  it.each(STAGE_IDS)(
    '%s — appears in ≥ 2 i3SafeStageState callsites (badge + stats safeState)',
    (stageId) => {
      // §9.3 #33 PR-F F2 — Count the i3SafeStageState calls whose argument
      // string contains the stage_id literal. Each stage must be referenced
      // in AT LEAST two distinct callsites:
      //   (1) the stage-array `state:` field (badge state, PR-C)
      //   (2) the stats IIFE / inline-ternary safeState const (PR-D)
      // The balanced-paren walk in findI3SafeStageStateArgs guarantees each
      // entry is exactly one full call, so false-positives from stage-id
      // array literals (FAST_STAGE_ORDER et al.) are impossible.
      const stageIdLiteral = `'${stageId}'`;
      const matchingCalls = I3_SAFE_STAGE_STATE_CALLS.filter(args =>
        args.includes(stageIdLiteral),
      );
      expect(matchingCalls.length).toBeGreaterThanOrEqual(2);
    },
  );

  it('every "Not run" stats return is preceded by a safeState guard', () => {
    // §9.3 #33 PR-F F3 — Walk the file, line-by-line. For every
    // `return 'Not run'` (anywhere on the line, including the inline-if
    // form `if (safeState === 'not_built') return 'Not run';` which PR-D
    // uses for 10 of the 15 sites — the line-start regex used previously
    // only matched 5 of 15) we expect one of:
    //   - `safeState === 'not_built'` (the IIFE pattern)
    //   - `safeState === 'complete'` (the inline-ternary refactor pattern,
    //     where 'Not run' is the fallback and 'complete' short-circuits)
    // within the enclosing IIFE body. We bound the look-back to the
    // nearest enclosing `(() => {` line so guards from a NEIGHBOURING
    // IIFE (PRD-TQ-2 originally allowed cross-IIFE leak: the preceding
    // IIFE's safeState satisfied the next IIFE's requirement) cannot
    // satisfy this IIFE's requirement.
    const lines = SRC.split('\n');
    const violations: Array<{ line: number; snippet: string }> = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!/\breturn\s+'Not run'/.test(line)) continue;
      // Walk backwards until we hit the start of the enclosing IIFE body.
      let start = Math.max(0, i - 60); // upper bound — no IIFE is this long
      for (let j = i - 1; j >= Math.max(0, i - 60); j--) {
        if (/\(\(\)\s*=>\s*\{/.test(lines[j])) { start = j; break; }
      }
      // Include line `i` itself in the window — the inline-if form
      // `if (safeState === 'not_built') return 'Not run';` has the guard
      // AND the return on the same line.
      const window = lines.slice(start, i + 1).join('\n');
      const guarded =
        /safeState\s*===\s*'not_built'/.test(window) ||
        /safeState\s*===\s*'complete'/.test(window);
      if (!guarded) {
        violations.push({ line: i + 1, snippet: line.trim() });
      }
    }
    expect(violations).toEqual([]);
  });

  it('every "Not run" return sits inside an IIFE body (boundary sanity)', () => {
    // §9.3 #33 PR-F F3 — Counter-test for the above. If the IIFE-boundary
    // walk above ever fails to find a `(() => {` line within 60 lines,
    // the `start` falls back to `i - 60` and a neighbouring IIFE's guard
    // could leak in. Pin that every 'Not run' has a `(() => {` opener
    // within its 60-line look-back. Failure here means the IIFE-boundary
    // assumption no longer holds and the guard test needs revisiting.
    const lines = SRC.split('\n');
    const orphans: number[] = [];
    for (let i = 0; i < lines.length; i++) {
      if (!/\breturn\s+'Not run'/.test(lines[i])) continue;
      const window = lines.slice(Math.max(0, i - 60), i).join('\n');
      if (!/\(\(\)\s*=>\s*\{/.test(window)) orphans.push(i + 1);
    }
    expect(orphans).toEqual([]);
  });
});

describe('GraphEnrichmentPipeline catalogue % clamp (§9.3 #31)', () => {
  it('catalogueStats IIFE clamps the % calculation with Math.min(100, ...)', () => {
    // Extract the catalogueStats IIFE body. It starts with
    // `const catalogueStats = (() => {` and ends with `})();`.
    const m = SRC.match(/const catalogueStats = \(\(\) => \{([\s\S]*?)\n\s*\}\)\(\);/);
    expect(m).not.toBeNull();
    const body = m![1];
    // Must contain the augmented_nodes / total_nodes calculation.
    expect(body).toMatch(/augmented_nodes\s*\/\s*augmentation\.total_nodes/);
    // §9.3 #33 PR-F F7 — clamp via Math.min that includes the literal 100.
    // Relaxed from the rigid `Math.min(100, Math.round(...))` form so a
    // semantically-equivalent reorder like
    //   Math.round(Math.min(100, ratio * 100))
    // (or any other arrangement that wraps the ratio in a Math.min with 100)
    // still passes. The contract is "clamp present", not "clamp in this
    // exact syntactic form".
    expect(body).toMatch(/Math\.min\([^)]*100[^)]*\)/);
  });

  it('the sibling catalogueProgress IIFE also clamps (regression net)', () => {
    // Pre-PR-D the progress bar already clamped; the stats text did not.
    // Pin both so the file's two derivations stay consistent.
    const m = SRC.match(/const catalogueProgress = \(\(\) => \{([\s\S]*?)\n\s*\}\)\(\);/);
    expect(m).not.toBeNull();
    const body = m![1];
    // §9.3 #33 PR-F F7 — same relaxed clamp pattern as catalogueStats.
    expect(body).toMatch(/Math\.min\([^)]*100[^)]*\)/);
  });
});

describe('CoverageBar width clamps (§9.3 #33 PR-F F1)', () => {
  // Pin the sibling CoverageBar widths in TraceCoveragePanel + GraphStructurePanel.
  // Same bug class as the 5501% catalogue chip — if augmented_nodes > total_nodes
  // (data-semantics inconsistency tracked under §9.3 #32) leaks into these panels,
  // unclamped widths break the rounded `overflow-hidden` clip.
  const TRACE_COVERAGE_SRC = readFileSync(
    resolve(__dirname, '..', 'TraceCoveragePanel.tsx'),
    'utf-8',
  );
  const GRAPH_STRUCTURE_SRC = readFileSync(
    resolve(__dirname, '..', 'GraphStructurePanel.tsx'),
    'utf-8',
  );

  it('TraceCoveragePanel: every Pct ratio is clamped via Math.min(100, ...)', () => {
    // Each of tracedPct / inProgressPct / stalePct / untracedPct must be
    // declared via Math.min(100, ...). The pattern `const xPct = Math.min(100,`
    // catches the canonical form.
    for (const name of ['tracedPct', 'inProgressPct', 'stalePct', 'untracedPct']) {
      const re = new RegExp(`const ${name}\\s*=\\s*Math\\.min\\(\\s*100\\s*,`);
      expect(TRACE_COVERAGE_SRC).toMatch(re);
    }
  });

  it('GraphStructurePanel: every Pct ratio is clamped via Math.min(100, ...)', () => {
    for (const name of ['tracedPct', 'inProgressPct', 'stalePct']) {
      const re = new RegExp(`const ${name}\\s*=\\s*Math\\.min\\(\\s*100\\s*,`);
      expect(GRAPH_STRUCTURE_SRC).toMatch(re);
    }
  });
});

describe('Stats IIFE promoteForRebuild wrap (§9.3 #34 PR-G)', () => {
  // PR-D + PR-F left the stats IIFEs computing safeState directly from the
  // raw computed state, without first wrapping in promoteForRebuild. The
  // BADGE state at every stage-array entry DOES wrap with promoteForRebuild
  // (lines ~1448, 1451, 1459, 1462, 1465, 1476, 1516, 1523, 1531 + the 5
  // finalize badges). During a /pipeline/rebuild this produced a desync:
  // badge shows the rebuild progress-bar variant (rebuilding); stats text
  // wouldn't match because the running-branch only matched 'running'.
  //
  // PR-G fix: every stats safeState is computed from
  // i3SafeStageState(promoteForRebuild(<rawState>), ...) — matching the
  // badge pattern — AND every running-text branch now also matches
  // 'rebuilding' so the stats text fires during rebuild too.

  it.each(STAGE_IDS)(
    '%s — stats safeState computation wraps raw state in promoteForRebuild',
    (stageId) => {
      // For each stage_id, find the i3SafeStageState call whose stage_id
      // arg matches AND whose preceding-bytes context shows it's inside a
      // `const safeState = ` assignment (the stats IIFE pattern, not the
      // badge stage-array entry which uses `state:`).
      const stageIdLiteral = `'${stageId}'`;
      // Find every i3SafeStageState call that references this stage id,
      // and locate it in the source.
      const callRe = /\bi3SafeStageState\s*\(/g;
      const wrappedCallSites: number[] = [];
      const allCallSites: number[] = [];
      let m: RegExpExecArray | null;
      while ((m = callRe.exec(SRC)) !== null) {
        const argsStart = m.index + m[0].length;
        // Find the matching closing paren.
        let depth = 1;
        let i = argsStart;
        while (i < SRC.length && depth > 0) {
          if (SRC[i] === '(') depth++;
          else if (SRC[i] === ')') depth--;
          if (depth === 0) break;
          i++;
        }
        const args = SRC.slice(argsStart, i);
        if (!args.includes(stageIdLiteral)) continue;
        // What's the ~80 chars preceding `i3SafeStageState(` ? If it
        // contains `const safeState`, this is a stats-IIFE callsite (the
        // ones we need to verify wrap promoteForRebuild).
        const preContext = SRC.slice(Math.max(0, m.index - 80), m.index);
        if (!/const safeState\s*=\s*$/.test(preContext)) continue;
        allCallSites.push(m.index);
        // Did the first arg wrap promoteForRebuild?
        if (/^\s*promoteForRebuild\s*\(/.test(args)) {
          wrappedCallSites.push(m.index);
        }
      }
      expect(allCallSites.length).toBeGreaterThanOrEqual(1);
      expect(wrappedCallSites.length).toBe(allCallSites.length);
    },
  );

  it('every IIFE body with a safeState running/rebuilding branch has BOTH literals', () => {
    // §9.3 #34 PR-G addenda — replaces the original line-based sweep
    // (which the PR-G scrutiny found was asymmetric: it only walked lines
    // containing `safeState === 'running'`, so a regression that removed
    // the 'running' literal and left only 'rebuilding' would be silently
    // skipped — see PRG-TQ-1).
    //
    // IIFE-body-based + bidirectional. For each IIFE body that mentions
    // EITHER `safeState === 'running'` OR `safeState === 'rebuilding'`,
    // both literals must appear. Catches removal of EITHER direction.
    //
    // Also resilient to behaviour-equivalent line-formatting changes
    // (multi-line conditionals, split-if refactors) that would have
    // tripped the line-based sweep — see PRG-TQ-2.
    const violations: Array<{ body_preview: string; missing: string }> = [];
    for (const body of IIFE_BODIES) {
      const hasRunning = /safeState\s*===\s*'running'/.test(body);
      const hasRebuilding = /safeState\s*===\s*'rebuilding'/.test(body);
      if (hasRunning && !hasRebuilding) {
        violations.push({ body_preview: body.slice(0, 200).trim(), missing: 'rebuilding' });
      } else if (hasRebuilding && !hasRunning) {
        violations.push({ body_preview: body.slice(0, 200).trim(), missing: 'running' });
      }
    }
    expect(violations).toEqual([]);
  });

  it('canonical safeState variable name (PRG-TQ-3 convention pin)', () => {
    // §9.3 #34 PR-G addenda — the per-stage promoteForRebuild pin and the
    // 'Not run' guard sweep both hardcode the identifier `safeState`. A
    // legitimate rename refactor like `const myState = i3SafeStageState(…)`
    // would silently break both pins for opaque reasons. Document the
    // convention explicitly so a future maintainer who hits the pin
    // failures sees a clean error pointing at the contract rather than
    // chasing structural regex misses.
    //
    // The convention: every `const X = i3SafeStageState(` assignment inside
    // a stats IIFE in GraphEnrichmentPipeline.tsx must use the identifier
    // `safeState`. The badge-state arg (in the stage array, after `state:`)
    // is separate and is allowed any form.
    const violations: string[] = [];
    const re = /const\s+(\w+)\s*=\s*i3SafeStageState\s*\(/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(SRC)) !== null) {
      if (m[1] !== 'safeState') {
        violations.push(`Found 'const ${m[1]} = i3SafeStageState(' — expected 'safeState'`);
      }
    }
    expect(violations).toEqual([]);
  });
});

describe('Atlas IIFE safeState gating (§9.3 #33 PR-F F4)', () => {
  it('atlasStats IIFE gates "Building atlas..." on safeState only — no `atlasRunning ||` bypass', () => {
    // Pre-PR-F: `if (atlasRunning || safeState === 'running') return 'Building atlas...';`
    // The raw atlasRunning flag escapes the i3SafeStageState coercion — in
    // the race window where finalizePhase has flipped to 'completed' but
    // atlasRunning is still stale-true for one poll tick, the badge would
    // show green ✓ while the stats line still read 'Building atlas...'.
    //
    // PR-F: gate on safeState only.
    const m = SRC.match(/const atlasStats = \(\(\) => \{([\s\S]*?)\n\s*\}\)\(\);/);
    expect(m).not.toBeNull();
    const body = m![1];
    // The 'Building atlas...' return must NOT be preceded by an `||` with
    // a raw running-flag identifier. Allow safeState-only forms (PR-F F4)
    // and the post-PR-G OR with 'rebuilding' added by §9.3 #34.
    // Accepted forms (any one):
    //   if (safeState === 'running') return 'Building atlas...';
    //   if (safeState === 'running' || safeState === 'rebuilding') return 'Building atlas...';
    //   if ((safeState === 'running' || safeState === 'rebuilding')) return 'Building atlas...';
    expect(body).toMatch(
      /if\s*\(\(?safeState === 'running'(\s*\|\|\s*safeState === 'rebuilding')?\)?\)\s*return 'Building atlas\.\.\.';/,
    );
    // Negative: the legacy `atlasRunning ||` form must not appear (the raw
    // running flag escapes the i3SafeStageState coercion).
    expect(body).not.toMatch(/atlasRunning\s*\|\|/);
  });
});

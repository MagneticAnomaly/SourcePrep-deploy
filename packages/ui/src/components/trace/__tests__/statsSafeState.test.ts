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

// Stages whose stats IIFE/expression had a literal `'Not run'` return
// before PR-D. Each must now be preceded by a safeState pattern.
const STAGE_IDS = [
  'structural',
  'inferred_edges',
  'catalogue',
  'validation',
  'enrichment',
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
    '%s — has both badge and stats i3SafeStageState calls (≥ 2 references)',
    (stageId) => {
      // Each stage must be referenced as the stage_id arg of i3SafeStageState
      // in AT LEAST two places:
      //   (1) the stage-array `state:` field (badge state, plumbed in PR-C)
      //   (2) the stats IIFE / inline-ternary safeState const (added in PR-D)
      // The literal `, '<stage_id>',` only matches the stage_id positional
      // argument of i3SafeStageState (preceded by comma+whitespace, followed
      // by comma). Inner references like `finStageState('rules', ...)` are
      // preceded by `(`, not a comma — so they don't false-match.
      const pattern = new RegExp(`,\\s*'${stageId}'\\s*,`, 'g');
      const matches = [...SRC.matchAll(pattern)];
      expect(matches.length).toBeGreaterThanOrEqual(2);
    },
  );

  it('every "Not run" stats return is preceded by a safeState guard', () => {
    // Walk the file, line-by-line. For every `return 'Not run'` we expect
    // one of the following within the previous 15 lines:
    //   - `safeState === 'not_built'` (the IIFE pattern)
    //   - `safeState === 'complete'` (the inline-ternary refactor pattern,
    //     where 'Not run' is the fallback and 'complete' short-circuits)
    const lines = SRC.split('\n');
    const violations: Array<{ line: number; context: string }> = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      // Skip comments / docstrings / non-return contexts.
      if (!/^\s*return\s+'Not run'/.test(line)) continue;
      const window = lines.slice(Math.max(0, i - 15), i).join('\n');
      const guarded =
        /safeState\s*===\s*'not_built'/.test(window) ||
        /safeState\s*===\s*'complete'/.test(window);
      if (!guarded) {
        violations.push({ line: i + 1, context: window.slice(-200) });
      }
    }
    expect(violations).toEqual([]);
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
    // The math must be clamped via Math.min(100, ...). Without the clamp,
    // augmented_nodes > total_nodes produces the 5501% Fast Catalogue class
    // observed live on 2026-06-23.
    expect(body).toMatch(/Math\.min\(\s*100\s*,\s*Math\.round/);
  });

  it('the sibling catalogueProgress IIFE also clamps (regression net)', () => {
    // Pre-PR-D the progress bar already clamped; the stats text did not.
    // Pin both so the file's two derivations stay consistent.
    const m = SRC.match(/const catalogueProgress = \(\(\) => \{([\s\S]*?)\n\s*\}\)\(\);/);
    expect(m).not.toBeNull();
    const body = m![1];
    expect(body).toMatch(/Math\.min\(\s*100\s*,\s*Math\.round/);
  });
});

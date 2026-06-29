/**
 * IndexHealthPanel — §9.3 #32 (PR-R) defensive ratio clamp.
 *
 * Sister of PR-D's Math.min clamp on the catalogue chip in
 * GraphEnrichmentPipeline.tsx (rendering-side defense for §9.3 #32).
 * IndexHealthPanel displays a raw `X/Y` fraction rather than a
 * percentage, so the equivalent defense is:
 *   (a) clamp the displayed numerator at the denominator so the chip
 *       never reads e.g. '7812/142' (visibly broken),
 *   (b) flag the over-coverage case with an orange accent so it
 *       doesn't quietly look like under-coverage (yellow) or
 *       healthy (default).
 *
 * Companion to PR-P / PR-P-fixup / PR-P-fixup-r2 which fix the backend
 * manifest writer (catalogue path). PR-R remains as defense-in-depth
 * for paths the backend fix does not cover (v2-fallback edge case per
 * scrutiny PRP-FXP-002, deepening/enrichment stages per FINDING §2j §9
 * 2026-06-25 dogfood).
 */
import { describe, it, expect } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { IndexHealthPanel, ratioChip, type IndexHealthData } from '../IndexHealthPanel';

afterEach(() => {
  cleanup();
});

// ─────────────────────────────────────────────────────────────────
// ratioChip — pure-logic pins
// ─────────────────────────────────────────────────────────────────

describe('ratioChip pure helper', () => {
  it("denominator <= 0 → '0' with no accent", () => {
    expect(ratioChip(0, 0)).toEqual({ value: '0', accent: undefined });
    expect(ratioChip(5, 0)).toEqual({ value: '0', accent: undefined });
    expect(ratioChip(5, -1)).toEqual({ value: '0', accent: undefined });
  });

  it("numerator < denominator → '{n}/{d}' with yellow accent", () => {
    expect(ratioChip(50, 100)).toEqual({ value: '50/100', accent: 'yellow' });
    expect(ratioChip(0, 100)).toEqual({ value: '0/100', accent: 'yellow' });
  });

  it("numerator == denominator → '{n}/{d}' with no accent (healthy)", () => {
    expect(ratioChip(100, 100)).toEqual({ value: '100/100', accent: undefined });
  });

  it("§9.3 #32 anomaly: numerator > denominator → clamped + orange accent", () => {
    // The production 7812/142 case — clamped display + orange flag.
    expect(ratioChip(7812, 142)).toEqual({ value: '142/142', accent: 'orange' });
    // The 2026-06-25 Applifier dogfood deepening case (per FINDING §2j §9).
    expect(ratioChip(1257, 1225)).toEqual({ value: '1225/1225', accent: 'orange' });
    // Smallest-step anomaly — still flagged.
    expect(ratioChip(101, 100)).toEqual({ value: '100/100', accent: 'orange' });
  });
});

// ─────────────────────────────────────────────────────────────────
// IndexHealthPanel render — chips actually use the clamped helper
// ─────────────────────────────────────────────────────────────────

const baseData: IndexHealthData = {
  total_chunks: 100,
  total_files: 50,
  stale_count: 0,
  error_count: 0,
  last_build_at: '2026-06-25T00:00:00Z',
  embedding_dim: 768,
  trace_nodes: 1000,
  trace_edges: 2500,
  coverage_pct: 1.0,
  catalogued_nodes: 100,
  catalogued_total: 100,
  deep: null,
};

describe('IndexHealthPanel — Catalogued chip render under §9.3 #32 anomaly', () => {
  it("renders clamped '142/142' (not '7812/142') when catalogued_nodes > catalogued_total", () => {
    const data: IndexHealthData = {
      ...baseData,
      catalogued_nodes: 7812,
      catalogued_total: 142,
    };
    render(<IndexHealthPanel data={data} />);
    // Catalogued chip must read 142/142 not 7812/142.
    expect(screen.getByText('142/142')).toBeInTheDocument();
    // The raw inverted numerator must not leak into the DOM.
    expect(screen.queryByText('7812/142')).not.toBeInTheDocument();
    // Anomaly accent (orange) must be applied to the value cell.
    const valueCell = screen.getByText('142/142');
    expect(valueCell.className).toMatch(/text-orange-400/);
  });

  it("renders '50/100' with yellow accent when under-covered (normal incomplete state)", () => {
    const data: IndexHealthData = {
      ...baseData,
      catalogued_nodes: 50,
      catalogued_total: 100,
    };
    render(<IndexHealthPanel data={data} />);
    const cell = screen.getByText('50/100');
    expect(cell.className).toMatch(/text-yellow-400/);
    expect(cell.className).not.toMatch(/text-orange-400/);
  });

  it("renders '100/100' with no accent when exactly complete (healthy)", () => {
    const data: IndexHealthData = {
      ...baseData,
      catalogued_nodes: 100,
      catalogued_total: 100,
    };
    render(<IndexHealthPanel data={data} />);
    const cell = screen.getByText('100/100');
    expect(cell.className).not.toMatch(/text-yellow-400/);
    expect(cell.className).not.toMatch(/text-orange-400/);
  });
});

describe('IndexHealthPanel — Enriched chip render under §9.3 #32 anomaly', () => {
  it("renders clamped enriched fraction when enriched_nodes > enriched_total (deepening §9.3 #32 surface)", () => {
    // 2026-06-25 dogfood: Deep Reasoning chip read '1,257 / 1,225 files' —
    // the deepening/enrichment side of the same bug class. IndexHealthPanel's
    // 'Enriched' chip pulls similar fields; pin the clamp here too so a
    // backend regression doesn't leak through this surface either.
    const data: IndexHealthData = {
      ...baseData,
      deep: {
        enriched_nodes: 1257,
        enriched_total: 1225,
        avg_confidence: 0.85,
        module_count: 35,
        files_clustered: 100,
        deepening_settled_ratio: 0.8,
        deepening_iteration: 1,
        knowledge_chunks: 500,
        deep_running: false,
        last_deep_at: '2026-06-25T00:00:00Z',
      },
    };
    render(<IndexHealthPanel data={data} />);
    expect(screen.getByText('1225/1225')).toBeInTheDocument();
    expect(screen.queryByText('1257/1225')).not.toBeInTheDocument();
    const cell = screen.getByText('1225/1225');
    expect(cell.className).toMatch(/text-orange-400/);
  });
});

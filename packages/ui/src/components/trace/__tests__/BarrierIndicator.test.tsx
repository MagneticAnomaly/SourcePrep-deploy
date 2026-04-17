/**
 * BarrierIndicator tests
 *
 * Pure logic/unit tests following the RecoverStagePanel.test.tsx pattern —
 * no DOM rendering, no @testing-library/react. These typecheck and run
 * with vitest once it is wired into the monorepo. Component render tests
 * live in Storybook.
 *
 * The 8 test cases cover:
 *   1. isBarrierStale — returns false when barrier is inactive
 *   2. isBarrierStale — returns false when age_seconds is under 3600
 *   3. isBarrierStale — returns true when age_seconds is over 3600
 *   4. isBarrierStale — returns false when age_seconds is exactly 3600 (boundary)
 *   5. isBarrierStale — returns false when age_seconds is undefined
 *   6. BarrierIndicator — returns null when barrier.active is false
 *   7. BarrierStatus type — active+reason+age shape satisfies contract
 *   8. BarrierIndicator — returns a non-null element when barrier is active
 */
import { describe, it, expect } from 'vitest';
import { isBarrierStale, BarrierIndicator } from '../BarrierIndicator';
import type { BarrierStatus } from '../../../types';

// ── Fixtures ─────────────────────────────────────────────────

const INACTIVE_BARRIER: BarrierStatus = {
  active: false,
};

const FRESH_BARRIER: BarrierStatus = {
  active: true,
  age_seconds: 120,
  reason: 'finalize in progress',
  written_at: Date.now() / 1000 - 120,
};

const STALE_BARRIER: BarrierStatus = {
  active: true,
  age_seconds: 7200, // 2 hours
  reason: 'leftover from interrupted run',
  written_at: Date.now() / 1000 - 7200,
};

const BOUNDARY_BARRIER: BarrierStatus = {
  active: true,
  age_seconds: 3600, // exactly 1h — NOT stale (must exceed threshold)
};

const NO_AGE_BARRIER: BarrierStatus = {
  active: true,
  // age_seconds intentionally omitted
  reason: 'rebuild triggered',
};

// ── isBarrierStale ───────────────────────────────────────────

describe('isBarrierStale', () => {
  // Test 1: inactive barrier is never stale
  it('returns false when barrier.active is false', () => {
    expect(isBarrierStale(INACTIVE_BARRIER)).toBe(false);
  });

  // Test 2: fresh active barrier is not stale
  it('returns false when age_seconds is under 3600', () => {
    expect(isBarrierStale(FRESH_BARRIER)).toBe(false);
  });

  // Test 3: old active barrier is stale
  it('returns true when age_seconds is over 3600', () => {
    expect(isBarrierStale(STALE_BARRIER)).toBe(true);
  });

  // Test 4: exactly 3600 is NOT stale (threshold is strictly greater than)
  it('returns false when age_seconds is exactly 3600 (boundary — not stale)', () => {
    expect(isBarrierStale(BOUNDARY_BARRIER)).toBe(false);
  });

  // Test 5: undefined age_seconds treated as 0 — not stale
  it('returns false when age_seconds is undefined', () => {
    expect(isBarrierStale(NO_AGE_BARRIER)).toBe(false);
  });
});

// ── BarrierIndicator structural ─────────────────────────────

describe('BarrierIndicator', () => {
  // Test 6: inactive barrier → null (component is a function we can call directly)
  it('returns null when barrier.active is false', () => {
    const result = BarrierIndicator({ barrier: INACTIVE_BARRIER });
    expect(result).toBeNull();
  });

  // Test 7: BarrierStatus type shape covers expected fields
  it('BarrierStatus with all optional fields satisfies the interface', () => {
    const b: BarrierStatus = {
      active: true,
      age_seconds: 300,
      reason: 'reset in progress',
      written_at: 1713369600,
    };
    expect(b.active).toBe(true);
    expect(b.age_seconds).toBe(300);
    expect(b.reason).toBe('reset in progress');
    expect(b.written_at).toBe(1713369600);
  });

  // Test 8: active barrier → BarrierIndicator returns a non-null JSX element
  it('returns a non-null React element when barrier is active', () => {
    const result = BarrierIndicator({ barrier: FRESH_BARRIER });
    expect(result).not.toBeNull();
  });
});

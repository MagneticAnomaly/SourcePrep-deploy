/**
 * ModelCard tests
 *
 * Pure logic/unit tests following the BarrierIndicator.test.tsx pattern —
 * source-inspection / function-call only (no DOM render). Convention,
 * not infra constraint: vitest + happy-dom + @testing-library/react ARE
 * wired in packages/ui as of PR-H (commits b3ca8d5f + dd1ff75c).
 *
 * Covers buildModelOptions — the helper that constructs the <Select>
 * option list for the Model dropdown. The key regression being fixed:
 * when a model is persisted in config but the endpoint's availableModels
 * list is empty (fetch not yet done, fetch failed, endpoint offline),
 * the native <select> must still render the saved value — not silently
 * fall back to the "Select a model..." placeholder.
 */
import { describe, it, expect } from 'vitest';
import { buildModelOptions, shouldShowAlwaysOn } from '../ModelCard';

describe('buildModelOptions', () => {
  it('injects synthetic option for saved model when availableModels is empty', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: [],
      modelDetails: undefined,
      loadingModels: false,
    });
    expect(opts).toHaveLength(1);
    expect(opts[0]).toEqual({ value: 'qwen3:8b', label: 'qwen3:8b' });
  });

  it('does not duplicate when saved model is already in availableModels', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: ['qwen3:8b', 'gemma3:12b'],
      modelDetails: undefined,
      loadingModels: false,
    });
    expect(opts).toHaveLength(2);
    expect(opts.map((o) => o.value)).toEqual(['qwen3:8b', 'gemma3:12b']);
  });

  it('treats ":latest" as equivalent when de-duping synthetic', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: ['qwen3:8b:latest'],
      modelDetails: undefined,
      loadingModels: false,
    });
    expect(opts).toHaveLength(1);
    expect(opts[0].value).toBe('qwen3:8b:latest');
  });

  it('shows placeholder when no model is saved', () => {
    const opts = buildModelOptions({
      model: undefined,
      availableModels: [],
      modelDetails: undefined,
      loadingModels: false,
    });
    expect(opts).toHaveLength(1);
    expect(opts[0]).toEqual({ value: '', label: 'Select a model...' });
  });

  it('shows loading placeholder when no model is saved and models are loading', () => {
    const opts = buildModelOptions({
      model: undefined,
      availableModels: [],
      modelDetails: undefined,
      loadingModels: true,
    });
    expect(opts).toHaveLength(1);
    expect(opts[0]).toEqual({ value: '', label: 'Loading models...' });
  });

  it('propagates blocked_by_policy flag onto matching options', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: ['qwen3:8b', 'gpt-5:cloud'],
      modelDetails: [
        { name: 'gpt-5:cloud', blocked_by_policy: true } as any,
      ],
      loadingModels: false,
    });
    expect(opts).toHaveLength(2);
    const blocked = opts.find((o) => o.value === 'gpt-5:cloud');
    expect(blocked?.disabled).toBe(true);
    expect(blocked?.label).toContain('Blocked by IT');
    const unblocked = opts.find((o) => o.value === 'qwen3:8b');
    expect(unblocked?.disabled).toBeFalsy();
  });
});

describe('shouldShowAlwaysOn', () => {
  it('returns true when showAlwaysOn=true and handler provided', () => {
    expect(shouldShowAlwaysOn({ showAlwaysOn: true, onAlwaysOnChange: () => {} })).toBe(true);
  });

  it('returns false when showAlwaysOn=false even if handler provided', () => {
    expect(shouldShowAlwaysOn({ showAlwaysOn: false, onAlwaysOnChange: () => {} })).toBe(false);
  });

  it('defaults to true when showAlwaysOn is undefined and handler provided (backcompat)', () => {
    expect(shouldShowAlwaysOn({ onAlwaysOnChange: () => {} })).toBe(true);
  });

  it('returns false when no handler regardless of showAlwaysOn', () => {
    expect(shouldShowAlwaysOn({ showAlwaysOn: true })).toBe(false);
  });
});

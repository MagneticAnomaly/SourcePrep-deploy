import { describe, it, expect } from 'vitest';
import { stripModeFields } from '../llmConfigHelpers';
import type { LLMConfig } from '../../../types';

const baseConfig: LLMConfig = {
  saved_endpoints: [],
  embedding: { source: 'endpoint', endpoint_id: 'e', model: 'nomic-embed-text' },
  small_model: { enabled: true, endpoint_id: 'e', model: 'qwen3:8b' },
  large_model: { enabled: false },
  code_model: { enabled: false },
  assignment_mode: 'structured',
  assignment_blocks: [
    { id: 'b1', endpoint_id: 'e', model: 'qwen3:8b', tasks: [] },
  ],
};

describe('stripModeFields', () => {
  it('removes assignment_mode', () => {
    const out = stripModeFields(baseConfig);
    expect('assignment_mode' in out).toBe(false);
  });

  it('removes assignment_blocks', () => {
    const out = stripModeFields(baseConfig);
    expect('assignment_blocks' in out).toBe(false);
  });

  it('preserves non-mode fields', () => {
    const out = stripModeFields(baseConfig);
    expect(out.small_model).toEqual(baseConfig.small_model);
    expect(out.embedding).toEqual(baseConfig.embedding);
    expect(out.saved_endpoints).toEqual(baseConfig.saved_endpoints);
  });

  it('does not mutate the input', () => {
    const snapshot = JSON.stringify(baseConfig);
    stripModeFields(baseConfig);
    expect(JSON.stringify(baseConfig)).toBe(snapshot);
  });
});

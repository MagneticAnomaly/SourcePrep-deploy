import { describe, it, expect } from 'vitest';
import { stripModeFields } from '../llmConfigHelpers';
import type { LLMConfig } from '../../../types';

const baseConfig: LLMConfig = {
  saved_endpoints: [{ id: 'e', name: 'Local', url: 'http://localhost:11434', provider: 'ollama' }],
  embedding: { source: 'endpoint', endpoint_id: 'e', model: 'nomic-embed-text' },
  small_model: { enabled: true, endpoint_id: 'e', model: 'qwen3:8b' },
  large_model: { enabled: false },
  code_model: { enabled: false },
  assignment_mode: 'structured',
  assignment_blocks: [
    { id: 'b1', endpoint_id: 'e', model: 'qwen3:8b', tasks: [] },
  ],
  model_context_cache: { 'qwen3:8b': 8192 },
};

describe('stripModeFields', () => {
  it('strips assignment_mode from output', () => {
    const out = stripModeFields(baseConfig);
    expect('assignment_mode' in out).toBe(false);
  });

  it('strips saved_endpoints from output', () => {
    const out = stripModeFields(baseConfig);
    expect('saved_endpoints' in out).toBe(false);
  });

  it('strips model_context_cache from output', () => {
    const out = stripModeFields(baseConfig);
    expect('model_context_cache' in out).toBe(false);
  });

  it('preserves assignment_blocks in output', () => {
    const out = stripModeFields(baseConfig);
    expect('assignment_blocks' in out).toBe(true);
    expect(out.assignment_blocks).toEqual(baseConfig.assignment_blocks);
  });

  it('preserves all other fields', () => {
    const out = stripModeFields(baseConfig);
    expect(out.small_model).toEqual(baseConfig.small_model);
    expect(out.embedding).toEqual(baseConfig.embedding);
    expect(out.large_model).toEqual(baseConfig.large_model);
    expect(out.code_model).toEqual(baseConfig.code_model);
  });

  it('does not mutate the input', () => {
    const snapshot = JSON.stringify(baseConfig);
    stripModeFields(baseConfig);
    expect(JSON.stringify(baseConfig)).toBe(snapshot);
  });
});

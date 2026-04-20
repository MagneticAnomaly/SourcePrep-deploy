import { describe, it, expect } from 'vitest';
import { isLocalProvider, LOCAL_PROVIDERS } from '../provider-utils';

describe('isLocalProvider', () => {
  it('returns true for ollama', () => {
    expect(isLocalProvider('ollama')).toBe(true);
  });

  it('returns true for lm-studio', () => {
    expect(isLocalProvider('lm-studio')).toBe(true);
  });

  it('returns false for openai', () => {
    expect(isLocalProvider('openai')).toBe(false);
  });

  it('returns false for anthropic', () => {
    expect(isLocalProvider('anthropic')).toBe(false);
  });

  it('returns false for google', () => {
    expect(isLocalProvider('google')).toBe(false);
  });

  it('returns false for openai-compatible', () => {
    expect(isLocalProvider('openai-compatible')).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isLocalProvider(undefined)).toBe(false);
  });
});

describe('LOCAL_PROVIDERS', () => {
  it('contains exactly ollama and lm-studio', () => {
    expect([...LOCAL_PROVIDERS].sort()).toEqual(['lm-studio', 'ollama']);
  });
});

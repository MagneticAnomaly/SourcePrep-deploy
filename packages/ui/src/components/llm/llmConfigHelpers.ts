import type { LLMConfig } from '../../types';

/** Return a shallow copy of the LLM config with mode-owned fields removed.
 *  Used by the debounced auto-save layer for change detection: mutations to
 *  `assignment_mode` or `assignment_blocks` are committed via the explicit
 *  "Apply mode" button path, not via auto-save. */
export function stripModeFields(cfg: LLMConfig): Omit<LLMConfig, 'assignment_mode' | 'assignment_blocks'> {
  const { assignment_mode: _m, assignment_blocks: _b, ...rest } = cfg;
  void _m;
  void _b;
  return rest;
}

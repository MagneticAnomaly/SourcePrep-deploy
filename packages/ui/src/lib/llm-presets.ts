/**
 * Phase 44: LLM Assignment Presets
 *
 * Three preset configurations for Mapped mode:
 * 1. Local Standard — mirrors the user's current Structured config
 * 2. Cloud / Hybrid — local small + cloud reasoning
 * 3. Blank Slate — empty, all 9 tasks unassigned
 */

import type { LLMAssignmentBlock, LLMConfig, CodragTaskId } from '../types';

let _blockCounter = 0;
function nextBlockId(): string {
  return `block-${Date.now()}-${++_blockCounter}`;
}

// ── Task groups matching the Structured tier layout ────────────────

const FAST_TASKS: CodragTaskId[] = ['catalogue', 'search_intent', 'augmentation'];
const CODE_TASKS: CodragTaskId[] = ['inferred_edges'];
const THINKING_TASKS: CodragTaskId[] = ['enrichment', 'clustering', 'atlas', 'deepening', 'audit'];

// ── Preset 1: Local Standard ──────────────────────────────────────

/**
 * Generates blocks that mirror the user's current Structured config.
 * If a slot is configured, it becomes a block. If not, its tasks are
 * merged into the nearest available block.
 */
export function presetLocalStandard(config: LLMConfig): LLMAssignmentBlock[] {
  const blocks: LLMAssignmentBlock[] = [];

  const smallEnabled = config.small_model?.enabled && config.small_model?.endpoint_id && config.small_model?.model;
  const largeEnabled = config.large_model?.enabled && config.large_model?.endpoint_id && config.large_model?.model;
  const codeEnabled = config.code_model?.enabled && config.code_model?.endpoint_id && config.code_model?.model;

  // Fast block
  if (smallEnabled) {
    const tasks: CodragTaskId[] = [...FAST_TASKS];
    // If no code model, absorb code tasks
    if (!codeEnabled) tasks.push(...CODE_TASKS);
    // If no large model, absorb thinking tasks too
    if (!largeEnabled) tasks.push(...THINKING_TASKS);

    blocks.push({
      id: nextBlockId(),
      endpoint_id: config.small_model.endpoint_id!,
      model: config.small_model.model!,
      tasks,
    });
  }

  // Thinking block (only if large is separately configured)
  if (largeEnabled) {
    const tasks: CodragTaskId[] = [...THINKING_TASKS];
    // If no small model, absorb fast tasks
    if (!smallEnabled) {
      tasks.push(...FAST_TASKS);
      if (!codeEnabled) tasks.push(...CODE_TASKS);
    }

    blocks.push({
      id: nextBlockId(),
      endpoint_id: config.large_model.endpoint_id!,
      model: config.large_model.model!,
      tasks,
    });
  }

  // Code block (only if code is separately configured AND small exists)
  if (codeEnabled && smallEnabled) {
    blocks.push({
      id: nextBlockId(),
      endpoint_id: config.code_model.endpoint_id!,
      model: config.code_model.model!,
      tasks: [...CODE_TASKS],
    });
  }

  // If nothing was configured, return empty (blank slate)
  return blocks;
}

// ── Preset 2: Cloud / Hybrid ──────────────────────────────────────

/**
 * Creates a 2-block layout: local small for cheap tasks, cloud for reasoning.
 * Uses the first Ollama endpoint for local and the first non-Ollama for cloud.
 * Falls back to whatever endpoints exist.
 */
export function presetCloudHybrid(config: LLMConfig): LLMAssignmentBlock[] {
  const endpoints = config.saved_endpoints || [];

  const localEp = endpoints.find((ep) => ep.provider === 'ollama') || endpoints[0];
  const cloudEp = endpoints.find((ep) => ep.provider !== 'ollama') || localEp;

  if (!localEp) return []; // No endpoints at all

  const blocks: LLMAssignmentBlock[] = [];

  // Local block: cheap fast tasks + code
  blocks.push({
    id: nextBlockId(),
    endpoint_id: localEp.id,
    model: config.small_model?.model || '',
    tasks: [...FAST_TASKS, ...CODE_TASKS],
  });

  // Cloud block: expensive reasoning tasks
  blocks.push({
    id: nextBlockId(),
    endpoint_id: cloudEp.id,
    model: '', // User must select a cloud model
    tasks: [...THINKING_TASKS],
  });

  return blocks;
}

// ── Preset 3: Blank Slate ─────────────────────────────────────────

export function presetBlankSlate(): LLMAssignmentBlock[] {
  return [];
}

// ── Preset Application Helper ─────────────────────────────────────

export type PresetId = 'local-standard' | 'cloud-hybrid' | 'blank-slate';

export const PRESET_OPTIONS: Array<{ value: PresetId; label: string; description: string }> = [
  { value: 'local-standard', label: 'Local Standard', description: 'Mirrors your current Structured config' },
  { value: 'cloud-hybrid', label: 'Cloud / Hybrid', description: 'Local fast + cloud reasoning' },
  { value: 'blank-slate', label: 'Blank Slate', description: 'Start from scratch' },
];

export function applyPreset(presetId: PresetId, config: LLMConfig): LLMAssignmentBlock[] {
  switch (presetId) {
    case 'local-standard':
      return presetLocalStandard(config);
    case 'cloud-hybrid':
      return presetCloudHybrid(config);
    case 'blank-slate':
      return presetBlankSlate();
  }
}

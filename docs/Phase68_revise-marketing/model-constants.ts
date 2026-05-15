/**
 * SINGLE SOURCE OF TRUTH: LLM Model & Hardware Recommendations
 * Move this to websites/apps/docs/src/lib/model-constants.ts after review.
 * Run: node websites/apps/scripts/audit_model_references.mjs
 */
export type ModelSlot = 'fast' | 'thinking' | 'code';
export type CloudProvider = 'openai' | 'google' | 'anthropic';
export type SpeedTier = 'high-end' | 'fast' | 'standard';

export interface LocalModel {
  name: string; size_gb: number; vram_gb: number;
  slot: ModelSlot; quality: number; note: string; ollamaLibrary: string;
}
export interface CloudModel {
  name: string; provider: CloudProvider;
  input_per_m: number; output_per_m: number;
  slot: 'fast' | 'thinking'; batch_profile: string;
}
export interface GPU {
  id: string; label: string; platform: string;
  vram_gb: number; usable_gb: number; speed: SpeedTier;
}
export interface VramTier {
  label: string; fast: string; thinking: string;
  code: string | null; singleModel?: boolean;
}

// ── Local LLM Models (Ollama) ── EDIT-Under no ciecumstances do we reccommend anything les than qwen314b and even that is old and tiny and we reccommend ollama cloud first
export const LOCAL_MODELS: LocalModel[] = [
  { name: 'qwen3:4b', size_gb: 2.5, vram_gb: 3, slot: 'fast', quality: 5, note: 'Best small model. Rivals 72B models at this size.', ollamaLibrary: 'qwen3' }, // NO NEVER USE 4b model ever 8b is absolut bottom
  { name: 'qwen3:1.7b', size_gb: 1.4, vram_gb: 2, slot: 'fast', quality: 3, note: 'Ultra-light. Decent JSON output.', ollamaLibrary: 'qwen3' }, // no no no
  { name: 'qwen3:0.6b', size_gb: 0.5, vram_gb: 1, slot: 'fast', quality: 1, note: 'Smallest option. May produce unreliable JSON.', ollamaLibrary: 'qwen3' },// lol
  { name: 'qwen3.5:35b', size_gb: 19, vram_gb: 20, slot: 'thinking', quality: 5, note: 'MoE — 35B total, only 3B active. Outstanding reasoning.', ollamaLibrary: 'qwen3' }, // reccommended
  { name: 'qwen3:14b', size_gb: 9.3, vram_gb: 10, slot: 'thinking', quality: 4, note: 'Strong reasoning. Best mid-range option.', ollamaLibrary: 'qwen3' }, // ok
  { name: 'qwen3:8b', size_gb: 5.2, vram_gb: 6, slot: 'thinking', quality: 3, note: 'Good reasoning. Default recommendation.', ollamaLibrary: 'qwen3' }, // absolute min 
  { name: 'qwen3:4b', size_gb: 2.5, vram_gb: 3, slot: 'thinking', quality: 2, note: 'Usable for thinking when VRAM is very limited.', ollamaLibrary: 'qwen3' },  /// no no
  { name: 'qwen3-coder:30b', size_gb: 19, vram_gb: 20, slot: 'code', quality: 5, note: 'MoE — 30B total, 3.3B active. Best code model on Ollama.', ollamaLibrary: 'qwen3-coder' }, // reccommended
  { name: 'qwen2.5-coder:7b', size_gb: 4.7, vram_gb: 5, slot: 'code', quality: 3, note: 'Specialized for code. Good at edge detection.', ollamaLibrary: 'qwen2.5-coder' }, // meh
];
export const DEFAULT_FAST_MODEL = LOCAL_MODELS.find(m => m.slot === 'fast' && m.quality === 5)!;
export const DEFAULT_THINKING_MODEL = LOCAL_MODELS.find(m => m.slot === 'thinking' && m.quality === 3)!;
export const DEFAULT_CODE_MODEL = LOCAL_MODELS.find(m => m.slot === 'code' && m.quality === 5)!;
export const FALLBACK_SINGLE_MODEL = DEFAULT_FAST_MODEL;

// ── Cloud LLM Models (BYOK) ──
export const CLOUD_MODELS: Record<CloudProvider, { fast: CloudModel; thinking: CloudModel }> = {
  openai: {
    fast: { name: 'gpt-4.1-nano', provider: 'openai', input_per_m: 0.10, output_per_m: 0.40, slot: 'fast', batch_profile: 'Standard' },
    thinking: { name: 'gpt-4.1-mini', provider: 'openai', input_per_m: 0.40, output_per_m: 1.60, slot: 'thinking', batch_profile: 'Standard' },
  },
  google: {
    fast: { name: 'gemini-2.5-flash-lite', provider: 'google', input_per_m: 0.075, output_per_m: 0.30, slot: 'fast', batch_profile: 'Compact' },
    thinking: { name: 'gemini-2.5-flash', provider: 'google', input_per_m: 0.15, output_per_m: 0.60, slot: 'thinking', batch_profile: 'Compact' },
  },
  anthropic: {
    fast: { name: 'claude-haiku-3.5', provider: 'anthropic', input_per_m: 0.80, output_per_m: 4.00, slot: 'fast', batch_profile: 'Compact' },
    thinking: { name: 'claude-sonnet-4.5', provider: 'anthropic', input_per_m: 3.00, output_per_m: 15.00, slot: 'thinking', batch_profile: 'Large' },
  },
};
export const CLOUD_SINGLE: Record<CloudProvider, CloudModel> = {
  openai: CLOUD_MODELS.openai.thinking, google: CLOUD_MODELS.google.thinking, anthropic: CLOUD_MODELS.anthropic.thinking,
};
export const PROVIDER_LABELS: Record<CloudProvider, string> = {
  openai: 'OpenAI', google: 'Google (Gemini)', anthropic: 'Anthropic (Claude)',
};

// ── Embedding Models ──
export const EMBEDDING_MODELS = {
  recommended: { name: 'nomic-embed-code', pullCmd: 'ollama pull manutic/nomic-embed-code', sizeDesc: '~4 GB', note: 'Code-specialized, GPU recommended' },
  standard: { name: 'nomic-embed-text', pullCmd: 'ollama pull nomic-embed-text', sizeDesc: '~274 MB', note: 'Good quality, works with or without GPU' },
  builtin: { name: 'nomic-embed-text-v1.5', pullCmd: '', sizeDesc: '~132 MB', note: 'Built-in ONNX, CPU only, no Ollama needed' },
};

// ── Stale / Deprecated Model Names ──
export const STALE_MODEL_NAMES = [
  'qwen2.5:', 'qwen2:', 'llama3:', 'llama-3:', 'deepseek-v2', 'deepseek-r1',
  'codellama', 'mistral:', 'phi3', 'phi-3', 'gemma:', 'starcoder',
  'o3-mini', 'gpt-4o', 'gpt-4-turbo',
  'claude 3.5 sonnet', 'claude-3.5-sonnet',
  'gemini 1.5 pro', 'gemini-1.5-pro', 'Qwen2.5-72B',
];

// ── GPU / Hardware ──
export const GPU_PLATFORMS = ['Apple Silicon', 'NVIDIA', 'AMD'] as const;
export const GPUS: GPU[] = [
  { id: 'apple-m1-8', label: 'M1 8GB', platform: 'Apple Silicon', vram_gb: 8, usable_gb: 5, speed: 'standard' },
  { id: 'apple-m1-16', label: 'M1 Pro/Max 16GB', platform: 'Apple Silicon', vram_gb: 16, usable_gb: 12, speed: 'fast' },
  { id: 'apple-m1-32', label: 'M1 Pro/Max 32GB', platform: 'Apple Silicon', vram_gb: 32, usable_gb: 24, speed: 'fast' },
  { id: 'apple-m2-8', label: 'M2 8GB', platform: 'Apple Silicon', vram_gb: 8, usable_gb: 5, speed: 'standard' },
  { id: 'apple-m2-16', label: 'M2 Pro 16GB', platform: 'Apple Silicon', vram_gb: 16, usable_gb: 12, speed: 'fast' },
  { id: 'apple-m2-32', label: 'M2 Pro/Max 32GB', platform: 'Apple Silicon', vram_gb: 32, usable_gb: 24, speed: 'fast' },
  { id: 'apple-m3-8', label: 'M3 8GB', platform: 'Apple Silicon', vram_gb: 8, usable_gb: 5, speed: 'standard' },
  { id: 'apple-m3-18', label: 'M3 Pro 18GB', platform: 'Apple Silicon', vram_gb: 18, usable_gb: 14, speed: 'fast' },
  { id: 'apple-m3-36', label: 'M3 Pro/Max 36GB', platform: 'Apple Silicon', vram_gb: 36, usable_gb: 28, speed: 'high-end' },
  { id: 'apple-m3-48', label: 'M3 Max 48GB', platform: 'Apple Silicon', vram_gb: 48, usable_gb: 40, speed: 'high-end' },
  { id: 'apple-m3-64', label: 'M3 Max 64GB', platform: 'Apple Silicon', vram_gb: 64, usable_gb: 56, speed: 'high-end' },
  { id: 'apple-m3-128', label: 'M3 Ultra 128GB', platform: 'Apple Silicon', vram_gb: 128, usable_gb: 112, speed: 'high-end' },
  { id: 'apple-m4-16', label: 'M4 16GB', platform: 'Apple Silicon', vram_gb: 16, usable_gb: 12, speed: 'fast' },
  { id: 'apple-m4-24', label: 'M4 Pro 24GB', platform: 'Apple Silicon', vram_gb: 24, usable_gb: 20, speed: 'high-end' },
  { id: 'apple-m4-48', label: 'M4 Max 48GB', platform: 'Apple Silicon', vram_gb: 48, usable_gb: 40, speed: 'high-end' },
  { id: 'apple-m4-64', label: 'M4 Max 64GB', platform: 'Apple Silicon', vram_gb: 64, usable_gb: 56, speed: 'high-end' },
  { id: 'apple-m4-128', label: 'M4 Ultra 128GB', platform: 'Apple Silicon', vram_gb: 128, usable_gb: 112, speed: 'high-end' },
  { id: 'nvidia-1080ti', label: 'GTX 1080 Ti 11GB', platform: 'NVIDIA', vram_gb: 11, usable_gb: 10, speed: 'standard' },
  { id: 'nvidia-3060', label: 'RTX 3060 12GB', platform: 'NVIDIA', vram_gb: 12, usable_gb: 11, speed: 'standard' },
  { id: 'nvidia-3070', label: 'RTX 3070 8GB', platform: 'NVIDIA', vram_gb: 8, usable_gb: 7, speed: 'fast' },
  { id: 'nvidia-3080', label: 'RTX 3080 10GB', platform: 'NVIDIA', vram_gb: 10, usable_gb: 9, speed: 'fast' },
  { id: 'nvidia-3090', label: 'RTX 3090 24GB', platform: 'NVIDIA', vram_gb: 24, usable_gb: 22, speed: 'fast' },
  { id: 'nvidia-4060', label: 'RTX 4060 8GB', platform: 'NVIDIA', vram_gb: 8, usable_gb: 7, speed: 'fast' },
  { id: 'nvidia-4070', label: 'RTX 4070 12GB', platform: 'NVIDIA', vram_gb: 12, usable_gb: 11, speed: 'fast' },
  { id: 'nvidia-4080', label: 'RTX 4080 16GB', platform: 'NVIDIA', vram_gb: 16, usable_gb: 15, speed: 'high-end' },
  { id: 'nvidia-4090', label: 'RTX 4090 24GB', platform: 'NVIDIA', vram_gb: 24, usable_gb: 23, speed: 'high-end' },
  { id: 'nvidia-5070ti', label: 'RTX 5070 Ti 16GB', platform: 'NVIDIA', vram_gb: 16, usable_gb: 15, speed: 'high-end' },
  { id: 'nvidia-5080', label: 'RTX 5080 16GB', platform: 'NVIDIA', vram_gb: 16, usable_gb: 15, speed: 'high-end' },
  { id: 'nvidia-5090', label: 'RTX 5090 32GB', platform: 'NVIDIA', vram_gb: 32, usable_gb: 30, speed: 'high-end' },
  { id: 'nvidia-a100-40', label: 'A100 40GB', platform: 'NVIDIA', vram_gb: 40, usable_gb: 38, speed: 'high-end' },
  { id: 'nvidia-a100-80', label: 'A100 80GB', platform: 'NVIDIA', vram_gb: 80, usable_gb: 78, speed: 'high-end' },
  { id: 'amd-7800xt', label: 'RX 7800 XT 16GB', platform: 'AMD', vram_gb: 16, usable_gb: 14, speed: 'fast' },
  { id: 'amd-7900xtx', label: 'RX 7900 XTX 24GB', platform: 'AMD', vram_gb: 24, usable_gb: 22, speed: 'fast' },
  { id: 'amd-9070xt', label: 'RX 9070 XT 16GB', platform: 'AMD', vram_gb: 16, usable_gb: 14, speed: 'fast' },
];
export const SPEED_INFO: Record<SpeedTier, { label: string; note: string; color: string }> = {
  'high-end': { label: 'High-end', note: 'Pipeline completes quickly (~50-80 tok/s)', color: 'text-green-500' },
  'fast': { label: 'Fast', note: 'A few minutes per stage (~25-45 tok/s)', color: 'text-blue-500' },
  'standard': { label: 'Standard', note: 'Slower — consider Hybrid for large repos (~10-20 tok/s)', color: 'text-yellow-500' },
};

// ── VRAM Quick-Ref ──
export const VRAM_TIERS: VramTier[] = [
  { label: '≤ 2GB', fast: 'qwen3:0.6b', thinking: 'qwen3:0.6b', code: null, singleModel: true },
  { label: '2-4GB', fast: 'qwen3:1.7b', thinking: 'qwen3:1.7b or qwen3:4b', code: null, singleModel: true },
  { label: '5-6GB', fast: 'qwen3:4b', thinking: 'qwen3:4b', code: null },
  { label: '6-12GB', fast: 'qwen3:4b', thinking: 'qwen3:8b', code: null },
  { label: '12-20GB', fast: 'qwen3:4b', thinking: 'qwen3:14b', code: 'qwen2.5-coder:7b' },
  { label: '20GB+', fast: 'qwen3:4b', thinking: 'qwen3:30b (MoE)', code: 'qwen3-coder:30b (MoE)' },
];

// ── Marketing-safe prose helpers ──
export const EXAMPLE_LOCAL_MODEL_FAMILIES = 'Qwen or Llama';
export const BYOK_EXAMPLE_MODELS = `${CLOUD_MODELS.anthropic.thinking.name}, ${CLOUD_MODELS.openai.thinking.name}, or ${CLOUD_MODELS.google.thinking.name}`;
export const DOCKER_BAKED_MODEL = DEFAULT_FAST_MODEL.name;
export const BYOK_CLI_EXAMPLE = CLOUD_MODELS.openai.thinking.name;

"use client";

// Recommendations stay family-level (e.g. "Claude Haiku", "Gemini Flash") rather
// than version-pinned ("claude-haiku-4-5"). Prices are described as cost tiers
// ($ / $$ / $$$) instead of per-million-token dollar amounts, so vendor pricing
// churn doesn't silently make this page wrong. Definitive per-version
// recommendations live in the dashboard config (model_advisor in core),
// not in marketing copy.

import { useState, useMemo } from 'react';
import { Monitor, Cloud, Zap, Cpu, HardDrive, ChevronDown, Check, AlertTriangle, Copy, ExternalLink, Zap as ZapIcon, Brain, Code, Lightbulb, Key } from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────

type DeployMode = 'local' | 'hybrid' | 'cloud';
type SpeedTier = 'high-end' | 'fast' | 'standard';
type CloudProvider = 'openai' | 'google' | 'anthropic';
type CloudSetup = '1-model' | '2-model';

interface GPU {
  id: string;
  label: string;
  platform: string;
  vram_gb: number;
  usable_gb: number;
  speed: SpeedTier;
}

interface LocalModel {
  name: string;
  size_gb: number;
  vram_gb: number;
  slot: 'fast' | 'thinking' | 'code';
  quality: number; // 1-5
  note?: string;
}

type CostTier = '$' | '$$' | '$$$';

interface CloudModel {
  name: string;          // family-level, e.g. "Claude Haiku", "Gemini Flash"
  provider: CloudProvider;
  cost_tier: CostTier;
  slot: 'fast' | 'thinking';
  batch_profile: string;
}

interface SlotRec {
  model: string;
  source: 'local' | 'cloud';
  vram_gb?: number;
  cost_tier?: CostTier;
  note?: string;
  ollama_url?: string;
}

interface ModelPlan {
  fast: SlotRec;
  thinking: SlotRec;
  code: SlotRec;
  cost_tier_overall?: CostTier;
  speed_note: string;
  warnings: string[];
  pull_commands: string[];
}

// Cost tier rubric. Pinned by tier, not vendor — same tier means roughly
// comparable price across vendors at any given moment.
const COST_TIER_NOTES: Record<CostTier, string> = {
  '$':   'Pennies per repo. Small/fast tier (e.g. Gemini Flash-Lite, GPT nano, Claude Haiku class).',
  '$$':  'Tens of cents to a dollar. Balanced tier (e.g. Gemini Flash, GPT mini class).',
  '$$$': 'A few dollars per repo. Premium tier (e.g. Claude Sonnet, GPT mid class).',
};

// ── GPU Database ─────────────────────────────────────────────────────

const GPU_PLATFORMS = ['Apple Silicon', 'NVIDIA', 'AMD'] as const;

const GPUS: GPU[] = [
  // Apple Silicon
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
  // NVIDIA
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
  // AMD
  { id: 'amd-7800xt', label: 'RX 7800 XT 16GB', platform: 'AMD', vram_gb: 16, usable_gb: 14, speed: 'fast' },
  { id: 'amd-7900xtx', label: 'RX 7900 XTX 24GB', platform: 'AMD', vram_gb: 24, usable_gb: 22, speed: 'fast' },
  { id: 'amd-9070xt', label: 'RX 9070 XT 16GB', platform: 'AMD', vram_gb: 16, usable_gb: 14, speed: 'fast' },
];

// ── Local Model Database ─────────────────────────────────────────────

const LOCAL_MODELS: LocalModel[] = [
  // Fast models (sorted by quality descending, then size ascending)
  { name: 'qwen3:4b', size_gb: 2.5, vram_gb: 3, slot: 'fast', quality: 5, note: 'Best small model. Rivals 72B models at this size.' },
  { name: 'qwen3:1.7b', size_gb: 1.4, vram_gb: 2, slot: 'fast', quality: 3, note: 'Ultra-light. Decent JSON output.' },
  { name: 'qwen3:0.6b', size_gb: 0.5, vram_gb: 1, slot: 'fast', quality: 1, note: 'Smallest option. May produce unreliable JSON.' },
  // Thinking models
  { name: 'qwen3:30b', size_gb: 19, vram_gb: 20, slot: 'thinking', quality: 5, note: 'MoE — 30B total, only 3B active. Outstanding reasoning.' },
  { name: 'qwen3:14b', size_gb: 9.3, vram_gb: 10, slot: 'thinking', quality: 4, note: 'Strong reasoning. Best mid-range option.' },
  { name: 'qwen3:8b', size_gb: 5.2, vram_gb: 6, slot: 'thinking', quality: 3, note: 'Good reasoning. Default recommendation.' },
  { name: 'qwen3:4b', size_gb: 2.5, vram_gb: 3, slot: 'thinking', quality: 2, note: 'Usable for thinking when VRAM is very limited.' },
  // Code models
  { name: 'qwen3-coder:30b', size_gb: 19, vram_gb: 20, slot: 'code', quality: 5, note: 'MoE — 30B total, 3.3B active. Best code model on Ollama.' },
  { name: 'qwen2.5-coder:7b', size_gb: 4.7, vram_gb: 5, slot: 'code', quality: 3, note: 'Specialized for code. Good at edge detection.' },
];

// ── Cloud Model Database ─────────────────────────────────────────────

// Family-level recommendations. Pick the current vendor model in that family
// when configuring the slot in SourcePrep — vendor catalogs ship new versions
// faster than this page updates, and pricing within a family tends to be
// roughly stable from one generation to the next.
const CLOUD_MODELS: Record<CloudProvider, { fast: CloudModel; thinking: CloudModel }> = {
  openai: {
    fast:     { name: 'OpenAI nano-class',  provider: 'openai',    cost_tier: '$',  slot: 'fast',     batch_profile: 'Standard' },
    thinking: { name: 'OpenAI mini-class',  provider: 'openai',    cost_tier: '$$', slot: 'thinking', batch_profile: 'Standard' },
  },
  google: {
    fast:     { name: 'Gemini Flash-Lite',  provider: 'google',    cost_tier: '$',  slot: 'fast',     batch_profile: 'Compact' },
    thinking: { name: 'Gemini Flash',       provider: 'google',    cost_tier: '$$', slot: 'thinking', batch_profile: 'Compact' },
  },
  anthropic: {
    fast:     { name: 'Claude Haiku',       provider: 'anthropic', cost_tier: '$$', slot: 'fast',     batch_profile: 'Compact' },
    thinking: { name: 'Claude Sonnet',      provider: 'anthropic', cost_tier: '$$$', slot: 'thinking', batch_profile: 'Large' },
  },
};

const CLOUD_SINGLE: Record<CloudProvider, CloudModel> = {
  openai:    { name: 'OpenAI mini-class', provider: 'openai',    cost_tier: '$$',  slot: 'thinking', batch_profile: 'Standard' },
  google:    { name: 'Gemini Flash',      provider: 'google',    cost_tier: '$$',  slot: 'thinking', batch_profile: 'Compact' },
  anthropic: { name: 'Claude Sonnet',     provider: 'anthropic', cost_tier: '$$$', slot: 'thinking', batch_profile: 'Large' },
};

const PROVIDER_LABELS: Record<CloudProvider, string> = {
  openai: 'OpenAI',
  google: 'Google (Gemini)',
  anthropic: 'Anthropic (Claude)',
};

// ── Speed Tier Labels ────────────────────────────────────────────────

const SPEED_INFO: Record<SpeedTier, { label: string; note: string; color: string }> = {
  'high-end': { label: 'High-end', note: 'Pipeline completes quickly (~50-80 tok/s)', color: 'text-green-500' },
  'fast': { label: 'Fast', note: 'A few minutes per stage (~25-45 tok/s)', color: 'text-blue-500' },
  'standard': { label: 'Standard', note: 'Slower — consider Hybrid for large repos (~10-20 tok/s)', color: 'text-yellow-500' },
};

// ── Recommendation Engine ────────────────────────────────────────────

const TIER_ORDER: Record<CostTier, number> = { '$': 1, '$$': 2, '$$$': 3 };

function maxTier(...tiers: (CostTier | undefined)[]): CostTier | undefined {
  const known = tiers.filter((t): t is CostTier => !!t);
  if (known.length === 0) return undefined;
  return known.sort((a, b) => TIER_ORDER[b] - TIER_ORDER[a])[0];
}

function bestLocalForSlot(slot: 'fast' | 'thinking' | 'code', maxVram: number): LocalModel | null {
  const candidates = LOCAL_MODELS
    .filter(m => m.slot === slot && m.vram_gb <= maxVram)
    .sort((a, b) => b.quality - a.quality);
  return candidates[0] || null;
}

function computePlan(
  mode: DeployMode,
  gpu: GPU | null,
  provider: CloudProvider,
  cloudSetup: CloudSetup,
): ModelPlan {
  const warnings: string[] = [];
  const pull: string[] = [];

  // ── Local mode ──
  if (mode === 'local') {
    const vram = gpu?.usable_gb ?? 6;
    const speed = gpu?.speed ?? 'standard';

    // Single-model edge case
    if (vram <= 4) {
      const single = bestLocalForSlot('fast', vram);
      if (!single) {
        return {
          fast: { model: '(none available)', source: 'local', note: 'Not enough VRAM' },
          thinking: { model: '(none available)', source: 'local', note: 'Not enough VRAM' },
          code: { model: '(none available)', source: 'local', note: 'Not enough VRAM' },
          speed_note: SPEED_INFO[speed].note,
          warnings: ['Your VRAM is very limited. Consider Hybrid mode (local Fast + cloud Thinking) for better results.'],
          pull_commands: [],
        };
      }
      warnings.push('Limited VRAM — using one model for all slots. Consider Hybrid mode for better quality.');
      pull.push(`ollama pull ${single.name}`);
      return {
        fast: { model: single.name, source: 'local', vram_gb: single.vram_gb, note: single.note },
        thinking: { model: single.name, source: 'local', vram_gb: single.vram_gb, note: 'Same model (VRAM limited)' },
        code: { model: single.name, source: 'local', vram_gb: single.vram_gb, note: 'Same model (VRAM limited)' },
        speed_note: SPEED_INFO[speed].note,
        warnings,
        pull_commands: pull,
      };
    }

    // Normal local: pick best Fast + best Thinking that fits
    const fast = bestLocalForSlot('fast', vram)!;
    const thinking = bestLocalForSlot('thinking', vram)!;
    // Code: only if there's room for a dedicated code model
    const code = bestLocalForSlot('code', vram);

    pull.push(`ollama pull ${fast.name}`);
    if (thinking.name !== fast.name) pull.push(`ollama pull ${thinking.name}`);

    const plan: ModelPlan = {
      fast: { model: fast.name, source: 'local', vram_gb: fast.vram_gb, note: fast.note },
      thinking: { model: thinking.name, source: 'local', vram_gb: thinking.vram_gb, note: thinking.note },
      code: code && code.vram_gb <= vram
        ? { model: code.name, source: 'local', vram_gb: code.vram_gb, note: code.note }
        : { model: fast.name, source: 'local', vram_gb: fast.vram_gb, note: 'Using Fast model (no dedicated code model needed)' },
      speed_note: SPEED_INFO[speed].note,
      warnings,
      pull_commands: pull,
    };

    if (code && code.vram_gb <= vram && code.name !== fast.name) {
      pull.push(`ollama pull ${code.name}`);
    }

    const peak = Math.max(fast.vram_gb, thinking.vram_gb, plan.code.vram_gb ?? 0);
    if (peak > vram * 0.9) {
      warnings.push('Peak VRAM usage is close to your limit. You may experience slower inference.');
    }

    return plan;
  }

  // ── Cloud mode ──
  if (mode === 'cloud') {
    if (cloudSetup === '1-model') {
      const m = CLOUD_SINGLE[provider];
      return {
        fast:     { model: m.name, source: 'cloud', cost_tier: m.cost_tier },
        thinking: { model: m.name, source: 'cloud', cost_tier: m.cost_tier },
        code:     { model: m.name, source: 'cloud', note: 'Same model' },
        cost_tier_overall: m.cost_tier,
        speed_note: 'Cloud models — fast network inference, no local GPU needed',
        warnings,
        pull_commands: [],
      };
    } else {
      const pair = CLOUD_MODELS[provider];
      return {
        fast:     { model: pair.fast.name,     source: 'cloud', cost_tier: pair.fast.cost_tier },
        thinking: { model: pair.thinking.name, source: 'cloud', cost_tier: pair.thinking.cost_tier },
        code:     { model: pair.fast.name,     source: 'cloud', cost_tier: pair.fast.cost_tier, note: 'Uses Fast model' },
        cost_tier_overall: maxTier(pair.fast.cost_tier, pair.thinking.cost_tier),
        speed_note: 'Cloud models — fast network inference, no local GPU needed',
        warnings,
        pull_commands: [],
      };
    }
  }

  // ── Hybrid mode ──
  {
    const vram = gpu?.usable_gb ?? 6;
    const speed = gpu?.speed ?? 'standard';
    const fast = bestLocalForSlot('fast', vram) ?? { name: 'qwen3:4b', size_gb: 2.5, vram_gb: 3, slot: 'fast' as const, quality: 5 };
    const cloudThinking = CLOUD_SINGLE[provider];

    pull.push(`ollama pull ${fast.name}`);

    return {
      fast:     { model: fast.name,          source: 'local', vram_gb: fast.vram_gb, note: 'Local — free, handles high-volume catalogue stage' },
      thinking: { model: cloudThinking.name, source: 'cloud', cost_tier: cloudThinking.cost_tier, note: 'Cloud — quality reasoning for enrichment' },
      code:     { model: cloudThinking.name, source: 'cloud', cost_tier: cloudThinking.cost_tier, note: 'Uses cloud Thinking model for better edge detection' },
      cost_tier_overall: cloudThinking.cost_tier,
      speed_note: `Local stages: ${SPEED_INFO[speed].note}. Cloud stages: fast.`,
      warnings,
      pull_commands: pull,
    };
  }
}

// ── UI Components ────────────────────────────────────────────────────

function ModeButton({ mode, selected, onClick, icon, title, subtitle }: {
  mode: DeployMode; selected: boolean; onClick: () => void;
  icon: React.ReactNode; title: string; subtitle: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded-lg border-2 p-4 text-left transition-all ${
        selected
          ? 'border-primary bg-primary/5 shadow-md'
          : 'border-border bg-surface hover:border-primary/40'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className={selected ? 'text-primary' : 'text-text-muted'}>{icon}</span>
        <span className="font-semibold text-sm">{title}</span>
      </div>
      <p className="text-xs text-text-muted">{subtitle}</p>
    </button>
  );
}

function SelectDropdown({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-text-muted mb-1">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full appearance-none rounded-md border border-border bg-surface px-3 py-2 pr-8 text-sm text-text focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          {options.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
      </div>
    </div>
  );
}

function VramBar({ usable, total, peak }: { usable: number; total: number; peak?: number }) {
  const pct = Math.min(100, (usable / total) * 100);
  const peakPct = peak ? Math.min(100, (peak / total) * 100) : 0;
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-text-muted mb-1">
        <span>Usable: {usable}GB of {total}GB</span>
        {peak !== undefined && <span>Peak model: {peak}GB</span>}
      </div>
      <div className="h-3 rounded-full bg-surface border border-border overflow-hidden relative">
        <div className="h-full rounded-full bg-primary/20" style={{ width: `${pct}%` }} />
        {peak !== undefined && (
          <div
            className={`absolute top-0 left-0 h-full rounded-full ${peakPct <= pct ? 'bg-primary/60' : 'bg-red-500/60'}`}
            style={{ width: `${peakPct}%` }}
          />
        )}
      </div>
    </div>
  );
}

function SlotCard({ label, rec, icon }: { label: string; rec: SlotRec; icon: React.ReactNode }) {
  const isCloud = rec.source === 'cloud';
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-primary">{icon}</span>
        <span className="font-semibold text-sm">{label}</span>
        <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
          isCloud ? 'bg-blue-500/10 text-blue-500' : 'bg-green-500/10 text-green-500'
        }`}>
          {isCloud ? 'Cloud' : 'Local'}
        </span>
      </div>
      <code className="text-sm font-mono text-primary">{rec.model}</code>
      {rec.vram_gb !== undefined && (
        <p className="text-xs text-text-muted mt-1">
          <HardDrive className="inline w-3 h-3 mr-1" />{rec.vram_gb}GB VRAM
        </p>
      )}
      {rec.cost_tier && (
        <p className="text-xs text-text-muted mt-1" title={COST_TIER_NOTES[rec.cost_tier]}>
          <span className="font-mono font-semibold text-text">{rec.cost_tier}</span>
          <span className="ml-1.5">tier — {COST_TIER_NOTES[rec.cost_tier]}</span>
        </p>
      )}
      {rec.note && (
        <p className="text-xs text-text-muted mt-2">{rec.note}</p>
      )}
    </div>
  );
}

function CopyBlock({ commands }: { commands: string[] }) {
  const [copied, setCopied] = useState(false);
  const text = commands.join('\n');
  return (
    <div className="relative rounded-md border border-border bg-surface p-3 font-mono text-sm">
      <button
        onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
        className="absolute top-2 right-2 p-1 rounded text-text-muted hover:text-text transition-colors"
        title="Copy"
      >
        {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
      </button>
      {commands.map((cmd, i) => (
        <div key={i} className="text-text-muted"><span className="text-text">$</span> {cmd}</div>
      ))}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────

export default function Page() {
  const [mode, setMode] = useState<DeployMode>('local');
  const [platform, setPlatform] = useState('Apple Silicon');
  const [gpuId, setGpuId] = useState('apple-m2-16');
  const [provider, setProvider] = useState<CloudProvider>('openai');
  const [cloudSetup, setCloudSetup] = useState<CloudSetup>('1-model');

  const platformGpus = useMemo(
    () => GPUS.filter(g => g.platform === platform),
    [platform],
  );

  const gpu = useMemo(() => GPUS.find(g => g.id === gpuId) ?? null, [gpuId]);

  // Reset GPU selection when platform changes
  const handlePlatformChange = (p: string) => {
    setPlatform(p);
    const first = GPUS.find(g => g.platform === p);
    if (first) setGpuId(first.id);
  };

  const plan = useMemo(
    () => computePlan(mode, gpu, provider, cloudSetup),
    [mode, gpu, provider, cloudSetup],
  );

  const peakVram = Math.max(
    plan.fast.vram_gb ?? 0,
    plan.thinking.vram_gb ?? 0,
    plan.code.vram_gb ?? 0,
  );

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          &larr; Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Model Setup Advisor
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          Get personalized model recommendations based on your hardware and preferences.
        </p>

        <div className="mt-6 rounded-lg border border-primary/30 bg-primary/5 p-4">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Cloud className="w-4 h-4 text-primary" /> Recommended: Ollama Cloud
          </h2>
          <p className="mt-1.5 text-sm text-text-muted">
            Route cloud-hosted models through one local Ollama config. You get cloud-grade
            quality without per-vendor API keys, pricing math, or version chasing — Ollama
            tracks the current generation for you. The picker below stays available for
            local-only and bring-your-own-key setups.
          </p>
        </div>

        {/* ── Step 1: Mode ── */}
        <div className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted mb-3">
            How do you want to run SourcePrep?
          </h2>
          <div className="flex gap-3">
            <ModeButton
              mode="local" selected={mode === 'local'} onClick={() => setMode('local')}
              icon={<Monitor className="w-5 h-5" />}
              title="Local" subtitle="Free &amp; private. Runs on your GPU."
            />
            <ModeButton
              mode="hybrid" selected={mode === 'hybrid'} onClick={() => setMode('hybrid')}
              icon={<Zap className="w-5 h-5" />}
              title="Hybrid" subtitle="Local fast + cloud thinking. Best of both."
            />
            <ModeButton
              mode="cloud" selected={mode === 'cloud'} onClick={() => setMode('cloud')}
              icon={<Cloud className="w-5 h-5" />}
              title="Cloud" subtitle="Fastest &amp; highest quality. Bring your own key."
            />
          </div>
        </div>

        {/* ── Step 2: GPU (Local/Hybrid) ── */}
        {(mode === 'local' || mode === 'hybrid') && (
          <div className="mt-8 rounded-lg border border-border p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted mb-4 flex items-center gap-2">
              <Cpu className="w-4 h-4" /> Your GPU
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectDropdown
                label="Platform"
                value={platform}
                onChange={handlePlatformChange}
                options={GPU_PLATFORMS.map(p => ({ value: p, label: p }))}
              />
              <SelectDropdown
                label="GPU Model"
                value={gpuId}
                onChange={setGpuId}
                options={platformGpus.map(g => ({ value: g.id, label: g.label }))}
              />
            </div>
            {gpu && (
              <>
                <VramBar usable={gpu.usable_gb} total={gpu.vram_gb} peak={peakVram > 0 ? peakVram : undefined} />
                <div className="mt-2 flex items-center gap-2 text-xs">
                  <span className={SPEED_INFO[gpu.speed].color}>&#9679;</span>
                  <span className="text-text-muted">
                    <span className="font-semibold text-text">{SPEED_INFO[gpu.speed].label}</span> &mdash; {SPEED_INFO[gpu.speed].note}
                  </span>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Step 2b: Cloud Provider (Cloud/Hybrid) ── */}
        {(mode === 'cloud' || mode === 'hybrid') && (
          <div className="mt-6 rounded-lg border border-border p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted mb-4 flex items-center gap-2">
              <Cloud className="w-4 h-4" /> Cloud Provider
            </h2>
            <div className={mode === 'cloud' ? 'grid gap-4 sm:grid-cols-2' : ''}>
              <SelectDropdown
                label="Provider"
                value={provider}
                onChange={v => setProvider(v as CloudProvider)}
                options={Object.entries(PROVIDER_LABELS).map(([k, v]) => ({ value: k, label: v }))}
              />
              {mode === 'cloud' && (
                <div>
                  <label className="block text-xs font-medium text-text-muted mb-1">Setup</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setCloudSetup('1-model')}
                      className={`flex-1 rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
                        cloudSetup === '1-model' ? 'border-primary bg-primary/5 text-primary' : 'border-border text-text-muted hover:border-primary/40'
                      }`}
                    >
                      1 model (simple)
                    </button>
                    <button
                      onClick={() => setCloudSetup('2-model')}
                      className={`flex-1 rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
                        cloudSetup === '2-model' ? 'border-primary bg-primary/5 text-primary' : 'border-border text-text-muted hover:border-primary/40'
                      }`}
                    >
                      2 models (save $)
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Recommendation ── */}
        <div className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted mb-4">
            Recommended Configuration
          </h2>

          {/* Warnings */}
          {plan.warnings.length > 0 && (
            <div className="mb-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-3">
              {plan.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-yellow-600">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          {/* Slot cards */}
          <div className="grid gap-3 sm:grid-cols-3">
            <SlotCard icon={<ZapIcon className="w-5 h-5" />} label="Fast Model" rec={plan.fast} />
            <SlotCard icon={<Brain className="w-5 h-5" />} label="Thinking Model" rec={plan.thinking} />
            <SlotCard icon={<Code className="w-5 h-5" />} label="Code Model" rec={plan.code} />
          </div>

          {/* Summary stats */}
          <div className="mt-4 flex flex-wrap gap-4 text-sm">
            {plan.cost_tier_overall && (
              <div className="flex items-center gap-1.5 text-text-muted">
                <span className="font-mono font-semibold text-text">{plan.cost_tier_overall}</span>
                <span>tier overall — {COST_TIER_NOTES[plan.cost_tier_overall]}</span>
              </div>
            )}
            {peakVram > 0 && (
              <div className="flex items-center gap-1.5 text-text-muted">
                <HardDrive className="w-4 h-4" />
                <span>Peak VRAM: <span className="font-semibold text-text">{peakVram}GB</span> (models swap, not cumulative)</span>
              </div>
            )}
          </div>
          <p className="mt-2 text-xs text-text-muted">{plan.speed_note}</p>

          {/* Pull commands */}
          {plan.pull_commands.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold mb-2">Quick Setup</h3>
              <CopyBlock commands={plan.pull_commands} />
            </div>
          )}

          {/* Cloud setup instructions */}
          {(mode === 'cloud' || mode === 'hybrid') && (
            <div className="mt-6 rounded-lg bg-surface border border-border p-4">
              <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
                <Key className="w-4 h-4 text-primary" /> Cloud Setup
              </h3>
              <ol className="text-xs text-text-muted space-y-1.5 list-decimal pl-4">
                <li>Get an API key from{' '}
                  <a href={
                    provider === 'openai' ? 'https://platform.openai.com/api-keys' :
                    provider === 'anthropic' ? 'https://console.anthropic.com/settings/keys' :
                    'https://aistudio.google.com/apikey'
                  } target="_blank" rel="noreferrer" className="text-primary hover:underline">
                    {PROVIDER_LABELS[provider]} <ExternalLink className="inline w-3 h-3" />
                  </a>
                </li>
                <li>In SourcePrep Dashboard, go to <span className="font-semibold text-text">Settings &gt; AI Models &gt; Saved Endpoints</span></li>
                <li>Add a new endpoint with provider &quot;{provider === 'google' ? 'OpenAI Compatible' : PROVIDER_LABELS[provider]}&quot;
                  {provider === 'google' && <span> and URL <code className="text-xs">https://generativelanguage.googleapis.com/v1beta/openai/</code></span>}
                </li>
                <li>Assign the endpoint and model to the appropriate slot(s)</li>
              </ol>
            </div>
          )}
        </div>

        {/* ── Reference Tables ── */}
        <div className="mt-12 prose max-w-none">
          <hr className="border-border" />

          <h2 className="text-xl font-bold mt-8 mb-4">Reference: All Recommended Models</h2>

          <h3 className="text-lg font-semibold mt-6 mb-3">Local (Ollama)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border">
              <thead>
                <tr className="bg-surface">
                  <th className="p-2 text-left border-b border-border text-text">Model</th>
                  <th className="p-2 text-left border-b border-border text-text">Slot</th>
                  <th className="p-2 text-left border-b border-border text-text">Size</th>
                  <th className="p-2 text-left border-b border-border text-text">VRAM</th>
                  <th className="p-2 text-left border-b border-border text-text">Notes</th>
                </tr>
              </thead>
              <tbody>
                {LOCAL_MODELS.filter((m, i, arr) => arr.findIndex(x => x.name === m.name && x.slot === m.slot) === i).map((m, i) => (
                  <tr key={i}>
                    <td className="p-2 border-b border-border font-mono text-xs">
                      <a href={`https://ollama.com/library/${m.name.split(':')[0]}`} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                        {m.name}
                      </a>
                    </td>
                    <td className="p-2 border-b border-border capitalize">{m.slot}</td>
                    <td className="p-2 border-b border-border">{m.size_gb}GB</td>
                    <td className="p-2 border-b border-border">~{m.vram_gb}GB</td>
                    <td className="p-2 border-b border-border text-text-muted text-xs">{m.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="text-lg font-semibold mt-8 mb-3">Cloud (BYOK)</h3>
          <p className="text-sm text-text-muted">
            Cost tiers are deliberately family-level. Vendor catalogs update faster than this page —
            check the vendor&apos;s pricing page for the exact per-million-token rate at any moment.
            <span className="ml-1.5 italic">${'$'} ≈ pennies, ${'$$'} ≈ tens-of-cents to a dollar, ${'$$$'} ≈ a few dollars per indexed repo.</span>
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border">
              <thead>
                <tr className="bg-surface">
                  <th className="p-2 text-left border-b border-border text-text">Family</th>
                  <th className="p-2 text-left border-b border-border text-text">Provider</th>
                  <th className="p-2 text-left border-b border-border text-text">Slot</th>
                  <th className="p-2 text-left border-b border-border text-text">Cost tier</th>
                  <th className="p-2 text-left border-b border-border text-text">Batch</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(CLOUD_MODELS).flatMap(pair => [pair.fast, pair.thinking]).map((m, i) => (
                  <tr key={i}>
                    <td className="p-2 border-b border-border text-xs">{m.name}</td>
                    <td className="p-2 border-b border-border">{PROVIDER_LABELS[m.provider]}</td>
                    <td className="p-2 border-b border-border capitalize">{m.slot}</td>
                    <td className="p-2 border-b border-border font-mono">{m.cost_tier}</td>
                    <td className="p-2 border-b border-border text-text-muted">{m.batch_profile}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="text-lg font-semibold mt-8 mb-3">VRAM Guide</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border">
              <thead>
                <tr className="bg-surface">
                  <th className="p-2 text-left border-b border-border text-text">Usable VRAM</th>
                  <th className="p-2 text-left border-b border-border text-text">Fast</th>
                  <th className="p-2 text-left border-b border-border text-text">Thinking</th>
                  <th className="p-2 text-left border-b border-border text-text">Code</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="p-2 border-b border-border font-medium text-text">&le; 2GB</td>
                  <td className="p-2 border-b border-border text-xs font-mono" colSpan={3}>qwen3:0.6b (single model for all)</td>
                </tr>
                <tr>
                  <td className="p-2 border-b border-border font-medium text-text">2&ndash;4GB</td>
                  <td className="p-2 border-b border-border text-xs font-mono" colSpan={3}>qwen3:1.7b or qwen3:4b (single model for all)</td>
                </tr>
                <tr>
                  <td className="p-2 border-b border-border font-medium text-text">5&ndash;6GB</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:4b</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:4b</td>
                  <td className="p-2 border-b border-border text-xs text-text-muted">(uses Fast)</td>
                </tr>
                <tr>
                  <td className="p-2 border-b border-border font-medium text-text">6&ndash;12GB</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:4b</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:8b</td>
                  <td className="p-2 border-b border-border text-xs text-text-muted">(uses Fast)</td>
                </tr>
                <tr>
                  <td className="p-2 border-b border-border font-medium text-text">12&ndash;20GB</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:4b</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:14b</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen2.5-coder:7b</td>
                </tr>
                <tr>
                  <td className="p-2 border-b border-border font-medium text-text">20GB+</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:4b</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3:30b (MoE)</td>
                  <td className="p-2 border-b border-border text-xs font-mono">qwen3-coder:30b (MoE)</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-8 rounded-lg bg-surface border border-border p-4">
            <h4 className="font-semibold flex items-center gap-2">
              <Lightbulb className="w-5 h-5 text-yellow-500" />
              Why Ollama models swap, not stack
            </h4>
            <p className="mt-2 text-sm">
              SourcePrep&apos;s pipeline runs one stage at a time. Ollama automatically loads and
              unloads models as needed, so you only need enough VRAM for the <span className="font-semibold text-text">single
              largest model</span> &mdash; not the total of all models combined.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

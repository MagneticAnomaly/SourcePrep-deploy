import { RotateCcw } from 'lucide-react';
import {
  Section,
  SettingRow,
  type AdvancedConfig,
} from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

// Defaults lifted verbatim from the legacy advanced settings panel (removed
// in T24). These power the per-field reset affordance.
const DEFAULTS = {
  chunk_max_chars: 2000,
  chunk_overlap_chars: 200,
  md_chunk_max_chars: 1800,
  md_chunk_min_chars: 350,
} as const;

export interface ChunkingEmbeddingsPageProps {
  config: AdvancedConfig;
  onChange: (patch: Partial<AdvancedConfig>) => void;
}

export function ChunkingEmbeddingsPage({ config, onChange }: ChunkingEmbeddingsPageProps) {
  return (
    <SettingsPage
      title="Chunking & Embeddings"
      scope="global"
      description="How source files and docs are split into chunks for embedding and search. Larger chunks capture more context; smaller chunks are more precise."
    >
      <Section title="Code chunks">
        <NumberRow
          id="chunk-max-chars"
          label="Code Chunk Size"
          description="Max characters per code chunk."
          value={config.chunk_max_chars}
          def={DEFAULTS.chunk_max_chars}
          min={500}
          max={10000}
          step={100}
          onChange={(v) => onChange({ chunk_max_chars: v })}
        />
        <NumberRow
          id="chunk-overlap"
          label="Code Overlap"
          description="Overlap between adjacent chunks."
          value={config.chunk_overlap_chars}
          def={DEFAULTS.chunk_overlap_chars}
          min={0}
          max={2000}
          step={50}
          onChange={(v) => onChange({ chunk_overlap_chars: v })}
          last
        />
      </Section>

      <Section title="Markdown chunks">
        <NumberRow
          id="md-chunk-max"
          label="Markdown Chunk Size"
          description="Max characters per documentation chunk."
          value={config.md_chunk_max_chars}
          def={DEFAULTS.md_chunk_max_chars}
          min={500}
          max={10000}
          step={100}
          onChange={(v) => onChange({ md_chunk_max_chars: v })}
        />
        <NumberRow
          id="md-chunk-min"
          label="Markdown Min Size"
          description="Sections smaller than this are merged."
          value={config.md_chunk_min_chars}
          def={DEFAULTS.md_chunk_min_chars}
          min={50}
          max={2000}
          step={50}
          onChange={(v) => onChange({ md_chunk_min_chars: v })}
          last
        />
      </Section>
    </SettingsPage>
  );
}

// ── File-local helper ────────────────────────────────────────────────────────

interface NumberRowProps {
  id: string;
  label: string;
  description: string;
  value: number;
  def: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  last?: boolean;
}

function NumberRow({ id, label, description, value, def, min, max, step, onChange, last }: NumberRowProps) {
  const isDefault = value === def;
  const control = (
    <div className="flex items-center gap-2">
      <input
        id={id}
        type="number"
        value={value}
        onChange={(e) => {
          const n = parseInt(e.target.value) || min;
          onChange(Math.max(min, Math.min(max, n)));
        }}
        min={min}
        max={max}
        step={step}
        className="w-28 bg-surface-raised border border-border rounded px-2 py-1.5 text-sm text-text focus:outline-none focus:ring-1 focus:ring-primary"
      />
      {!isDefault && (
        <button
          type="button"
          onClick={() => onChange(def)}
          className="text-text-muted hover:text-text transition-colors"
          title={`Reset to default (${def.toLocaleString()})`}
          aria-label={`Reset ${label} to default`}
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
  return (
    <SettingRow
      id={id}
      label={label}
      description={description}
      control={control}
      last={last}
    />
  );
}

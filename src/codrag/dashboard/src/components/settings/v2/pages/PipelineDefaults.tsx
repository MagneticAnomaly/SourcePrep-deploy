import { RotateCcw } from 'lucide-react';
import {
  Section,
  SettingRow,
  Select,
  type AdvancedConfig,
} from '@codrag/ui';
import { SettingsPage } from '../SettingsPage';

// Defaults lifted verbatim from the legacy advanced settings panel (removed
// in T24) for checkpoint_interval and min_edge_confidence. These power the
// per-field reset affordance.
const DEFAULTS = {
  checkpoint_interval: 500,
  min_edge_confidence: 0.5,
} as const;

const MAX_ACTIVE_OPTIONS = [
  { value: '1', label: '1 (Conservative)' },
  { value: '2', label: '2' },
  { value: '3', label: '3 (Standard)' },
  { value: '4', label: '4' },
  { value: '5', label: '5' },
  { value: 'infinite', label: 'Unlimited' },
];

export interface PipelineDefaultsPageProps {
  maxActiveProjects: number | 'infinite';
  onMaxActiveProjectsChange: (value: number | 'infinite') => void;
  config: AdvancedConfig;
  onChange: (patch: Partial<AdvancedConfig>) => void;
}

export function PipelineDefaultsPage({
  maxActiveProjects, onMaxActiveProjectsChange, config, onChange,
}: PipelineDefaultsPageProps) {
  return (
    <SettingsPage
      title="Pipeline Defaults"
      scope="global"
      description="Concurrency and enrichment thresholds applied to every pipeline run."
    >
      <Section title="Concurrency">
        <SettingRow
          id="max-active-projects"
          label="Max Active Projects"
          description="Local performance safeguard — how many projects may run LLM pipelines simultaneously. Increase if your hardware can handle more concurrency."
          control={
            <Select
              size="sm"
              value={String(maxActiveProjects)}
              onChange={(e) => {
                const v = e.target.value;
                onMaxActiveProjectsChange(v === 'infinite' ? 'infinite' : parseInt(v));
              }}
              options={MAX_ACTIVE_OPTIONS}
              aria-label="Max Active Projects"
            />
          }
          last
        />
      </Section>

      <Section title="Thresholds">
        <NumberRow
          id="checkpoint-interval"
          label="Checkpoint Interval"
          description="Save augmentation progress every N items. Lower = more frequent saves (slower but safer)."
          value={config.checkpoint_interval}
          def={DEFAULTS.checkpoint_interval}
          min={50}
          max={5000}
          step={50}
          onChange={(v) => onChange({ checkpoint_interval: v })}
        />
        <FloatRow
          id="min-edge-confidence"
          label="Min Edge Confidence"
          description="Inferred edges below this confidence threshold are discarded. Higher = fewer but more reliable edges."
          value={config.min_edge_confidence}
          def={DEFAULTS.min_edge_confidence}
          min={0.1}
          max={0.9}
          step={0.05}
          onChange={(v) => onChange({ min_edge_confidence: v })}
          last
        />
      </Section>
    </SettingsPage>
  );
}

// ── File-local helpers ───────────────────────────────────────────────────────

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

interface FloatRowProps {
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

function FloatRow({ id, label, description, value, def, min, max, step, onChange, last }: FloatRowProps) {
  const isDefault = value === def;
  const control = (
    <div className="flex flex-col gap-1 w-full">
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="range"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          min={min}
          max={max}
          step={step}
          className="flex-1 accent-primary"
        />
        {!isDefault && (
          <button
            type="button"
            onClick={() => onChange(def)}
            className="text-text-muted hover:text-text transition-colors"
            title={`Reset to default (${def})`}
            aria-label={`Reset ${label} to default`}
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div className="flex justify-between text-[10px] text-text-muted">
        <span>{min}</span>
        <span className="font-medium text-text">{value}</span>
        <span>{max}</span>
      </div>
    </div>
  );
  return (
    <SettingRow id={id} label={label} description={description} control={control} last={last} />
  );
}

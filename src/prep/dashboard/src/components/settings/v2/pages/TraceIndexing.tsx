import {
  Section,
  SettingRow,
  Toggle,
  type ProjectConfig,
} from '@prep/ui';
import { RotateCcw } from 'lucide-react';
import { SettingsPage } from '../SettingsPage';

// Defaults lifted verbatim from the legacy advanced settings panel (removed
// in T24). These power the per-field reset affordance.
const TRACE_LIMIT_DEFAULTS = {
  max_files: 50_000,
  max_nodes: 100_000,
  max_edges: 500_000,
} as const;

export interface TraceIndexingPageProps {
  projectName: string | null;
  config: ProjectConfig;
  /** True while a debounced autosave is in-flight — drives the "Saving…" indicator. */
  saving: boolean;
  onChange: (next: ProjectConfig) => void;
}

export function TraceIndexingPage({
  projectName,
  config,
  saving,
  onChange,
}: TraceIndexingPageProps) {
  const autoRebuild = config.auto_rebuild;
  const trace = config.trace;
  const advanced = config.advanced ?? {};

  const maxFiles = advanced.max_files ?? TRACE_LIMIT_DEFAULTS.max_files;
  const maxNodes = advanced.max_nodes ?? TRACE_LIMIT_DEFAULTS.max_nodes;
  const maxEdges = advanced.max_edges ?? TRACE_LIMIT_DEFAULTS.max_edges;

  const updateAdvanced = (key: 'max_files' | 'max_nodes' | 'max_edges', value: number) => {
    onChange({
      ...config,
      advanced: { ...advanced, [key]: value },
    });
  };

  const resetAdvanced = (key: 'max_files' | 'max_nodes' | 'max_edges') => {
    updateAdvanced(key, TRACE_LIMIT_DEFAULTS[key]);
  };

  // ── Controls ────────────────────────────────────────────────────────

  const liveUpdatesControl = (
    <Toggle
      checked={autoRebuild.enabled}
      onChange={(checked) =>
        onChange({
          ...config,
          auto_rebuild: { ...autoRebuild, enabled: checked },
        })
      }
    />
  );

  const debounceControl = (
    <div className="flex items-center gap-2 w-full">
      <input
        id="trace-debounce-ms"
        type="number"
        value={autoRebuild.debounce_ms ?? 5000}
        onChange={(e) =>
          onChange({
            ...config,
            auto_rebuild: {
              ...autoRebuild,
              debounce_ms: parseInt(e.target.value) || 5000,
            },
          })
        }
        min={1000}
        max={60000}
        step={1000}
        className="flex-1 bg-surface-raised border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
      />
      <span className="text-[10px] text-text-muted w-12 text-right">ms</span>
    </div>
  );

  const traceEnabledControl = (
    <Toggle
      checked={trace.enabled}
      onChange={(checked) =>
        onChange({ ...config, trace: { ...trace, enabled: checked } })
      }
    />
  );

  const limitInput = (args: {
    id: string;
    value: number;
    defaultValue: number;
    min: number;
    max: number;
    step: number;
    unit: string;
    onChange: (v: number) => void;
    onReset: () => void;
  }) => {
    const showReset = args.value !== args.defaultValue;
    return (
      <div className="flex items-center gap-2 w-full">
        <input
          id={args.id}
          type="number"
          value={args.value}
          onChange={(e) => args.onChange(parseInt(e.target.value) || args.defaultValue)}
          min={args.min}
          max={args.max}
          step={args.step}
          className="flex-1 bg-surface-raised border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <span className="text-[10px] text-text-muted w-16 text-right">{args.unit}</span>
        {showReset && (
          <button
            type="button"
            onClick={args.onReset}
            className="text-text-subtle hover:text-text transition-colors"
            title="Reset to default"
            aria-label={`Reset ${args.id} to default`}
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    );
  };

  const maxFilesControl = limitInput({
    id: 'trace-max-files',
    value: maxFiles,
    defaultValue: TRACE_LIMIT_DEFAULTS.max_files,
    min: 1000,
    max: 200_000,
    step: 5000,
    unit: `${(maxFiles / 1000).toFixed(0)}K files`,
    onChange: (v) => updateAdvanced('max_files', v),
    onReset: () => resetAdvanced('max_files'),
  });

  const maxNodesControl = limitInput({
    id: 'trace-max-nodes',
    value: maxNodes,
    defaultValue: TRACE_LIMIT_DEFAULTS.max_nodes,
    min: 10_000,
    max: 1_000_000,
    step: 50_000,
    unit: `${(maxNodes / 1000).toFixed(0)}K nodes`,
    onChange: (v) => updateAdvanced('max_nodes', v),
    onReset: () => resetAdvanced('max_nodes'),
  });

  const maxEdgesControl = limitInput({
    id: 'trace-max-edges',
    value: maxEdges,
    defaultValue: TRACE_LIMIT_DEFAULTS.max_edges,
    min: 50_000,
    max: 5_000_000,
    step: 100_000,
    unit: `${(maxEdges / 1000).toFixed(0)}K edges`,
    onChange: (v) => updateAdvanced('max_edges', v),
    onReset: () => resetAdvanced('max_edges'),
  });

  const savingIndicator = saving ? (
    <span className="text-xs text-text-muted">Saving…</span>
  ) : null;

  const description = projectName
    ? `How ${projectName}'s code graph is built and refreshed.`
    : "How this project's code graph is built and refreshed.";

  return (
    <SettingsPage
      title="Trace & Indexing"
      scope="project"
      description={description}
      actions={savingIndicator}
    >
      <Section title="Trace">
        <SettingRow
          id="trace-auto-rebuild"
          label="Live Updates"
          description="Automatically rebuilds the index when files change. Recommended for most users."
          control={liveUpdatesControl}
        />
        {autoRebuild.enabled && (
          <SettingRow
            id="trace-debounce-ms"
            label="Debounce (ms)"
            description="Delay before rebuilding after file changes."
            control={debounceControl}
          />
        )}
        <SettingRow
          id="trace-enabled"
          label="Structural Graph"
          description="Enables advanced code navigation (references, definitions). Disabling this reduces memory usage but limits context quality."
          control={traceEnabledControl}
          last
        />
      </Section>

      <Section title="Trace Limits">
        <SettingRow
          id="trace-max-files"
          label="Max Files"
          description="Maximum number of source files to trace. Files beyond this are silently skipped."
          control={maxFilesControl}
        />
        <SettingRow
          id="trace-max-nodes"
          label="Max Nodes"
          description="Maximum AST nodes (functions, classes, files) in the code graph."
          control={maxNodesControl}
        />
        <SettingRow
          id="trace-max-edges"
          label="Max Edges"
          description="Maximum relationships (imports, calls, references) in the code graph."
          control={maxEdgesControl}
          last
        />
      </Section>
    </SettingsPage>
  );
}

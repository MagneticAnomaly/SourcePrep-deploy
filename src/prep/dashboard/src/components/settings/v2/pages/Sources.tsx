import { useState } from 'react';
import {
  Button,
  InfoTooltip,
  Section,
  SettingRow,
  Toggle,
  type ProjectConfig,
} from '@prep/ui';
import {
  Check,
  ChevronDown,
  ChevronUp,
  Layers,
  Plus,
  Save,
  Wand2,
  X,
} from 'lucide-react';
import { SettingsPage } from '../SettingsPage';

const DEFAULT_PRESETS: Record<string, string[]> = {
  'Web (JS/TS)': ['**/*.js', '**/*.jsx', '**/*.ts', '**/*.tsx', '**/*.html', '**/*.css', '**/*.json'],
  Python: ['**/*.py', '**/*.ipynb'],
  'iOS (Swift/ObjC)': ['**/*.swift', '**/*.h', '**/*.m', '**/*.mm'],
  Rust: ['**/*.rs', '**/*.toml'],
  Go: ['**/*.go', '**/*.mod'],
  'Java/Kotlin': ['**/*.java', '**/*.kt', '**/*.kts', '**/*.gradle'],
  'C/C++': ['**/*.c', '**/*.cpp', '**/*.h', '**/*.hpp', '**/*.cc'],
  'C#': ['**/*.cs'],
  Ruby: ['**/*.rb'],
  PHP: ['**/*.php'],
  Shell: ['**/*.sh', '**/*.bash', '**/*.zsh'],
  Configuration: ['**/*.yaml', '**/*.yml', '**/*.json', '**/*.toml', '**/*.xml', '**/*.ini', '**/*.env'],
  Documentation: ['**/*.md', '**/*.markdown', '**/*.txt'],
};

export interface SourcesPageProps {
  /** Name of the active project — used in the description copy. */
  projectName: string | null;
  config: ProjectConfig;
  dirty: boolean;
  /** Applies a full replacement config (matches handleProjectConfigChange). */
  onChange: (next: ProjectConfig) => void;
  onSave: () => void | Promise<void>;
  onDiscard: () => void;
  saving: boolean;
  onDetectStack?: () => Promise<{
    recommended_globs: string[];
    detected_presets: string[];
    all_presets: Record<string, string[]>;
  }>;
}

export function SourcesPage({
  projectName,
  config,
  dirty,
  onChange,
  onSave,
  onDiscard,
  saving,
  onDetectStack,
}: SourcesPageProps) {
  const [includeInput, setIncludeInput] = useState('');
  const [excludeInput, setExcludeInput] = useState('');
  const [detecting, setDetecting] = useState(false);
  const [detectedMessage, setDetectedMessage] = useState<string | null>(null);
  const [availablePresets, setAvailablePresets] = useState<Record<string, string[]>>(DEFAULT_PRESETS);
  const [detectedPresetNames, setDetectedPresetNames] = useState<string[]>([]);
  const [showAllIncludes, setShowAllIncludes] = useState(false);
  const [showAllExcludes, setShowAllExcludes] = useState(false);

  const addGlob = (list: string[], val: string) => {
    if (!val.trim()) return list;
    const clean = val.trim();
    if (list.includes(clean)) return list;
    return [...list, clean];
  };

  const addIncludeGlob = () => {
    if (includeInput.trim()) {
      onChange({
        ...config,
        include_globs: addGlob(config.include_globs, includeInput),
      });
      setIncludeInput('');
    }
  };

  const removeIncludeGlob = (glob: string) => {
    onChange({
      ...config,
      include_globs: config.include_globs.filter((g) => g !== glob),
    });
  };

  const addExcludeGlob = () => {
    if (excludeInput.trim()) {
      onChange({
        ...config,
        exclude_globs: addGlob(config.exclude_globs, excludeInput),
      });
      setExcludeInput('');
    }
  };

  const removeExcludeGlob = (glob: string) => {
    onChange({
      ...config,
      exclude_globs: config.exclude_globs.filter((g) => g !== glob),
    });
  };

  const handleAutoDetect = async () => {
    if (!onDetectStack) return;
    setDetecting(true);
    setDetectedMessage(null);
    try {
      const result = await onDetectStack();
      if (result.all_presets && Object.keys(result.all_presets).length > 0) {
        setAvailablePresets(result.all_presets);
      }
      setDetectedPresetNames(result.detected_presets || []);

      const newGlobs = [...config.include_globs];
      let addedCount = 0;
      for (const glob of result.recommended_globs) {
        if (!newGlobs.includes(glob)) {
          newGlobs.push(glob);
          addedCount++;
        }
      }

      if (addedCount > 0) {
        onChange({ ...config, include_globs: newGlobs });
        setDetectedMessage(
          `Detected ${result.detected_presets.join(', ')}. Added ${addedCount} patterns.`,
        );
      } else if (result.detected_presets.length > 0) {
        setDetectedMessage(
          `Detected ${result.detected_presets.join(', ')} (patterns already present).`,
        );
      } else {
        setDetectedMessage('No specific stack detected.');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('fetch') || msg.includes('network') || msg.includes('Failed')) {
        setDetectedMessage('Detection failed — is the Prep daemon running?');
      } else {
        setDetectedMessage(`Detection failed: ${msg}`);
      }
    } finally {
      setDetecting(false);
      setTimeout(() => setDetectedMessage(null), 5000);
    }
  };

  const handleAddPreset = (presetName: string) => {
    const patterns = availablePresets[presetName];
    if (!patterns) return;

    const newGlobs = [...config.include_globs];
    let addedCount = 0;
    for (const glob of patterns) {
      if (!newGlobs.includes(glob)) {
        newGlobs.push(glob);
        addedCount++;
      }
    }

    if (addedCount > 0) {
      onChange({ ...config, include_globs: newGlobs });
      setDetectedMessage(`Added ${presetName} patterns.`);
    } else {
      setDetectedMessage(`${presetName} patterns already active.`);
    }
    setTimeout(() => setDetectedMessage(null), 3000);
  };

  const includePatternsEditor = (
    <div className="w-full">
      {/* Auto-detect + presets row */}
      <div className="flex items-center justify-between gap-2 mb-2">
        {onDetectStack ? (
          <div className="flex items-center gap-2 min-w-0">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAutoDetect}
              disabled={detecting}
              className="h-7 text-xs gap-1.5 flex-shrink-0"
            >
              <Wand2 className={detecting ? 'w-3.5 h-3.5 animate-spin' : 'w-3.5 h-3.5'} />
              {detecting ? 'Scanning...' : 'Auto-Detect Stack'}
            </Button>
            {detectedMessage && (
              <span className="text-xs text-primary truncate">{detectedMessage}</span>
            )}
          </div>
        ) : (
          <span />
        )}
        <div className="relative group flex-shrink-0">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs gap-1.5 text-text-subtle hover:text-text"
          >
            <Layers className="w-3.5 h-3.5" />
            Presets
          </Button>
          <div className="absolute right-0 top-full mt-1 w-52 py-1 rounded-md border border-border bg-surface-raised shadow-lg z-50 hidden group-hover:block max-h-72 overflow-y-auto">
            {Object.keys(availablePresets)
              .sort()
              .map((preset) => {
                const isDetected = detectedPresetNames.includes(preset);
                return (
                  <button
                    key={preset}
                    onClick={() => handleAddPreset(preset)}
                    className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-surface transition-colors flex items-center justify-between gap-2"
                  >
                    <span>{preset}</span>
                    {isDetected && <Check className="w-3 h-3 text-success shrink-0" />}
                  </button>
                );
              })}
          </div>
        </div>
      </div>

      {/* Add pattern input */}
      <div className="flex gap-2 mb-2">
        <input
          type="text"
          placeholder="**/*.py"
          value={includeInput}
          onChange={(e) => setIncludeInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addIncludeGlob()}
          className="flex-1 bg-surface-raised border border-border rounded-md px-3 py-1.5 text-sm text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
        />
        <Button
          onClick={addIncludeGlob}
          disabled={!includeInput.trim()}
          size="sm"
          variant="outline"
          icon={Plus}
        >
          Add
        </Button>
      </div>

      <div className="flex flex-col mt-2">
        {(showAllIncludes ? config.include_globs : config.include_globs.slice(0, 6)).map((glob) => (
          <div key={glob} className="flex items-center justify-between gap-2 py-0.5 group">
            <span className="text-sm font-mono text-text truncate">{glob}</span>
            <button
              onClick={() => removeIncludeGlob(glob)}
              className="text-text-subtle hover:text-error transition-colors opacity-0 group-hover:opacity-100"
              aria-label={`Remove ${glob}`}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}

        {config.include_globs.length > 6 && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setShowAllIncludes(!showAllIncludes)}
              className="flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary-hover transition-colors"
            >
              {showAllIncludes ? (
                <>
                  <ChevronUp className="w-3.5 h-3.5" />
                  Show Less
                </>
              ) : (
                <>
                  <ChevronDown className="w-3.5 h-3.5" />
                  View {config.include_globs.length - 6} more patterns
                </>
              )}
            </button>
          </div>
        )}

        {config.include_globs.length === 0 && (
          <div className="text-xs text-text-subtle italic py-1">No patterns defined</div>
        )}
      </div>
    </div>
  );

  const excludePatternsEditor = (
    <div className="w-full">
      <div className="flex gap-2 mb-2">
        <input
          type="text"
          placeholder="**/node_modules/**"
          value={excludeInput}
          onChange={(e) => setExcludeInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addExcludeGlob()}
          className="flex-1 bg-surface-raised border border-border rounded-md px-3 py-1.5 text-sm text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
        />
        <Button
          onClick={addExcludeGlob}
          disabled={!excludeInput.trim()}
          size="sm"
          variant="outline"
          icon={Plus}
        >
          Add
        </Button>
      </div>

      <div className="flex flex-col mt-2">
        {(showAllExcludes ? config.exclude_globs : config.exclude_globs.slice(0, 6)).map((glob) => (
          <div key={glob} className="flex items-center justify-between gap-2 py-0.5 group">
            <span className="text-sm font-mono text-text truncate">{glob}</span>
            <button
              onClick={() => removeExcludeGlob(glob)}
              className="text-text-subtle hover:text-error transition-colors opacity-0 group-hover:opacity-100"
              aria-label={`Remove ${glob}`}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}

        {config.exclude_globs.length > 6 && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setShowAllExcludes(!showAllExcludes)}
              className="flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary-hover transition-colors"
            >
              {showAllExcludes ? (
                <>
                  <ChevronUp className="w-3.5 h-3.5" />
                  Show Less
                </>
              ) : (
                <>
                  <ChevronDown className="w-3.5 h-3.5" />
                  View {config.exclude_globs.length - 6} more patterns
                </>
              )}
            </button>
          </div>
        )}

        {config.exclude_globs.length === 0 && (
          <div className="text-xs text-text-subtle italic py-1">No exclude patterns defined</div>
        )}
      </div>
    </div>
  );

  const maxFileBytesControl = (
    <div className="flex items-center gap-2 w-full">
      <input
        id="sources-max-file-bytes"
        type="number"
        value={config.max_file_bytes}
        onChange={(e) => onChange({ ...config, max_file_bytes: parseInt(e.target.value) || 0 })}
        min={1000}
        max={10000000}
        step={10000}
        className="flex-1 bg-surface-raised border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
      />
      <span className="text-[10px] text-text-muted w-12 text-right">
        {(config.max_file_bytes / 1000).toFixed(0)} KB
      </span>
    </div>
  );

  const hardLimitBytesControl = (
    <div className="flex items-center gap-2 w-full">
      <input
        id="sources-hard-limit-bytes"
        type="number"
        value={config.hard_limit_bytes || 100000000}
        onChange={(e) => onChange({ ...config, hard_limit_bytes: parseInt(e.target.value) || 0 })}
        min={100000}
        max={1000000000}
        step={1000000}
        className="flex-1 bg-surface-raised border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
      />
      <span className="text-[10px] text-text-muted w-12 text-right">
        {((config.hard_limit_bytes || 100000000) / 1000000).toFixed(0)} MB
      </span>
    </div>
  );

  const saveAction = (
    <div className="flex items-center gap-2">
      {dirty && (
        <Button variant="ghost" size="sm" onClick={onDiscard} disabled={saving}>
          Discard
        </Button>
      )}
      <Button
        size="sm"
        onClick={() => void onSave()}
        disabled={!dirty || saving}
        icon={Save}
        className="bg-primary text-primary-foreground"
      >
        {saving ? 'Saving…' : 'Save Changes'}
      </Button>
    </div>
  );

  const description = projectName
    ? `Which files are included in ${projectName}'s index.`
    : "Which files are included in this project's index.";

  return (
    <SettingsPage
      title="Sources & Scope"
      scope="project"
      description={description}
      actions={saveAction}
      dirty={dirty}
    >
      <Section title="Include Patterns">
        {/* The include-pattern editor is multi-line (auto-detect, presets,
            input, list). Use a stacked full-width row rather than the standard
            SettingRow (which constrains the control to a ~260px column). */}
        <StackedSettingRow
          label="Include Patterns"
          tooltip="Glob patterns for files to include. This acts as an allowlist (e.g. **/*.ts)."
          description={
            <>
              Only files matching these patterns will be indexed. Use{' '}
              <code className="bg-surface-raised px-1 rounded">**/*</code> to include everything not
              excluded.
            </>
          }
          control={includePatternsEditor}
          last
        />
      </Section>

      <Section title="Exclude Patterns">
        <SettingRow
          id="sources-use-gitignore"
          label="Use .gitignore"
          description="Exclude .gitignore files"
          control={
            <Toggle
              checked={config.use_gitignore}
              onChange={(checked) => onChange({ ...config, use_gitignore: checked })}
            />
          }
        />
        <StackedSettingRow
          label="Exclude Patterns"
          tooltip="Glob patterns for files to completely ignore."
          control={excludePatternsEditor}
          last
        />
      </Section>

      <Section title="Size Limits">
        <SettingRow
          id="sources-max-file-bytes"
          label="Max File Size (Index)"
          description="Files larger than this (in bytes) will be summarized rather than fully indexed."
          control={maxFileBytesControl}
        />
        <SettingRow
          id="sources-hard-limit-bytes"
          label="Hard Limit (Ignore)"
          description="Files larger than this are completely ignored to prevent crashes."
          control={hardLimitBytesControl}
          last
        />
      </Section>
    </SettingsPage>
  );
}

// ── Local layout helper ───────────────────────────────────────────────
// The glob list editors are multi-line and need the full page width. The
// shared `SettingRow` primitive locks the control to a ~260px right column,
// so we render a stacked row ourselves when a control needs full width.
// Label/tooltip/help-text copy is preserved verbatim from the drawer.

interface StackedSettingRowProps {
  label: string;
  tooltip?: string;
  description?: React.ReactNode;
  control: React.ReactNode;
  last?: boolean;
  id?: string;
}

function StackedSettingRow({
  label,
  tooltip,
  description,
  control,
  last,
  id,
}: StackedSettingRowProps) {
  return (
    <div className={last ? 'py-4' : 'py-4 border-b border-border-subtle'}>
      <div className="flex items-center gap-2 mb-1">
        {id ? (
          <label htmlFor={id} className="text-sm font-medium text-text">
            {label}
          </label>
        ) : (
          <div className="text-sm font-medium text-text">{label}</div>
        )}
        {tooltip && <InfoTooltip content={tooltip} />}
      </div>
      {description && <div className="text-sm text-text-muted mb-3">{description}</div>}
      <div className="mt-2">{control}</div>
    </div>
  );
}

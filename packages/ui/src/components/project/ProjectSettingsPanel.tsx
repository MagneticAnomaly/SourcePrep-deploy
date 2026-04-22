import { useState } from 'react';
import { cn } from '../../lib/utils';
import type { ProjectConfig, ProjectMode } from '../../types';
import { Plus, X, Save, Database, FolderOpen, Wand2, Layers, Check, ChevronDown, ChevronUp, Cpu, Zap, Network, FileCode, FileX } from 'lucide-react';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';

const DEFAULT_PRESETS: Record<string, string[]> = {
  "Web (JS/TS)": ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.html", "**/*.css", "**/*.json"],
  "Python": ["**/*.py", "**/*.ipynb"],
  "iOS (Swift/ObjC)": ["**/*.swift", "**/*.h", "**/*.m", "**/*.mm"],
  "Rust": ["**/*.rs", "**/*.toml"],
  "Go": ["**/*.go", "**/*.mod"],
  "Java/Kotlin": ["**/*.java", "**/*.kt", "**/*.kts", "**/*.gradle"],
  "C/C++": ["**/*.c", "**/*.cpp", "**/*.h", "**/*.hpp", "**/*.cc"],
  "C#": ["**/*.cs"],
  "Ruby": ["**/*.rb"],
  "PHP": ["**/*.php"],
  "Shell": ["**/*.sh", "**/*.bash", "**/*.zsh"],
  "Configuration": ["**/*.yaml", "**/*.yml", "**/*.json", "**/*.toml", "**/*.xml", "**/*.ini", "**/*.env"],
  "Documentation": ["**/*.md", "**/*.markdown", "**/*.txt"],
};

export interface ProjectSettingsPanelProps {
  config: ProjectConfig;
  mode?: ProjectMode;
  path?: string;
  onChange: (config: ProjectConfig) => void;
  onSave: () => void;
  onDetectStack?: () => Promise<{
    recommended_globs: string[];
    detected_presets: string[];
    all_presets: Record<string, string[]>;
  }>;
  isDirty?: boolean;
  className?: string;
  bare?: boolean;
}

export function ProjectSettingsPanel({
  config,
  mode,
  path,
  onChange,
  onSave,
  onDetectStack,
  isDirty = false,
  className,
  bare = false,
}: ProjectSettingsPanelProps) {
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
      
      // Merge recommended globs
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
        setDetectedMessage(`Detected ${result.detected_presets.join(', ')}. Added ${addedCount} patterns.`);
      } else if (result.detected_presets.length > 0) {
        setDetectedMessage(`Detected ${result.detected_presets.join(', ')} (patterns already present).`);
      } else {
        setDetectedMessage('No specific stack detected.');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('fetch') || msg.includes('network') || msg.includes('Failed')) {
        setDetectedMessage('Detection failed — is the SourcePrep daemon running?');
      } else {
        setDetectedMessage(`Detection failed: ${msg}`);
      }
    } finally {
      setDetecting(false);
      // Clear message after 3s
      setTimeout(() => setDetectedMessage(null), 5000);
    }
  };

  const handleAddPreset = (presetName: string) => {
    if (!availablePresets) return;
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

  const Toggle = ({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) => (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
        checked ? 'bg-primary' : 'bg-surface-raised border-border'
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
          checked ? 'translate-x-5' : 'translate-x-0'
        )}
      />
    </button>
  );

  return (
    <div className={cn(
      'space-y-8',
      !bare && 'prep-card bg-surface p-6 rounded-lg border border-border',
      className
    )}>
      {/* Include Globs */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileCode className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-text">Include Patterns</h3>
            <InfoTooltip content="Glob patterns for files to include. This acts as an allowlist (e.g. **/*.ts)." />
          </div>
          <div className="relative group">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs gap-1.5 text-text-subtle hover:text-text"
            >
              <Layers className="w-3.5 h-3.5" />
              Presets
            </Button>
            <div className="absolute right-0 top-full mt-1 w-52 py-1 rounded-md border border-border bg-surface-raised shadow-lg z-50 hidden group-hover:block max-h-72 overflow-y-auto">
              {Object.keys(availablePresets).sort().map(preset => {
                const isDetected = detectedPresetNames.includes(preset);
                return (
                  <button
                    key={preset}
                    onClick={() => handleAddPreset(preset)}
                    className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-surface-raised-hover transition-colors flex items-center justify-between gap-2"
                  >
                    <span>{preset}</span>
                    {isDetected && <Check className="w-3 h-3 text-success shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Auto-Detect row */}
        {onDetectStack && (
          <div className="flex items-center gap-2 mb-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAutoDetect}
              disabled={detecting}
              className="h-7 text-xs gap-1.5"
            >
              <Wand2 className={cn("w-3.5 h-3.5", detecting && "animate-spin")} />
              {detecting ? 'Scanning...' : 'Auto-Detect Stack'}
            </Button>
            {detectedMessage && (
              <span className="text-xs text-primary animate-in fade-in slide-in-from-left-1">
                {detectedMessage}
              </span>
            )}
          </div>
        )}

        <p className="text-xs text-text-muted mb-3">
          Only files matching these patterns will be indexed. Use <code className="bg-surface-raised px-1 rounded">**/*</code> to include everything not excluded.
        </p>
        
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
          {/* Always show the top 6, or all if toggled */}
          {(showAllIncludes ? config.include_globs : config.include_globs.slice(0, 6)).map((glob) => (
            <div
              key={glob}
              className="flex items-center justify-between gap-2 py-0.5 group"
            >
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
          
          {/* Toggle Drawer */}
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
            <div className="text-xs text-text-subtle italic py-1">
              No patterns defined
            </div>
          )}
        </div>
      </section>

      {/* Exclude Globs */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileX className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-text">Exclude Patterns</h3>
            <InfoTooltip content="Glob patterns for files to completely ignore." />
          </div>
        </div>
        
        {/* Gitignore Toggle */}
        <div className="flex items-center gap-2 mb-3">
          <Toggle
            checked={config.use_gitignore}
            onChange={(checked) => onChange({ ...config, use_gitignore: checked })}
          />
          <span className="text-sm text-text">Exclude .gitignore files</span>
        </div>

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
            <div
              key={glob}
              className="flex items-center justify-between gap-2 py-0.5 group"
            >
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
            <div className="text-xs text-text-subtle italic py-1">
              No exclude patterns defined
            </div>
          )}
        </div>
      </section>

      <div className="h-px bg-border my-6" />

      {/* Indexing Engine Strategy */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Cpu className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-text">Indexing Engine</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Live Updates (Auto-Rebuild) */}
          <div className="p-3 rounded-md border border-border bg-surface-raised space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-text-subtle" />
                <span className="text-sm font-medium text-text">Live Updates</span>
              </div>
              <Toggle
                checked={config.auto_rebuild.enabled}
                onChange={(checked) =>
                  onChange({
                    ...config,
                    auto_rebuild: { ...config.auto_rebuild, enabled: checked },
                  })
                }
              />
            </div>
            <p className="text-xs text-text-muted leading-relaxed">
              Automatically rebuilds the index when files change. 
              <span className="opacity-70"> Recommended for most users.</span>
            </p>
            
            {config.auto_rebuild.enabled && (
              <div className="pt-2 border-t border-border/50">
                <div className="flex items-center justify-between gap-2">
                  <label className="text-xs text-text-subtle">Debounce (ms)</label>
                  <input
                    type="number"
                    value={config.auto_rebuild.debounce_ms || 5000}
                    onChange={(e) =>
                      onChange({
                        ...config,
                        auto_rebuild: { ...config.auto_rebuild, debounce_ms: parseInt(e.target.value) || 5000 },
                      })
                    }
                    min={1000}
                    max={60000}
                    step={1000}
                    className="w-20 bg-surface border border-border rounded px-2 py-1 text-xs text-right focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Structural Graph (Trace) */}
          <div className="p-3 rounded-md border border-border bg-surface-raised space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-text-subtle" />
                <span className="text-sm font-medium text-text">Structural Graph</span>
              </div>
              <Toggle
                checked={config.trace.enabled}
                onChange={(checked) =>
                  onChange({ ...config, trace: { ...config.trace, enabled: checked } })
                }
              />
            </div>
            <p className="text-xs text-text-muted leading-relaxed">
              Enables advanced code navigation (references, definitions).
              <span className="opacity-70"> Disabling this reduces memory usage but limits context quality.</span>
            </p>
          </div>
        </div>

        {/* Limits */}
        <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <label className="text-xs font-medium text-text-subtle">Max File Size (Index)</label>
              <InfoTooltip content="Files larger than this (in bytes) will be summarized rather than fully indexed." />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={config.max_file_bytes}
                onChange={(e) => onChange({ ...config, max_file_bytes: parseInt(e.target.value) || 0 })}
                min={1000}
                max={10000000}
                step={10000}
                className="flex-1 bg-surface-raised border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <span className="text-[10px] text-text-muted w-12">
                {(config.max_file_bytes / 1000).toFixed(0)} KB
              </span>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <label className="text-xs font-medium text-text-subtle">Hard Limit (Ignore)</label>
              <InfoTooltip content="Files larger than this are completely ignored to prevent crashes." />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={config.hard_limit_bytes || 100000000}
                onChange={(e) => onChange({ ...config, hard_limit_bytes: parseInt(e.target.value) || 0 })}
                min={100000}
                max={1000000000}
                step={1000000}
                className="flex-1 bg-surface-raised border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <span className="text-[10px] text-text-muted w-12">
                {((config.hard_limit_bytes || 100000000) / 1000000).toFixed(0)} MB
              </span>
            </div>
          </div>
        </div>
      </section>

      <div className="h-px bg-border my-6" />

      {/* Data Storage Info */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Database className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-text">Data Storage</h3>
          <InfoTooltip content="Location of the generated Search Index and Code Graph." />
        </div>
        <div className="rounded-md bg-surface-raised border border-border p-3 text-sm flex items-start gap-3">
          <Database className="w-4 h-4 text-text-muted mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="font-medium text-text">
              {mode === 'embedded' ? 'Embedded Mode' : 'Standalone Mode'}
            </p>
            <p className="text-text-muted text-xs leading-relaxed">
              {mode === 'embedded' 
                ? 'Index is stored inside the project folder at .runprep/ (committed to git if not ignored).'
                : 'Index is stored in the SourcePrep application data directory, separate from your source code.'}
            </p>
            {path && (
              <div className="flex items-center gap-1.5 mt-2 text-xs text-text-subtle font-mono bg-surface px-2 py-1 rounded border border-border/50 break-all">
                <FolderOpen className="w-3 h-3 shrink-0" />
                {mode === 'embedded' ? `${path}/.prep` : 'Managed by SourcePrep'}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Save Button */}
      {isDirty && (
        <div className="pt-6 border-t border-border sticky bottom-0 bg-surface -mb-6 pb-6">
          <Button 
            onClick={onSave}
            className="w-full shadow-sm"
            icon={Save}
          >
            Save Changes
          </Button>
        </div>
      )}
    </div>
  );
}

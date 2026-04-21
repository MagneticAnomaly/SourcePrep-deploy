import { useState } from 'react';
import { cn } from '../../lib/utils';
import type { ProjectMode } from '../../types';
import { FolderPlus, X, Folder, Layout, HardDrive, Info, ChevronDown, ChevronUp, Zap, Check } from 'lucide-react';
import { Button } from '../primitives/Button';
import { PathInput } from '../primitives/PathInput';

export interface AddProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (path: string, name: string, mode: ProjectMode, indexPath?: string) => void;
  className?: string;
  /** When true, replace the form with an upgrade prompt */
  limitReached?: boolean;
  /** Current tier label shown in the upgrade prompt */
  currentTierLabel?: string;
  /** Max projects for current tier */
  currentLimit?: number;
  /** Called when user clicks the upgrade CTA */
  onUpgrade?: () => void;
}

const INDEX_LOCATION_INFO: Record<ProjectMode, { best: string; detail: string }> = {
  standalone: {
    best: 'Best for portability',
    detail: 'Index lives in the app data directory (~/.runprep/). Move or delete the repo without losing your index. Ideal if the repo is on network or external storage.',
  },
  embedded: {
    best: 'Best when boot disk is faster',
    detail: 'Index lives inside the repo at .runprep/. Co-located with your code for zero-config. Best when your boot SSD is faster than the repo\'s storage device.',
  },
  custom: {
    best: 'Best for performance',
    detail: 'Place the index on any path — ideal for a fast NVMe scratch disk, Optane drive, or RAM disk. Maximum I/O throughput for large codebases.',
  },
};

export function AddProjectModal({
  isOpen,
  onClose,
  onAdd,
  className,
  limitReached = false,
  currentTierLabel = 'Free',
  currentLimit = 1,
  onUpgrade,
}: AddProjectModalProps) {
  const [path, setPath] = useState('');
  const [name, setName] = useState('');
  const [mode, setMode] = useState<ProjectMode>('standalone');
  const [customIndexPath, setCustomIndexPath] = useState('');
  const [infoOpen, setInfoOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (path.trim()) {
      console.log('[AddProjectModal] Submitting:', { path, name, mode, customIndexPath });
      setIsSubmitting(true);
      setError(null);
      try {
        const indexPath = mode === 'custom' && customIndexPath.trim() ? customIndexPath.trim() : undefined;
        await onAdd(path.trim(), name.trim() || path.split('/').pop() || 'project', mode, indexPath);
        console.log('[AddProjectModal] Success');
        // Parent closes modal on success
      } catch (err) {
        console.error("[AddProjectModal] Failed to add project:", err);
        // Show detailed error if available
        let msg = err instanceof Error ? err.message : 'Failed to add project';
        if (typeof err === 'object' && err !== null && 'details' in err) {
           msg += ` (${JSON.stringify((err as any).details)})`;
        }
        setError(msg);
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const handleClose = () => {
    setPath('');
    setName('');
    setMode('standalone');
    setCustomIndexPath('');
    setError(null);
    onClose();
  };

  if (!isOpen) return null;

  const modes: { key: ProjectMode; label: string; icon: typeof Folder; desc: string }[] = [
    { key: 'standalone', label: 'Standalone', icon: Folder,    desc: 'App data directory' },
    { key: 'embedded',   label: 'Embedded',   icon: Layout,    desc: '.runprep/ in repo' },
    { key: 'custom',     label: 'Custom',     icon: HardDrive, desc: 'Choose a path' },
  ];

  return (
    <div className={cn('fixed inset-0 z-50 flex items-center justify-center', className)}>
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative z-10 w-full max-w-md rounded-lg border border-border bg-surface shadow-xl animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-text flex items-center gap-2">
            <FolderPlus className="w-5 h-5 text-primary" />
            Add Project
          </h2>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>
        
        {limitReached ? (
          <div className="p-6 flex flex-col items-center text-center">
            <div className="relative mb-6 mt-2">
              <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full" />
              <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-b from-surface to-surface-raised border border-border shadow-lg">
                <Zap className="w-8 h-8 text-primary" />
              </div>
            </div>
            
            <h3 className="text-xl font-bold text-text mb-2">
              Unlock Unlimited Projects
            </h3>
            
            <p className="text-sm text-text-muted mb-6 max-w-[320px]">
              Your {currentTierLabel} plan {currentLimit === 1 ? 'only supports a single project' : `supports up to ${currentLimit} projects`}. Upgrade to Pro for unlimited workspaces and advanced features.
            </p>

            <div className="w-full rounded-xl border border-primary/20 bg-primary-muted/5 p-4 text-left space-y-3 mb-8">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 border border-primary/20">
                  <Check className="w-3.5 h-3.5 text-primary" strokeWidth={3} />
                </div>
                <span className="text-sm font-medium text-text">Unlimited active projects</span>
              </div>
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 border border-primary/20">
                  <Check className="w-3.5 h-3.5 text-primary" strokeWidth={3} />
                </div>
                <span className="text-sm font-medium text-text">Live Sync file watcher</span>
              </div>
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 border border-primary/20">
                  <Check className="w-3.5 h-3.5 text-primary" strokeWidth={3} />
                </div>
                <span className="text-sm font-medium text-text">Continuous Deepening</span>
              </div>
            </div>

            <div className="flex gap-3 w-full">
              <Button variant="outline" onClick={onClose} className="flex-1">
                Maybe Later
              </Button>
              {onUpgrade && (
                <Button onClick={() => { onUpgrade(); onClose(); }} className="flex-1 gap-1.5 shadow-primary/25 shadow-lg hover:shadow-primary/40 transition-shadow">
                  <Zap className="w-4 h-4" />
                  Upgrade to Pro
                </Button>
              )}
            </div>
          </div>
        ) : (
        <>
        <div className="p-6 space-y-5">
          {/* Path input */}
          <PathInput
            label="Project Path"
            value={path}
            onChange={setPath}
            placeholder="/path/to/your/project"
            hint="Type or paste the absolute path to the project root directory"
            directory
          />
          
          {/* Name input */}
          <div>
            <label className="block text-sm font-medium text-text-muted mb-1.5">Display Name (optional)</label>
            <input
              type="text"
              placeholder="my-project"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
            />
          </div>
          
          {/* Index Location selector */}
          <div>
            <label className="block text-sm font-medium text-text-muted mb-2">Index Location</label>
            <div className="grid grid-cols-3 gap-2">
              {modes.map(({ key, label, icon: Icon, desc }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setMode(key)}
                  className={cn(
                    'flex flex-col items-center gap-1.5 p-3 rounded-lg border text-sm transition-all',
                    mode === key
                      ? 'border-primary bg-primary-muted/10 text-primary'
                      : 'border-border bg-surface hover:bg-surface-raised text-text-muted hover:text-text'
                  )}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium text-xs">{label}</span>
                  <span className="text-[10px] opacity-80 text-center leading-tight">{desc}</span>
                </button>
              ))}
            </div>

            {/* Custom path input — revealed when custom is selected */}
            {mode === 'custom' && (
              <div className="mt-3">
                <PathInput
                  value={customIndexPath}
                  onChange={setCustomIndexPath}
                  placeholder="/fast-drive/prep-indexes"
                  hint="Path where the index database will be stored"
                  directory
                />
              </div>
            )}

            {/* Error display */}
            {error && (
              <div className="mt-4 p-3 rounded-md bg-error-muted/10 border border-error/20 text-error text-sm flex items-start gap-2">
                <Info className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Info drawer */}
            <button
              type="button"
              onClick={() => setInfoOpen(!infoOpen)}
              className="mt-2 flex items-center gap-1 text-xs text-text-subtle hover:text-text-muted transition-colors"
            >
              <Info className="w-3 h-3" />
              <span>Which should I choose?</span>
              {infoOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {infoOpen && (
              <div className="mt-2 rounded-md border border-border bg-surface-raised/50 p-3 space-y-2 text-xs animate-in fade-in slide-in-from-top-1 duration-150">
                {modes.map(({ key, label }) => (
                  <div key={key} className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className={cn(
                        'font-semibold',
                        mode === key ? 'text-primary' : 'text-text',
                      )}>{label}</span>
                      <span className="text-text-subtle">—</span>
                      <span className="text-text-muted italic">{INDEX_LOCATION_INFO[key].best}</span>
                    </div>
                    <p className="text-text-subtle leading-relaxed pl-0.5">
                      {INDEX_LOCATION_INFO[key].detail}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex justify-end gap-3 p-4 border-t border-border bg-surface-raised/30">
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!path.trim() || (mode === 'custom' && !customIndexPath.trim()) || isSubmitting}
            loading={isSubmitting}
          >
            {isSubmitting ? 'Adding...' : 'Add Project'}
          </Button>
        </div>
        </>
        )}
      </div>
    </div>
  );
}

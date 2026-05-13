import { useCallback, useEffect, useState } from 'react';
import { Copy, X, AlertTriangle } from 'lucide-react';

import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';

export interface GitignoreGap {
  rel_path: string;
  size_bytes: number;
  file_count: number;
  reason: string;
}

export interface GitignoreHygieneModalProps {
  open: boolean;
  gaps: GitignoreGap[];
  onCancel: () => void;
  onContinue: () => void;
  className?: string;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function GitignoreHygieneModal({
  open,
  gaps,
  onCancel,
  onContinue,
  className,
}: GitignoreHygieneModalProps) {
  const [copied, setCopied] = useState(false);
  const snippet = gaps.map((g) => `${g.rel_path}/`).join('\n');

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCancel();
      }
    },
    [onCancel],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API failed (older browsers / non-https) — silent no-op.
    }
  };

  if (!open) return null;

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm',
        className,
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="gitignore-hygiene-title"
    >
      <div className="mx-4 w-full max-w-lg rounded-lg border border-amber-500/40 bg-surface p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 shrink-0 rounded-full bg-amber-500/10 p-2">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
            </div>
            <div>
              <h3 id="gitignore-hygiene-title" className="text-sm font-semibold text-text">
                Your .gitignore looks incomplete
              </h3>
              <p className="mt-1 text-xs text-text-subtle leading-relaxed">
                SourcePrep detected directories at your project root that are typically
                gitignored but aren&apos;t in your{' '}
                <code className="font-mono text-[11px]">.gitignore</code>.
                Adding them helps every tool that reads your repo — not just SourcePrep.
              </p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="rounded-md p-1 text-text-subtle hover:bg-surface-raised hover:text-text transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4">
          <p className="text-xs text-text-subtle mb-2">Found (not in .gitignore):</p>
          <ul className="space-y-1 mb-4">
            {gaps.map((g) => (
              <li key={g.rel_path} className="font-mono text-xs flex items-center gap-2">
                <span className="text-text">{g.rel_path}/</span>
                <span className="text-text-subtle">
                  ({formatBytes(g.size_bytes)}, {g.file_count.toLocaleString()} files)
                </span>
              </li>
            ))}
          </ul>

          <p className="text-xs text-text-subtle mb-2">Recommended additions:</p>
          <div className="flex items-stretch gap-2">
            <pre className="flex-1 bg-surface-raised border border-border rounded-md p-3 text-xs font-mono overflow-x-auto">
              {snippet}
            </pre>
            <Button variant="outline" size="sm" onClick={handleCopy} className="shrink-0">
              <Copy className="h-3.5 w-3.5 mr-1" />
              {copied ? 'Copied!' : 'Copy'}
            </Button>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel Initialize
          </Button>
          <Button variant="default" size="sm" onClick={onContinue}>
            Continue Anyway
          </Button>
        </div>
      </div>
    </div>
  );
}

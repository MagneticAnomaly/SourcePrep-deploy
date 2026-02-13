import { useState, useEffect } from 'react';
import { Pin, PinOff, FileText } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { CopyButton } from '../context/CopyButton';
import { CodeViewer } from './CodeViewer';

export interface FilePreviewPaneProps {
  path: string | null;
  content: string | null;
  loading?: boolean;
  error?: string | null;
  isPinned?: boolean;
  onPin?: (path: string) => void;
  onUnpin?: (path: string) => void;
  className?: string;
}

export function FilePreviewPane({
  path,
  content,
  loading = false,
  error = null,
  isPinned = false,
  onPin,
  onUnpin,
  className,
}: FilePreviewPaneProps) {
  // Local optimistic state so the button updates immediately on click,
  // then syncs back to the parent `isPinned` prop on subsequent renders.
  const [localPinOverride, setLocalPinOverride] = useState<boolean | null>(null);

  // Reset local override when parent prop catches up or path changes
  useEffect(() => { setLocalPinOverride(null); }, [isPinned, path]);

  const effectivePinned = localPinOverride ?? isPinned;

  if (!path) {
    return (
      <div className={cn('flex items-center justify-center h-full text-text-muted text-sm', className)}>
        <div className="text-center space-y-2">
          <FileText className="w-8 h-8 mx-auto opacity-40" />
          <p>Select a file to preview</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header with path + actions */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border bg-surface shrink-0">
        <span className="text-xs font-mono text-text truncate flex-1">{path}</span>
        <div className="flex items-center gap-1 shrink-0">
          {content && <CopyButton text={content} label="Copy" />}
          <Button
            variant={effectivePinned ? 'default' : 'outline'}
            size="sm"
            onClick={() => {
              if (effectivePinned) {
                setLocalPinOverride(false);
                onUnpin?.(path);
              } else {
                setLocalPinOverride(true);
                onPin?.(path);
              }
            }}
            title={effectivePinned ? 'Remove from dashboard' : 'Pin file to dashboard'}
          >
            {effectivePinned ? (
              <PinOff className="w-3.5 h-3.5 mr-1.5" />
            ) : (
              <Pin className="w-3.5 h-3.5 mr-1.5" />
            )}
            {effectivePinned ? 'Remove from Dashboard' : 'Pin to Dashboard'}
          </Button>
        </div>
      </div>

      {/* File content */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
          Loading…
        </div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-error text-sm p-4">
          {error}
        </div>
      ) : (
        <CodeViewer 
          content={content ?? ''} 
          path={path}
          className="h-full border-0 rounded-none"
        />
      )}
    </div>
  );
}

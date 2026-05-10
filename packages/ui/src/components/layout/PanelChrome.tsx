import { ChevronDown, ChevronUp, Maximize2, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface PanelChromeProps {
  title: string;
  description?: string;
  docsUrl?: string;
  icon?: LucideIcon;
  collapsed?: boolean;
  onCollapse?: () => void;
  onDetails?: () => void;
  closeable?: boolean;
  onClose?: () => void;
  fillHeight?: boolean;
  children: ReactNode;
  className?: string;
}

export function PanelChrome({
  title,
  description,
  docsUrl,
  icon: Icon,
  collapsed = false,
  onCollapse,
  onDetails,
  closeable = true,
  onClose,
  fillHeight = false,
  children,
  className,
}: PanelChromeProps) {
  return (
    <div
      className={cn(
        'prep-panel group relative w-full bg-surface border border-border shadow-sm rounded-lg overflow-hidden flex flex-col',
        fillHeight && 'h-full',
        className
      )}
    >
      {/* Panel Header — the entire bar is the drag handle. Action buttons
          inside `.panel-actions` are excluded via the grid's draggableCancel
          selector so clicking them doesn't initiate a drag. */}
      <div
        className={cn(
          "prep-panel-header drag-handle cursor-grab active:cursor-grabbing flex items-center justify-between px-3 py-2 bg-surface border-b border-border min-h-[40px]",
          collapsed && "border-b-0"
        )}
        aria-label={`Drag ${title}`}
      >
        <div className="flex items-center gap-2 overflow-hidden select-none">
          {Icon && <Icon className="w-4 h-4 text-text-muted flex-shrink-0" />}
          <span className="font-medium text-sm text-text truncate">{title}</span>
          {description && <InfoTooltip content={description} href={docsUrl} className="ml-1 flex-shrink-0" />}
        </div>

        <div className="panel-actions flex items-center gap-1 cursor-default">
          {onDetails && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onDetails}
              className="text-text-muted hover:text-text"
              aria-label="Details"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </Button>
          )}
          {onCollapse && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onCollapse}
              className="text-text-muted hover:text-text"
              aria-label={collapsed ? 'Expand panel' : 'Collapse panel'}
            >
              {collapsed ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronUp className="w-3.5 h-3.5" />
              )}
            </Button>
          )}
          {closeable && onClose && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onClose}
              className="text-text-muted hover:text-error hover:bg-error-muted/20"
              aria-label="Close panel"
            >
              <X className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Panel Content */}
      {!collapsed && (
        <div
          className={cn(
            'prep-panel-content flex-1 min-h-0 bg-surface',
            fillHeight ? 'h-full overflow-hidden' : 'overflow-visible'
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}

import type { ReactNode } from 'react';
import { useState, useCallback, useEffect, useRef } from 'react';
import { cn } from '../../lib/utils';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '../primitives/Button';

export interface SidebarProps {
  children: ReactNode;
  footer?: ReactNode;
  collapsed?: boolean;
  onCollapseToggle?: () => void;
  className?: string;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  onWidthChange?: (width: number) => void;
}

/**
 * Sidebar - Main navigation sidebar container
 * 
 * Provides structure for:
 * - Project list
 * - Add project action
 * - Collapse/expand toggle
 * - Resizable width via drag handle
 */
export function Sidebar({
  children,
  footer,
  collapsed = false,
  onCollapseToggle,
  className,
  defaultWidth = 280,
  minWidth = 240,
  maxWidth = 480,
  onWidthChange,
}: SidebarProps) {
  const storageKey = 'prep_sidebar_width';
  const [width, setWidth] = useState(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem(storageKey) : null;
    return saved ? parseInt(saved, 10) : defaultWidth;
  });
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (sidebarRef.current) {
        const newWidth = Math.max(minWidth, Math.min(maxWidth, e.clientX));
        setWidth(newWidth);
        onWidthChange?.(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      // Persist width on resize end
      if (typeof window !== 'undefined') {
        localStorage.setItem(storageKey, width.toString());
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, minWidth, maxWidth, onWidthChange, width]);

  return (
    <>
      <aside
        ref={sidebarRef}
        className={cn(
          'flex flex-col border-r border-border h-full bg-surface relative',
          collapsed ? 'w-16' : 'transition-[width] duration-0',
          className
        )}
        style={collapsed ? undefined : { width }}
      >
        <div className={cn(
          "flex items-center p-4 border-b border-border h-16",
          collapsed ? "justify-center" : "justify-between"
        )}>
          {!collapsed && (
            <span className="font-semibold text-lg flex items-center text-text">
              <img src="/prep-logo.png" alt="SourcePrep" className="w-12 h-12 rounded" />
              SourcePrep
            </span>
          )}
          {onCollapseToggle && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onCollapseToggle}
              className="text-text-muted hover:text-text"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
            </Button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {children}
        </div>

        {/* Footer (AI Gateway, etc.) */}
        {footer && (
          <div className="flex-shrink-0 border-t border-border">
            {footer}
          </div>
        )}

        {/* Resize handle */}
        {!collapsed && (
          <div
            className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary transition-colors z-10"
            onMouseDown={handleMouseDown}
            title="Drag to resize"
          />
        )}
      </aside>

      {/* Global cursor style during resize */}
      {isResizing && (
        <style>{`
          * { cursor: col-resize !important; user-select: none !important; }
        `}</style>
      )}
    </>
  );
}

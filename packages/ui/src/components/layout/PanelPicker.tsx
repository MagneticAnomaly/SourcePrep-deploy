import { useState, useRef, useEffect, useCallback } from 'react';
import { Check, ClipboardCopy, ClipboardPaste, Columns, Plus, RotateCcw } from 'lucide-react';
import type { DashboardLayout, PanelDefinition } from '../../types/layout';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';

export interface PanelPickerProps {
  layout: DashboardLayout;
  panelDefinitions: PanelDefinition[];
  onTogglePanel: (panelId: string) => void;
  onResetLayout: () => void;
  onRefitLayout?: () => void;
  onCopyLayout?: () => void;
  onPasteLayout?: () => void;
  className?: string;
}

export function PanelPicker({
  layout,
  panelDefinitions,
  onTogglePanel,
  onResetLayout,
  onRefitLayout,
  onCopyLayout,
  onPasteLayout,
  className,
}: PanelPickerProps) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});

  const visibleIds = new Set(
    layout.panels.filter((p) => p.visible).map((p) => p.id)
  );

  // Calculate fixed position from button's bounding rect
  const updatePosition = useCallback(() => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const dropdownHeight = 400; // approximate max height
    const openUp = spaceBelow < dropdownHeight && spaceAbove > spaceBelow;

    setDropdownStyle({
      position: 'fixed' as const,
      left: Math.max(8, rect.left),
      width: 256,
      zIndex: 50,
      ...(openUp
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
    });
  }, []);

  useEffect(() => {
    if (open) updatePosition();
  }, [open, updatePosition]);

  const handleToggle = (panelId: string) => {
    onTogglePanel(panelId);
  };

  const handleReset = () => {
    if (window.confirm('Reset layout to defaults? This will restore all panels to their original positions.')) {
      onResetLayout();
      setOpen(false);
    }
  };

  return (
    <div ref={buttonRef} className={cn('relative', className)}>
      <Button
        onClick={() => setOpen(!open)}
        variant="outline"
        size="sm"
        aria-expanded={open}
        aria-haspopup="true"
        icon={Plus}
        className="flex-1 bg-surface hover:bg-surface-raised"
      >
        Panels
      </Button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />

          {/* Dropdown — fixed position to escape overflow parents */}
          <div
            style={dropdownStyle}
            className="bg-surface border border-border rounded-lg shadow-lg overflow-hidden">
            <div className="p-2 border-b border-border">
              <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                Toggle Panels
              </span>
            </div>

            <div className="max-h-80 overflow-y-auto">
              {panelDefinitions.map((def) => {
                const isVisible = visibleIds.has(def.id);
                const Icon = def.icon;

                return (
                  <Button
                    key={def.id}
                    onClick={() => handleToggle(def.id)}
                    variant="ghost"
                    title={def.description}
                    className={cn(
                      'w-full justify-start rounded-none h-auto py-2 px-3',
                      isVisible ? 'text-text' : 'text-text-muted'
                    )}
                  >
                    <Icon className="w-4 h-4 mr-3 flex-shrink-0" />
                    <span className="flex-1 text-left truncate text-sm">{def.title}</span>
                    {isVisible && (
                      <Check className="w-4 h-4 text-success flex-shrink-0" />
                    )}
                  </Button>
                );
              })}
            </div>

            <div className="p-2 border-t border-border flex flex-col gap-1">
              {onRefitLayout && (
                <Button
                  onClick={() => { onRefitLayout(); setOpen(false); }}
                  variant="ghost"
                  size="sm"
                  className="w-full justify-center text-text-muted hover:text-text hover:bg-muted"
                  icon={Columns}
                >
                  Refit Layout
                </Button>
              )}
              <Button
                onClick={handleReset}
                variant="ghost"
                size="sm"
                className="w-full justify-center text-text-muted hover:text-text hover:bg-muted"
                icon={RotateCcw}
              >
                Reset Layout
              </Button>
              {onCopyLayout && (
                <Button
                  onClick={() => { onCopyLayout(); setOpen(false); }}
                  variant="ghost"
                  size="sm"
                  className="w-full justify-center text-text-muted hover:text-text hover:bg-muted"
                  icon={ClipboardCopy}
                >
                  Copy Layout
                </Button>
              )}
              {onPasteLayout && (
                <Button
                  onClick={() => { onPasteLayout(); setOpen(false); }}
                  variant="ghost"
                  size="sm"
                  className="w-full justify-center text-text-muted hover:text-text hover:bg-muted"
                  icon={ClipboardPaste}
                >
                  Paste Layout
                </Button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}


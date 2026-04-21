import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

interface AutoHeightPanelProps {
  children: ReactNode;
  panelId: string;
  rowHeight: number;
  marginY: number;
  minHeight?: number;
  onHeightChange: (panelId: string, gridUnits: number) => void;
  className?: string;
}

/**
 * Wrapper component that measures its content and reports the required
 * grid height (in grid units) to the parent.
 * 
 * Grid height formula (react-grid-layout):
 *   pixelHeight = h * rowHeight + (h - 1) * marginY
 * 
 * Solving for h:
 *   h = ceil((pixelHeight + marginY) / (rowHeight + marginY))
 */
export function AutoHeightPanel({
  children,
  panelId,
  rowHeight,
  marginY,
  minHeight = 1,
  onHeightChange,
  className,
}: AutoHeightPanelProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const lastReportedHeight = useRef<number>(0);

  useEffect(() => {
    if (!contentRef.current) return;

    const el = contentRef.current;

    const calculateGridHeight = (contentHeight: number) => {
      // Convert pixel height to grid units, rounding up
      const h = Math.ceil((contentHeight + marginY) / (rowHeight + marginY));
      return Math.max(h, minHeight);
    };

    const measureAndReport = () => {
      const headerEl = el.querySelector('.prep-panel-header') as HTMLElement | null;
      const bodyEl = el.querySelector('.prep-panel-body') as HTMLElement | null;
      const contentHeight =
        headerEl && bodyEl
          ? headerEl.offsetHeight + bodyEl.scrollHeight
          : el.scrollHeight;
      const newGridHeight = calculateGridHeight(contentHeight);

      if (newGridHeight !== lastReportedHeight.current) {
        lastReportedHeight.current = newGridHeight;
        onHeightChange(panelId, newGridHeight);
      }
    };

    requestAnimationFrame(measureAndReport);

    const observer = new ResizeObserver((entries) => {
      if (entries.length > 0) measureAndReport();
    });

    const mutationObserver = new MutationObserver(() => {
      measureAndReport();
    });

    observer.observe(el);
    mutationObserver.observe(el, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
    });

    return () => {
      observer.disconnect();
      mutationObserver.disconnect();
    };
  }, [panelId, rowHeight, marginY, minHeight, onHeightChange]);

  return (
    <div
      ref={contentRef}
      className={className ? `h-full ${className}` : 'h-full'}
    >
      {children}
    </div>
  );
}

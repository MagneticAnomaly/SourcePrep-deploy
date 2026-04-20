import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface SectionProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

export function Section({ title, children, className }: SectionProps) {
  return (
    <section className={cn('space-y-0', className)}>
      {title && (
        <h3 className="text-xs uppercase tracking-wide text-text-muted mb-2">
          {title}
        </h3>
      )}
      <div className="border border-border-subtle rounded-lg px-6 bg-surface-subtle/30">
        {children}
      </div>
    </section>
  );
}

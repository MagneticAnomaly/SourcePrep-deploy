import React from 'react';
import { cn } from '../../lib/utils';

export interface AdminSectionProps {
  title: string;
  children: React.ReactNode;
  enforcementMode?: 'suggest' | 'enforce';
  className?: string;
}

/**
 * Orange-bordered section wrapper for admin-only UI elements.
 *
 * Visually distinguishes IT-managed settings from user settings with:
 * - Orange left border (border-l-4 border-l-amber-500)
 * - "ADMIN" badge
 * - Enforcement mode indicator (suggest/enforce)
 */
export function AdminSection({ title, children, enforcementMode, className }: AdminSectionProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-amber-500/30 border-l-4 border-l-amber-500 bg-amber-500/5 p-4 space-y-3',
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-400">
            {enforcementMode === 'enforce' ? (
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            ) : (
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4" />
                <path d="M12 8h.01" />
              </svg>
            )}
            Admin
          </span>
          <h4 className="text-sm font-semibold text-text">{title}</h4>
        </div>
        {enforcementMode && (
          <span className={cn(
            'text-[10px] font-medium px-2 py-0.5 rounded-full',
            enforcementMode === 'enforce'
              ? 'bg-red-500/10 text-red-400'
              : 'bg-amber-500/10 text-amber-400',
          )}>
            {enforcementMode === 'enforce' ? 'Enforced by IT' : 'Suggested by IT'}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

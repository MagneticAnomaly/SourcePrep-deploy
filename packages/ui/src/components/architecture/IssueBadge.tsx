import { memo } from 'react';

export interface IssueBadgeProps {
  issueCount: number;
  acrCount: number;
  maxPriority: 'P0' | 'P1' | 'P2' | 'P3' | null;
}

function IssueBadgeInner({ issueCount, acrCount, maxPriority }: IssueBadgeProps) {
  if (issueCount === 0 && acrCount === 0) return null;

  return (
    <div className="absolute -top-1 -right-1 flex items-center gap-0.5 z-10">
      {issueCount > 0 && (
        <span
          className={`
            text-[9px] font-bold leading-none rounded-full min-w-[16px] h-[16px]
            flex items-center justify-center px-1
            ${maxPriority === 'P0' || maxPriority === 'P1'
              ? 'bg-red-500 text-white animate-pulse'
              : 'bg-amber-500 text-zinc-900'}
          `}
        >
          {issueCount}
        </span>
      )}
      {acrCount > 0 && (
        <span className="text-[10px] leading-none text-amber-400">{'\u26a0\ufe0f'}</span>
      )}
    </div>
  );
}

export const IssueBadge = memo(IssueBadgeInner);

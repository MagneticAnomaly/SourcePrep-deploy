"use client";

import type { ReactNode } from 'react';
import type { TerminalTheme } from './cli-types';

export interface TerminalFrameProps {
  children: ReactNode;
  title?: string;
  theme?: TerminalTheme;
  className?: string;
  contentClassName?: string;
}

export function TerminalFrame({
  children,
  title = 'Terminal',
  theme = 'dark',
  className = '',
  contentClassName = 'min-h-[300px] max-h-[450px]',
}: TerminalFrameProps) {
  const themeStyles: Record<TerminalTheme, { bg: string; border: string; titleBg: string }> = {
    dark: {
      bg: 'bg-[#0d1117]',
      border: 'border-[#30363d]',
      titleBg: 'bg-[#161b22]',
    },
    claude: {
      bg: 'bg-[#1a1a2e]',
      border: 'border-[#2a2a4a]',
      titleBg: 'bg-[#16162a]',
    },
    minimal: {
      bg: 'bg-[#000000]',
      border: 'border-[#333333]',
      titleBg: 'bg-[#111111]',
    },
  };

  const t = themeStyles[theme];

  return (
    <div className={`${t.bg} ${t.border} border rounded-xl overflow-hidden shadow-2xl shadow-black/40 ${className}`}>
      <div className={`${t.titleBg} px-4 py-2.5 flex items-center gap-3 border-b ${t.border}`}>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
          <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
          <div className="w-3 h-3 rounded-full bg-[#28c840]" />
        </div>
        <span className="text-xs text-[#8b949e] font-mono flex-1 text-center select-none">{title}</span>
        <div className="w-[42px]" />
      </div>
      <div className={`p-4 font-mono text-sm leading-relaxed overflow-y-auto ${contentClassName}`}>
        {children}
      </div>
    </div>
  );
}

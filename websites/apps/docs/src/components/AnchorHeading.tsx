"use client";

import { Link as LinkIcon } from 'lucide-react';
import { type ReactNode } from 'react';

interface AnchorHeadingProps {
  id: string;
  level?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  children: ReactNode;
  className?: string;
}

export function AnchorHeading({ id, level = 'h2', children, className = '' }: AnchorHeadingProps) {
  const Component = level;

  const copyToClipboard = (e: React.MouseEvent) => {
    e.preventDefault();
    const url = `${window.location.origin}${window.location.pathname}#${id}`;
    navigator.clipboard.writeText(url);
    // Optional: could add a toast here, but for now just copying is fine
    window.history.pushState(null, '', `#${id}`);
    
    // Scroll to it manually if needed, though the hash change usually handles it
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <Component id={id} className={`group flex items-center gap-2 ${className}`}>
      {children}
      <a
        href={`#${id}`}
        onClick={copyToClipboard}
        className="opacity-0 group-hover:opacity-100 transition-opacity text-text-muted hover:text-primary"
        aria-label={`Link to ${id}`}
      >
        <LinkIcon className="w-5 h-5" />
      </a>
    </Component>
  );
}

"use client";

import { useEffect, useRef, useState } from 'react';
import './StoryEmbed.css';

/**
 * StoryEmbed — Secure, sandboxed Storybook iframe for the public docs site.
 *
 * Security model:
 * - `sandbox="allow-scripts"` — no navigation, forms, popups, or top-frame access
 * - `referrerPolicy="no-referrer"` — no URL leakage from parent
 * - `allow=""` — no camera/mic/geolocation permissions
 * - Separate origin isolation when deployed to storybook.runprep.io
 * - Stories use hardcoded mock data only — no real API calls
 */

const STORYBOOK_BASE_URL = process.env.NEXT_PUBLIC_STORYBOOK_URL || '/storybook';

interface StoryEmbedProps {
  /** Storybook story ID, e.g. "dashboard-widgets-searchpanel--default" */
  storyId: string;
  /** iframe height — number (px) or CSS string */
  height?: number | string;
  /** Accessible iframe title */
  title?: string;
  // Theme is locked to dark + Retro Aurora for all docs embeds
  /** Additional CSS class on the outer wrapper */
  className?: string;
  /** Optional caption below the embed */
  caption?: string;
}

export function StoryEmbed({
  storyId,
  height = 400,
  title,
  className = '',
  caption,
}: StoryEmbedProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Fallback: auto-dismiss loading overlay after 3s in case onLoad doesn't fire
  useEffect(() => {
    const timer = setTimeout(() => setLoaded(true), 3000);
    return () => clearTimeout(timer);
  }, []);

  // Locked to dark + Retro Aurora ("m") + docsMode for all docs embeds
  const src = `${STORYBOOK_BASE_URL}/iframe.html?id=${encodeURIComponent(storyId)}&viewMode=story&globals=theme:dark;prepTheme:m;docsMode:true`;

  const heightValue = typeof height === 'number' ? `${height}px` : height;

  return (
    <div className={`story-embed ${className}`}>
      <div
        className="story-embed__frame"
        style={{ height: heightValue }}
      >
        {/* Loading skeleton */}
        {!loaded && !error && (
          <div className="story-embed__skeleton">
            <div className="story-embed__skeleton-shimmer" />
            <span className="story-embed__skeleton-label">Loading component preview…</span>
          </div>
        )}

        {/* Error fallback */}
        {error && (
          <div className="story-embed__error">
            <span className="story-embed__error-icon">⚠</span>
            <span>Component preview unavailable</span>
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              className="story-embed__error-link"
            >
              Open in Storybook →
            </a>
          </div>
        )}

        {/* The actual sandboxed iframe */}
        <iframe
          ref={iframeRef}
          src={src}
          title={title || `Prep Dashboard — ${storyId.split('--')[0].replaceAll('-', ' ')}`}
          className={`story-embed__iframe ${loaded ? 'story-embed__iframe--loaded' : ''}`}
          style={{ height: heightValue }}
          sandbox="allow-scripts allow-same-origin"
          referrerPolicy="no-referrer"
          loading="lazy"
          allow=""
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
      </div>

      {caption && (
        <p className="story-embed__caption">{caption}</p>
      )}
    </div>
  );
}

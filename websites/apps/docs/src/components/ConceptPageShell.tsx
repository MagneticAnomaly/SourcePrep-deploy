"use client";

import { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';

export interface ConceptSection {
  id: string;
  label: string;
}

export interface ConceptPageShellProps {
  /** Small uppercase eyebrow above the title (e.g. "How It Works"). */
  subtitle: string;
  /** Concept title (e.g. "Graph Enrichment"). */
  title: string;
  /** One-paragraph summary that lives in the sticky sidebar. */
  description: string;
  /** Anchor-nav entries — order shown in the sticky sidebar. */
  sections: ConceptSection[];
  children: React.ReactNode;
}

/** Referrer-aware back-link: marketing → marketing, docs → docs (default). */
function BackLink() {
  const [target, setTarget] = useState<{ href: string; label: string }>({
    href: '/',
    label: 'Back to Docs',
  });

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const ref = document.referrer;
    if (!ref) return;
    try {
      const url = new URL(ref);
      // Marketing site (sourceprep.io apex, NOT docs.sourceprep.io subdomain)
      if (url.hostname === 'sourceprep.io' || url.hostname === 'www.sourceprep.io') {
        setTarget({ href: 'https://sourceprep.io', label: 'Back to sourceprep.io' });
      } else if (url.hostname === 'localhost' && url.port === '3000') {
        // Local marketing dev server.
        setTarget({ href: 'http://localhost:3000', label: 'Back to sourceprep.io' });
      }
    } catch {
      /* invalid referrer URL — keep default */
    }
  }, []);

  return (
    <a href={target.href} className="text-sm text-text-muted hover:text-primary transition-colors inline-flex items-center gap-2">
      <ArrowLeft className="w-3 h-3" /> {target.label}
    </a>
  );
}

/**
 * Shared shell for docs concept pages. Provides:
 *   - referrer-aware back-link top bar
 *   - sticky left sidebar with subtitle/title/description + anchor nav
 *   - main content area for the page's <section> children
 */
export function ConceptPageShell({
  subtitle,
  title,
  description,
  sections,
  children,
}: ConceptPageShellProps) {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 pb-16 pt-0">

        <div className="pb-6 mb-8 border-b border-border">
          <BackLink />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Sticky section sidebar */}
          <div className="lg:col-span-3">
            <div className="sticky top-20 space-y-8">
              <div>
                <p className="text-xs font-mono font-bold uppercase tracking-widest text-primary mb-3">{subtitle}</p>
                <h1 className="text-3xl font-bold tracking-tight text-text">{title}</h1>
                <p className="mt-3 text-sm text-text-muted leading-relaxed">{description}</p>
              </div>

              {sections.length > 0 && (
                <nav className="space-y-1 border-l border-border-subtle">
                  {sections.map((section) => (
                    <a
                      key={section.id}
                      href={`#${section.id}`}
                      className="block pl-4 py-2 text-sm text-text-muted hover:text-primary hover:border-l-2 hover:border-primary hover:bg-surface transition-all -ml-[1px]"
                    >
                      {section.label}
                    </a>
                  ))}
                </nav>
              )}
            </div>
          </div>

          {/* Main content */}
          <div className="lg:col-span-9 space-y-16">
            {children}
          </div>

        </div>
      </div>
    </main>
  );
}

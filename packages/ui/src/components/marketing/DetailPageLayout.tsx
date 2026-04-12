"use client";

import { ArrowLeft, ArrowRight, ExternalLink } from 'lucide-react';

export interface DetailPageSection {
  id: string;
  label: string;
}

export interface DetailPageLayoutProps {
  title: string;
  subtitle: string;
  description: string;
  badge?: string;
  sections: DetailPageSection[];
  docsUrl: string;
  docsLabel?: string;
  children: React.ReactNode;
}

export function DetailPageLayout({
  title,
  subtitle,
  description,
  badge,
  sections,
  docsUrl,
  docsLabel = 'Read the full guide',
  children,
}: DetailPageLayoutProps) {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-12">

        {/* Top bar */}
        <div className="flex items-center justify-between border-b border-border pb-6 mb-12">
          <a href="/" className="text-sm text-text-muted hover:text-primary transition-colors inline-flex items-center gap-2">
            <ArrowLeft className="w-3 h-3" /> Home
          </a>
          {badge && (
            <span className="font-mono text-xs uppercase tracking-widest text-primary">{badge}</span>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Sidebar */}
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

              <div className="pt-6 border-t border-border-subtle space-y-3">
                <a
                  href={docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm font-medium text-primary hover:underline underline-offset-4"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  {docsLabel}
                </a>
                <a
                  href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request"
                  className="flex items-center gap-2 text-sm font-medium text-text-muted hover:text-text transition-colors"
                >
                  Request Beta Access <ArrowRight className="w-3 h-3" />
                </a>
              </div>
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

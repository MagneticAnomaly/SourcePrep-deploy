"use client";

import { useSearchParams } from 'next/navigation';
import { Suspense, useMemo, useState } from 'react';
import { Button } from '@prep/ui';
import { docsSidebar } from '../../config/docs';
import { FileText, ArrowRight } from 'lucide-react';
import { AnchorHeading } from '../../components/AnchorHeading';

// Flatten the sidebar into searchable items
interface SearchItem {
  title: string;
  href: string;
  category: string;
}

function getSearchItems(): SearchItem[] {
  const items: SearchItem[] = [];
  docsSidebar.forEach(section => {
    section.children?.forEach(child => {
      items.push({
        title: child.title,
        href: child.href,
        category: section.title
      });
    });
  });
  return items;
}

function SearchResults() {
  const searchParams = useSearchParams();
  const query = searchParams.get('q') || '';
  const [searchTerm, setSearchTerm] = useState(query);

  const items = useMemo(() => getSearchItems(), []);
  
  const results = useMemo(() => {
    if (!searchTerm.trim()) return [];
    const lower = searchTerm.toLowerCase();
    return items.filter(item => 
      item.title.toLowerCase().includes(lower) || 
      item.category.toLowerCase().includes(lower) ||
      item.href.toLowerCase().includes(lower)
    );
  }, [searchTerm, items]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-4">Search Results</h1>
        <div className="flex gap-2">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search documentation..."
            className="flex-1 px-4 py-2 rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-primary/50"
            autoFocus
          />
        </div>
      </div>

      <div className="space-y-4">
        {results.length > 0 ? (
          results.map((result) => (
            <a
              key={result.href}
              href={result.href}
              className="block p-4 rounded-lg border border-border bg-surface hover:border-primary transition-colors group"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-text-muted group-hover:text-primary" />
                  <div>
                    <div className="font-medium text-text group-hover:text-primary transition-colors">
                      {result.title}
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">
                      {result.category} &bull; {result.href}
                    </div>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-text-muted opacity-0 group-hover:opacity-100 transition-all -translate-x-2 group-hover:translate-x-0" />
              </div>
            </a>
          ))
        ) : searchTerm ? (
          <div className="text-center py-12 text-text-muted">
            No results found for &quot;{searchTerm}&quot;
          </div>
        ) : (
          <div className="text-center py-12 text-text-muted">
            Enter a search term to find guides and references.
          </div>
        )}
      </div>

      <div className="border-t border-border pt-8 mt-8">
        <AnchorHeading id="browse-by-category" level="h2" className="text-lg font-semibold mb-4">Browse by Category</AnchorHeading>
        <div className="grid sm:grid-cols-2 gap-4">
          {docsSidebar.map((section) => (
            <div key={section.title} className="p-4 rounded-lg bg-surface border border-border">
              <h3 className="font-medium mb-2">{section.title}</h3>
              <ul className="space-y-1 text-sm">
                {section.children?.map(child => (
                  <li key={child.href}>
                    <a href={child.href} className="text-text-muted hover:text-primary hover:underline">
                      {child.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <Suspense fallback={<div>Loading...</div>}>
          <SearchResults />
        </Suspense>
      </div>
    </main>
  );
}

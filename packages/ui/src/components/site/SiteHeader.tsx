"use client";

import { Badge } from '@tremor/react';
import { Box, Menu, Search, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { Button } from '../primitives/Button';

export interface NavLink {
  label: string;
  href: string;
  active?: boolean;
}

export interface SiteHeaderProps {
  productName?: string;
  productBadge?: string;
  logo?: React.ReactNode;
  links: NavLink[];
  actions?: React.ReactNode;
  searchPlaceholder?: string;
  onSearch?: (query: string) => void;
  className?: string;
}

export function SiteHeader({
  productName = 'Prep',
  productBadge,
  logo = <Box className="w-5 h-5" />,
  links,
  actions,
  searchPlaceholder = 'Search docs...',
  onSearch,
  className = '',
}: SiteHeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

  const handleSearch = (query: string) => {
    if (onSearch) {
      onSearch(query);
    } else {
      // Default behavior: Redirect to docs search
      window.location.href = `https://docs.runprep.io?q=${encodeURIComponent(query)}`;
    }
  };

  return (
    <header className={`sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-md ${className}`}>
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        
        {/* Left: Logo & Desktop Nav */}
        <div className="flex items-center gap-8">
          <a href="/" className="flex items-center font-mono font-bold text-lg tracking-tight text-text hover:text-primary transition-colors">
            <span className="text-primary">{logo}</span>
            {productName}
            {productBadge && (
              <Badge size="xs" color="blue" className="ml-1 px-1.5 py-0">
                {productBadge}
              </Badge>
            )}
          </a>

          <nav className="hidden md:flex items-center gap-6">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-colors hover:text-primary ${
                  link.active ? 'text-primary' : 'text-text-muted'
                }`}
              >
                {link.label}
              </a>
            ))}
          </nav>
        </div>

        {/* Right: Actions & Mobile Toggle */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:block relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-subtle" />
            <input
              type="text"
              placeholder={searchPlaceholder}
              className="h-9 w-64 rounded-md border border-border bg-surface-raised pl-9 pr-4 text-sm text-text placeholder:text-text-subtle focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
              onKeyDown={(e) => e.key === 'Enter' && handleSearch(e.currentTarget.value)}
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
              <kbd className="hidden rounded border border-border bg-surface px-1.5 font-mono text-[10px] font-medium text-text-subtle sm:inline-block">
                ⌘K
              </kbd>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-3">
            {actions}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div 
          className="absolute top-full left-0 w-full md:hidden border-b border-border bg-background p-4 space-y-4 shadow-lg overflow-y-auto"
          style={{ maxHeight: 'calc(100vh - 3.5rem)' }}
        >
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-subtle" />
            <input
              type="text"
              placeholder={searchPlaceholder}
              className="h-10 w-full rounded-md border border-border bg-surface-raised pl-10 pr-4 text-sm text-text placeholder:text-text-subtle focus:border-primary focus:outline-none"
              onKeyDown={(e) => e.key === 'Enter' && handleSearch(e.currentTarget.value)}
            />
          </div>
          
          <nav className="flex flex-col space-y-3">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className={`text-base font-medium px-2 py-1.5 rounded-md hover:bg-surface-raised ${
                  link.active ? 'text-primary bg-surface-raised' : 'text-text-muted'
                }`}
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="pt-4 border-t border-border flex flex-col gap-3">
            {actions}
          </div>
        </div>
      )}
    </header>
  );
}

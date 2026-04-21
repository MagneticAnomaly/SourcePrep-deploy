"use client";

import { Button } from '../../primitives/Button';
import { ArrowRight, Hash, LayoutGrid } from 'lucide-react';

export function SwissHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="bg-background">
      <div className="grid grid-cols-12 gap-4 border-t border-text">
        <div className="col-span-12 md:col-span-8 pt-12 pb-24 pr-12">
          <h1 className="text-6xl md:text-8xl font-bold text-text tracking-tight leading-[0.9]">
            Local.<br/>
            Context.<br/>
            Solved.
          </h1>
          <div className="mt-12 grid grid-cols-2 gap-8 border-t border-text pt-6">
            <div>
              <p className="text-sm font-bold uppercase mb-2 flex items-center gap-2"><Hash className="w-4 h-4" /> Problem</p>
              <p className="text-lg leading-snug text-text-muted">AI coding tools index your files but miss how code connects — imports, calls, dependencies.</p>
            </div>
            <div>
              <p className="text-sm font-bold uppercase mb-2 flex items-center gap-2"><LayoutGrid className="w-4 h-4" /> Solution</p>
              <p className="text-lg leading-snug text-text-muted">Rust-powered semantic + structural indexing that feeds perfect context to every AI tool you use.</p>
            </div>
          </div>
        </div>
        <div className="col-span-12 md:col-span-4 bg-primary p-8 flex flex-col justify-between text-background">
          <div className="text-6xl font-bold"><LayoutGrid className="w-16 h-16" /></div>
          <div className="space-y-4">
            <p className="text-2xl font-medium">RunPrep v1.0</p>
            <p className="opacity-80">Structural codebase intelligence for Cursor, Windsurf, and Claude Desktop.</p>
            <Button 
              className="mt-8 bg-white text-primary rounded-full font-bold w-full flex items-center justify-between group hover:bg-white/90 border-none"
              asChild
            >
              {isBetaMode ? (
                <a href="mailto:support@runprep.io?subject=RunPrep%20Beta%20Access%20Request">
                  Request Beta <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </a>
              ) : (
                <a href="/download">
                  Get Started <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </a>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

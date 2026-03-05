"use client";

import { Button } from '../../primitives/Button';
import { ArrowRight, Code, Command, Download } from 'lucide-react';

export function YaleHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="bg-background min-h-[600px] border-t-8 border-primary">
      <div className="max-w-7xl mx-auto px-6 py-12">
        {/* Strict Grid Layout */}
        <div className="grid grid-cols-12 gap-x-6 border-b border-border pb-12">
          <div className="col-span-12 md:col-span-3">
            <span className="font-sans font-bold text-sm tracking-wide uppercase text-text-muted flex items-center gap-2">
              <Command className="w-4 h-4" /> Magnetic Anomaly llc
            </span>
          </div>
          <div className="col-span-12 md:col-span-6">
            <h1
              className="font-heading text-5xl md:text-6xl font-medium text-text leading-tight tracking-tight mb-8"
              style={{ fontFamily: "var(--font-heading, 'IBM Plex Sans', system-ui, Helvetica, Arial, sans-serif)" }}
            >
              This is the bridge between how you think about code and how your AI reads it.
            </h1>
          </div>
          <div className="col-span-12 md:col-span-3 flex flex-col justify-end items-start md:items-end">
            <span className="font-mono text-xs text-text-muted mb-2">RELEASE 2026.1</span>
            <span className="font-mono text-xs text-text-muted">MACOS / WINDOWS / LINUX</span>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-x-6 pt-12">
          {/* Column 1: Description */} 
          <div className="col-span-12 md:col-span-3 md:col-start-4">
            <p className="font-sans text-base text-text leading-relaxed mb-6" >
              CoDRAG's Rust-powered engine indexes your codebase locally—semantics, symbols, and call graphs—with built-in
              ONNX embeddings, path weights for precision control, and smart compression for code and documentation. 
            </p>
            <a href="#" className="font-sans font-medium text-primary hover:underline underline-offset-4 decoration-2 flex items-center gap-1">
              Documentation <ArrowRight className="w-3 h-3" />
            </a>
          </div>

          {/* Column 2: Specs */}
          <div className="col-span-12 md:col-span-3 mt-8 md:mt-0">
            <div className="flex flex-col gap-4 pl-6 border-l border-border">
              
              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-xs text-text-muted shrink-0">Index</span>
                <span className="font-mono text-sm text-text font-bold text-right">Vector + Graph</span>
              </div>

              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-xs text-text-muted shrink-0">Embedding</span>
                <span className="font-mono text-sm text-text font-bold text-right">Local Nomic</span>
              </div>

              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-xs text-text-muted shrink-0">Compression</span>
                <span className="font-mono text-sm text-text font-bold text-right">3–20× (Smart)</span>
              </div>
              
              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-xs text-text-muted shrink-0">Integrations</span>
                <span className="font-mono text-sm text-text font-bold text-right">MCP Native</span>
              </div>

              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-xs text-text-muted shrink-0">Latency</span>
                <span className="font-mono text-sm text-text font-bold text-right">&lt;100ms</span>
              </div>
              
            </div>
          </div>

          {/* Column 3: Action */}
          <div className="col-span-12 md:col-span-3 mt-8 md:mt-0 flex flex-col justify-between">
            <div className="pl-6 md:border-l md:border-border">
              <span className="font-sans font-bold text-sm mb-4 block">Get Started</span>
              <div className="flex flex-col gap-2">
                {isBetaMode ? (
                  <Button variant="ghost" className="justify-start px-0 hover:bg-transparent hover:text-primary h-auto py-2" icon={Download} asChild>
                    <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request">Request Beta</a>
                  </Button>
                ) : (
                  <Button variant="ghost" className="justify-start px-0 hover:bg-transparent hover:text-primary h-auto py-2" icon={Download} asChild>
                    <a href="/download">Download Installer</a>
                  </Button>
                )}
                <Button variant="ghost" className="justify-start px-0 hover:bg-transparent hover:text-primary h-auto py-2" icon={Code} asChild>
                  <a href="/docs">Documentation</a>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

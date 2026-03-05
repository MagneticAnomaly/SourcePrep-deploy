"use client";

import { Button } from '../../primitives/Button';
import { Eye, Lock, Zap } from 'lucide-react';

export function FocusHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="bg-background min-h-[600px] flex flex-col justify-center relative">
      <div className="w-full max-w-4xl mx-auto px-6 text-center z-10">
        <div className="mb-8 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-info/10 text-info font-medium text-sm border border-info/20">
          <Eye className="w-4 h-4" />
          <span>Essential for AI-Assisted Development</span>
        </div>

        <h1 className="text-5xl md:text-7xl font-bold text-text mb-8 tracking-tight">
          Better context in.<br/>
          <span className="text-primary underline decoration-4 underline-offset-8 decoration-primary/30">Better code out.</span>
        </h1>

        <p className="text-xl md:text-2xl text-text-muted max-w-2xl mx-auto mb-12 leading-relaxed font-medium">
          CoDRAG adds the context intelligence layer your AI tools are missing — built-in embeddings,
          structural code graph, path weights, and smart compression so Cursor, Windsurf, and Claude Desktop
          get the right code, not just more code.
        </p>

        <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
          {isBetaMode ? (
            <Button 
              size="lg" 
              className="w-full sm:w-auto px-8 py-6 text-lg font-bold shadow-lg transform hover:-translate-y-1 h-auto"
              asChild
            >
              <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request">Request Beta Access</a>
            </Button>
          ) : (
            <Button 
              size="lg" 
              className="w-full sm:w-auto px-8 py-6 text-lg font-bold shadow-lg transform hover:-translate-y-1 h-auto"
              asChild
            >
              <a href="/download">Download for Free</a>
            </Button>
          )}
          <Button 
            size="lg" 
            variant="outline" 
            className="w-full sm:w-auto px-8 py-6 text-lg font-bold border-2 h-auto"
            asChild
          >
            <a href="/docs">See How It Works</a>
          </Button>
        </div>

        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
          <div className="bg-surface p-6 rounded-xl border border-border shadow-sm">
            <div className="w-12 h-12 bg-success/20 rounded-lg flex items-center justify-center text-2xl mb-4 text-success"><Lock className="w-6 h-6" /></div>
            <h3 className="font-bold text-lg text-text mb-2">Private & Extensible</h3>
            <p className="text-text-muted">Your code never leaves your machine. Use built-in local models for zero network traffic, or seamlessly connect your preferred cloud APIs.</p>
          </div>
          <div className="bg-surface p-6 rounded-xl border border-border shadow-sm">
            <div className="w-12 h-12 bg-warning/20 rounded-lg flex items-center justify-center text-2xl mb-4 text-warning"><Zap className="w-6 h-6" /></div>
            <h3 className="font-bold text-lg text-text mb-2">Sub-100ms Search</h3>
            <p className="text-text-muted">Semantic search across every project you manage. Results before you finish typing.</p>
          </div>
          <div className="bg-surface p-6 rounded-xl border border-border shadow-sm">
            <div className="w-12 h-12 bg-primary/20 rounded-lg flex items-center justify-center text-2xl mb-4 text-primary"><Eye className="w-6 h-6" /></div>
            <h3 className="font-bold text-lg text-text mb-2">Structural Code Graph</h3>
            <p className="text-text-muted">Goes beyond vector search. A Rust engine maps imports, calls, and symbol hierarchies so AI sees how code connects.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

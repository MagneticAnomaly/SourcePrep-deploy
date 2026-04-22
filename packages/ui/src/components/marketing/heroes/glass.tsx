"use client";

import { Badge, Flex } from '@tremor/react';
import { Button } from '../../primitives/Button';
import { Activity, Cpu, Database, Zap } from 'lucide-react';

export function GlassHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 p-8 md:p-16">
      <div className="absolute top-0 left-0 w-64 h-64 bg-primary/30 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2"></div>
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-info/30 rounded-full blur-3xl translate-x-1/3 translate-y-1/3"></div>
      
      <div className="relative z-10 flex flex-col items-center text-center">
        <div className="backdrop-blur-xl bg-white/30 border border-white/50 shadow-xl rounded-2xl p-8 md:p-12 max-w-4xl w-full">
          <Badge className="bg-white/50 text-text border-white/60 backdrop-blur-md mb-6 shadow-sm gap-2">
            <Zap className="w-4 h-4 text-warning" /> Essential for AI-assisted development
          </Badge>
          
          <h1 className="text-5xl md:text-7xl font-bold text-text bg-clip-text text-transparent bg-gradient-to-r from-text to-primary mb-6">
            Context Your AI Can Trust
          </h1>
          
          <p className="text-xl text-text-muted mb-8 max-w-2xl mx-auto">
            SourcePrep sits between your codebase and your AI tools — built-in embeddings, structural tracing,
            path weights for precision control, and smart compression for both code and docs. Better context in, better code out. Core runs entirely locally, add cloud reasoning when needed.
          </p>

          <Flex className="gap-4" justifyContent="center">
            {isBetaMode ? (
              <Button size="lg" className="backdrop-blur-md bg-primary/80 hover:bg-primary text-background rounded-xl shadow-lg hover:shadow-primary/30 border border-white/20" asChild>
                <a href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request">Request Beta</a>
              </Button>
            ) : (
              <Button size="lg" className="backdrop-blur-md bg-primary/80 hover:bg-primary text-background rounded-xl shadow-lg hover:shadow-primary/30 border border-white/20" asChild>
                <a href="/download">Download Free</a>
              </Button>
            )}
            <Button size="lg" variant="ghost" className="backdrop-blur-md bg-white/40 hover:bg-white/60 text-text rounded-xl border border-white/40" asChild>
              <a href="/docs">See How It Works</a>
            </Button>
          </Flex>
        </div>

        {/* Floating cards */}
        <div className="mt-16 flex gap-6" style={{ perspective: '1000px' }}>
          <div 
            className="backdrop-blur-lg bg-white/20 border border-white/30 p-4 rounded-xl shadow-lg"
            style={{ transform: 'rotateY(12deg) translateY(1rem)' }}
          >
            <div className="w-12 h-12 bg-success/40 rounded-full mb-3 blur-sm flex items-center justify-center"><Activity className="w-6 h-6 text-white" /></div>
            <div className="h-2 w-24 bg-white/40 rounded mb-2"></div>
            <div className="h-2 w-16 bg-white/30 rounded"></div>
          </div>
          <div className="backdrop-blur-lg bg-white/40 border border-white/50 p-6 rounded-xl shadow-2xl z-20 scale-110">
            <div className="text-4xl mb-2 flex justify-center"><Cpu className="w-12 h-12 text-primary" /></div>
            <div className="font-bold text-text">Deep Index</div>
          </div>
          <div 
            className="backdrop-blur-lg bg-white/20 border border-white/30 p-4 rounded-xl shadow-lg"
            style={{ transform: 'rotateY(-12deg) translateY(1rem)' }}
          >
            <div className="w-12 h-12 bg-primary/40 rounded-full mb-3 blur-sm flex items-center justify-center"><Database className="w-6 h-6 text-white" /></div>
            <div className="h-2 w-24 bg-white/40 rounded mb-2"></div>
            <div className="h-2 w-16 bg-white/30 rounded"></div>
          </div>
        </div>
      </div>
    </div>
  );
}

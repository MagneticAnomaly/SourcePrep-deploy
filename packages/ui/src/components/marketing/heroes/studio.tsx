"use client";

import { Text } from '@tremor/react';
import { Button } from '../../primitives/Button';
import { Activity, ArrowRight, Code, Download, Eye } from 'lucide-react';

export function FeaturePoint({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xl">{icon}</span>
      <Text className="text-text">{text}</Text>
    </div>
  );
}

export function StudioHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="relative bg-background p-8 md:p-16 overflow-hidden min-h-[600px] flex items-center">
      {/* Abstract Shapes/Collage Elements */}
      <div className="absolute top-10 right-10 w-64 h-64 bg-primary/20 rounded-full blur-3xl mix-blend-multiply"></div>
      <div className="absolute bottom-10 left-10 w-80 h-80 bg-warning/20 rounded-full blur-3xl mix-blend-multiply"></div>
      
      <div className="relative z-10 w-full max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
        {/* Main Text Block - Asymmetric */}
        <div className="col-span-12 md:col-span-7 space-y-6">
          <div className="inline-block bg-surface border border-border px-4 py-2 shadow-sm">
            <span className="font-mono text-xs uppercase tracking-widest text-text-muted flex items-center gap-2">
              <Code className="w-3 h-3" /> Essential Developer Tool
            </span>
          </div>
          
          <h1 className="text-6xl md:text-8xl font-serif text-text leading-[0.9] tracking-tight">
            See your code <br/>
            <span className="italic text-primary">the way AI should.</span>
          </h1>
          
          <div className="max-w-md bg-surface/80 backdrop-blur-sm p-6 border-l-4 border-primary mt-8">
            <p className="text-lg font-sans text-text leading-relaxed">
              Prep's Rust engine maps the semantics, symbols, and structure of your codebase
              so every AI prompt gets the context it needs. Runs locally, or connects to your cloud.
            </p>
          </div>

          <div className="flex gap-4 pt-4">
            {isBetaMode ? (
              <Button 
                className="px-8 py-6 bg-text text-background font-mono text-sm hover:bg-primary transition-colors gap-2 rounded-none"
                icon={Download}
                asChild
              >
                <a href="mailto:support@runprep.io?subject=Prep%20Beta%20Access%20Request">[ JOIN_BETA ]</a>
              </Button>
            ) : (
              <Button 
                className="px-8 py-6 bg-text text-background font-mono text-sm hover:bg-primary transition-colors gap-2 rounded-none"
                icon={Download}
                asChild
              >
                <a href="/download">[ GET_PREP ]</a>
              </Button>
            )}
            <Button 
              variant="outline"
              className="px-8 py-6 border-text text-text font-serif italic hover:bg-surface-raised transition-colors gap-2 rounded-none"
              asChild
            >
              <a href="/docs">How it works <ArrowRight className="w-4 h-4 ml-2" /></a>
            </Button>
          </div>
        </div>

        {/* Visual Collage Right (No Rotation, playful retro-future elements) */}
        <div className="col-span-12 md:col-span-5 relative h-[400px]">
          {/* Retro Grid element */}
          <div className="absolute top-0 right-10 w-48 h-48 opacity-20" 
             style={{ 
               backgroundImage: 'linear-gradient(currentColor 1px, transparent 1px), linear-gradient(90deg, currentColor 1px, transparent 1px)',
               backgroundSize: '10px 10px'
             }}>
          </div>

          <div className="absolute top-10 right-0 w-64 bg-surface border-2 border-border p-4 shadow-xl z-20">
            <div className="font-mono text-xs border-b border-border pb-2 mb-2 flex justify-between">
              <span>index_status.log</span>
              <Activity className="w-3 h-3" />
            </div>
            <div className="flex gap-1 mb-2">
              <div className="w-2 h-2 rounded-full bg-success"></div>
              <div className="w-2 h-2 rounded-full bg-success"></div>
              <div className="w-2 h-2 rounded-full bg-warning animate-pulse"></div>
            </div>
            <div className="h-2 bg-surface-raised w-3/4 mb-1"></div>
            <div className="h-2 bg-surface-raised w-1/2"></div>
          </div>

          <div className="absolute top-32 left-0 w-72 bg-surface-raised border border-border p-6 shadow-lg z-10">
            <h3 className="font-mono text-2xl italic mb-2 flex items-center gap-2"><Eye className="w-5 h-5" /> Structural Code Graph</h3>
            <p className="font-sans text-sm text-text-muted">
              Rust-powered engine maps imports, call graphs, and symbol hierarchies so AI understands how your code connects.
            </p>
          </div>

          <div className="absolute bottom-10 right-20 w-40 h-40 border-4 border-primary rounded-full flex items-center justify-center bg-background/50 backdrop-blur-sm z-30">
            <span className="font-mono text-xs text-center font-bold">
              PRIVACY<br/>FIRST<br/>BY DESIGN
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

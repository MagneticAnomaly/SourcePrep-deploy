"use client";

import { Badge, Flex } from '@tremor/react';
import { Button } from '../../primitives/Button';
import { Cpu, Zap, Database, Server, Lock } from 'lucide-react';

export function CenteredHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-surface via-surface to-surface-raised">
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-30">
        <svg className="w-full h-full" viewBox="0 0 800 400">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="hsl(var(--border))" strokeWidth="0.5" />
            </pattern>
            <radialGradient id="fade" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.15" />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
          <rect width="100%" height="100%" fill="url(#fade)" />
        </svg>
      </div>

      <div className="relative z-10 px-8 py-16 md:px-16 md:py-24 text-center">
        {/* Eyebrow */}
        <div className="flex justify-center mb-6">
          <Badge size="lg" className="bg-primary/10 text-primary border border-primary/20 px-4 py-1.5 gap-2">
            <Cpu className="w-4 h-4" />
            Local-first • Cloud-ready (BYOK)
          </Badge>
        </div>

        {/* Headline */}
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-text leading-tight max-w-4xl mx-auto">
          Your AI writes better code{' '}
          <span className="text-primary">when it can see yours.</span>
        </h1>

        {/* Subheadline */}
        <p className="mt-6 text-lg md:text-xl text-text-muted max-w-2xl mx-auto leading-relaxed">
          CoDRAG's Rust-powered engine indexes your entire codebase — semantics, symbols,
          and call graphs — with built-in ONNX embeddings, path weights for precision control, and
          smart structural compression that fits 3–20× more code context into every prompt. Runs locally, or connect your preferred cloud APIs.
        </p>

        {/* CTAs */}
        <Flex className="mt-10 gap-4" justifyContent="center" alignItems="center">
          {isBetaMode ? (
            <Button size="lg" className="shadow-lg shadow-primary/25" asChild>
              <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request">Request Beta Access</a>
            </Button>
          ) : (
            <Button size="lg" className="shadow-lg shadow-primary/25" asChild>
              <a href="/download">Download for Free</a>
            </Button>
          )}
          <Button size="lg" variant="outline" className="border-2" asChild>
            <a href="/docs">See How It Works</a>
          </Button>
        </Flex>

        {/* Trust indicators */}
        <div className="mt-12 flex flex-wrap justify-center gap-6 text-text-subtle text-sm">
          <span className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-success" /> Runs offline or cloud-connected
          </span>
          <span className="flex items-center gap-2">
            <Database className="w-4 h-4 text-success" /> Built-in embeddings or BYOK
          </span>
          <span className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-success" /> Pro license — yours forever
          </span>
          <span className="flex items-center gap-2">
            <Server className="w-4 h-4 text-success" /> macOS & Windows
          </span>
        </div>
      </div>

      {/* Product screenshot placeholder */}
      <div className="relative mx-8 mb-8 md:mx-16">
        <div className="rounded-xl border border-border bg-surface shadow-2xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-surface">
            <div className="flex gap-1.5">
              <span className="w-3 h-3 rounded-full bg-error/60" />
              <span className="w-3 h-3 rounded-full bg-warning/60" />
              <span className="w-3 h-3 rounded-full bg-success/60" />
            </div>
            <span className="text-xs text-text-subtle ml-2">CoDRAG — LinuxBrain</span>
          </div>
          <div className="p-6 min-h-[200px] bg-gradient-to-b from-surface to-background">
            {/* Mock dashboard UI */}
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2 space-y-3">
                <div className="h-8 bg-surface-raised rounded-lg border border-border-subtle animate-pulse" />
                <div className="space-y-2">
                  <div className="h-20 bg-surface-raised rounded-lg border border-border-subtle" />
                  <div className="h-20 bg-surface-raised rounded-lg border border-border-subtle" />
                </div>
              </div>
              <div className="space-y-3">
                <div className="h-24 bg-primary/10 rounded-lg border border-primary/20" />
                <div className="h-16 bg-surface-raised rounded-lg border border-border-subtle" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

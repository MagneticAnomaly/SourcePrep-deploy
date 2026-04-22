"use client";

import { Badge, Flex, Text } from '@tremor/react';
import { Button } from '../../primitives/Button';
import { Search, Shield, Layers, Zap } from 'lucide-react';
import { FeaturePoint } from './studio';

export function SplitHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="grid lg:grid-cols-2 gap-12 items-center py-12">
      {/* Left: Content */}
      <div>
        <Badge size="lg" className="bg-primary/10 text-primary border border-primary/20 mb-6 gap-2">
          <Zap className="w-4 h-4" /> The missing layer for AI coding
        </Badge>
        
        <h1 className="text-4xl md:text-5xl font-bold text-text leading-tight">
          Your code. <br />
          <span className="text-primary">Your context.</span> <br />
          Your machine.
        </h1>

        <p className="mt-6 text-lg text-text-muted leading-relaxed">
          AI tools already index your code — but they grab files, not relationships.
          SourcePrep's Rust engine adds the structural layer: semantics, symbols, and call graphs.
          The right context, delivered in under 100 ms.
        </p>

        <div className="mt-8 space-y-4">
          <FeaturePoint icon={<Search className="w-5 h-5 text-primary" />} text="Semantic search with built-in ONNX embeddings — Ollama or cloud API optional" />
          <FeaturePoint icon={<Layers className="w-5 h-5 text-primary" />} text="Rust-powered Code Graph maps imports, calls, and symbol hierarchies" />
          <FeaturePoint icon={<Zap className="w-5 h-5 text-primary" />} text="Path weights let you boost core modules and silence noise — instantly" />
          <FeaturePoint icon={<Shield className="w-5 h-5 text-primary" />} text="Smart compression for code (3–20× structural) and docs (language-aware) — built in" />
        </div>

        <Flex className="mt-10 gap-4">
          {isBetaMode ? (
            <Button size="lg" className="font-semibold" asChild>
              <a href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request">Request Beta</a>
            </Button>
          ) : (
            <Button size="lg" className="font-semibold" asChild>
              <a href="/download">Download for Free</a>
            </Button>
          )}
          <Button size="lg" variant="outline" className="font-semibold" asChild>
            <a href="/docs">See How It Works</a>
          </Button>
        </Flex>
      </div>

      {/* Right: Visual */}
      <div className="relative">
        <div className="absolute -inset-4 bg-gradient-to-r from-primary/20 to-info/20 rounded-3xl blur-3xl opacity-50" />
        <div className="relative rounded-2xl border border-border bg-surface p-6 shadow-xl">
          <Text className="text-text-subtle text-sm mb-4 flex items-center gap-2"><Search className="w-4 h-4" /> Search: "authentication middleware"</Text>
          
          <div className="space-y-3">
            {[
              { file: 'src/auth/middleware.ts', score: 94, lines: '12-45' },
              { file: 'src/api/routes/auth.py', score: 87, lines: '88-112' },
              { file: 'docs/AUTH.md', score: 72, lines: '1-34' },
            ].map((result) => (
              <div
                key={result.file}
                className="flex items-center justify-between p-3 rounded-lg bg-surface-raised border border-border-subtle"
              >
                <div>
                  <div className="font-mono text-sm text-text">{result.file}</div>
                  <div className="text-xs text-text-subtle">Lines {result.lines}</div>
                </div>
                <Badge color={result.score > 90 ? 'green' : result.score > 80 ? 'blue' : 'gray'}>
                  {result.score}%
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

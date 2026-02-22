"use client";

import { Badge, Flex, Text } from '@tremor/react';
import { Button } from '../primitives/Button';
import { 
  Terminal, Search, Cpu, Shield, Layers, Zap, Eye, 
  Database, Server, Lock, Activity, FileText, Code, 
  Command, Hash, Download, ArrowRight, LayoutGrid,
  AlertTriangle
} from 'lucide-react';

export interface MarketingHeroProps {
  variant?: 'centered' | 'split' | 'neo' | 'swiss' | 'glass' | 'retro' | 'studio' | 'yale' | 'focus' | 'enterprise';
}

export function MarketingHero({ variant = 'centered' }: MarketingHeroProps) {
  switch (variant) {
    case 'split': return <SplitHero />;
    case 'neo': return <NeoBrutalistHero />;
    case 'swiss': return <SwissHero />;
    case 'glass': return <GlassHero />;
    case 'retro': return <RetroHero />;
    case 'studio': return <StudioHero />;
    case 'yale': return <YaleHero />;
    case 'focus': return <FocusHero />;
    case 'enterprise': return <EnterpriseHero />;
    default: return <CenteredHero />;
  }
}

function CenteredHero() {
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
          smart compression that fits 3–20× more signal into every prompt. Runs locally, or connect your preferred cloud APIs.
        </p>

        {/* CTAs */}
        <Flex className="mt-10 gap-4" justifyContent="center" alignItems="center">
          <Button size="lg" className="shadow-lg shadow-primary/25">
            Download for Free
          </Button>
          <Button size="lg" variant="outline" className="border-2">
            See How It Works
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
            <Lock className="w-4 h-4 text-success" /> Perpetual license available
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

function NeoBrutalistHero() {
  return (
    <div className="border-4 border-border bg-surface p-8 md:p-12 shadow-xl">
      <div className="flex flex-col md:flex-row gap-8 items-start">
        <div className="flex-1">
          <div className="inline-flex items-center gap-2 border-2 border-border bg-warning px-4 py-1 text-sm font-bold text-black mb-6 transform -rotate-2">
            <AlertTriangle className="w-4 h-4" /> NO CLOUD REQUIRED
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold text-text leading-none uppercase tracking-tighter">
            Your AI<br/>
            Sees Code.<br/>
            <span className="bg-primary text-background px-2">Not Structure.</span><br/>
            Fix That.
          </h1>
          
          <p className="mt-6 text-xl text-text font-mono border-l-4 border-primary pl-4">
            CoDRAG adds the structural layer your AI tools are missing.
            Imports, calls, symbol graphs — indexed in Rust, instantly served.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row gap-4">
            <Button 
              size="lg"
              className="border-2 border-border bg-primary text-background font-bold text-lg hover:translate-x-1 hover:translate-y-1 hover:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all rounded-none"
              icon={Download}
            >
              GET_CODRAG
            </Button>
            <Button 
              size="lg"
              variant="outline"
              className="border-2 border-border bg-surface text-text font-bold text-lg hover:translate-x-1 hover:translate-y-1 hover:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all rounded-none"
              icon={FileText}
            >
              SEE_HOW_IT_WORKS
            </Button>
          </div>
        </div>

        <div className="flex-1 w-full">
          <div className="border-4 border-border bg-background p-2 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
            <div className="border-b-4 border-border pb-2 mb-4 flex justify-between items-center px-2">
              <span className="font-bold flex items-center gap-2"><Terminal className="w-4 h-4" /> MCP_BRIDGE_LOG</span>
              <div className="flex gap-2">
                <div className="w-4 h-4 bg-error border-2 border-black"></div>
                <div className="w-4 h-4 bg-warning border-2 border-black"></div>
              </div>
            </div>
            <div className="font-mono text-sm space-y-2 p-2">
              <div className="text-text-muted border-b border-border/50 pb-2 mb-2">
                <span className="text-info"># ~/.codeium/windsurf/mcp_config.json</span><br/>
                {`"codrag": { "url": "http://localhost:8400/mcp/sse", "transport": "sse" }`}
              </div>
              
              <div className="text-success">$ cascade_agent --connect codrag</div>
              <div className="text-text-muted">[mcp] tools loaded: codrag (primary), codrag_search, codrag_trace</div>
              
              <div className="mt-4">
                <span className="text-primary font-bold">USER:</span> "Graph the auth flow and find where tokens expire"
              </div>
              
              <div className="bg-primary/10 p-2 border-l-2 border-primary mt-2">
                <div className="text-xs text-text-subtle mb-1">TOOL CALL: codrag(trace_expand=true)</div>
                <span className="text-primary">&gt; Found 3 entry points in src/auth/*</span><br/>
                <span className="text-primary">&gt; Traced 12 downstream calls (Rust Code Graph)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SwissHero() {
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
            <p className="text-2xl font-medium">CoDRAG v1.0</p>
            <p className="opacity-80">Structural codebase intelligence for Cursor, Windsurf, and Claude Desktop.</p>
            <Button 
              className="mt-8 bg-white text-primary rounded-full font-bold w-full flex items-center justify-between group hover:bg-white/90 border-none"
            >
              Get Started <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function GlassHero() {
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
            CoDRAG sits between your codebase and your AI tools — built-in embeddings, structural tracing,
            path weights for precision control, and smart compression for both code and docs. Better context in, better code out. Runs locally, or connects to your cloud APIs.
          </p>

          <Flex className="gap-4" justifyContent="center">
            <Button size="lg" className="backdrop-blur-md bg-primary/80 hover:bg-primary text-background rounded-xl shadow-lg hover:shadow-primary/30 border border-white/20">
              Download Free
            </Button>
            <Button size="lg" variant="ghost" className="backdrop-blur-md bg-white/40 hover:bg-white/60 text-text rounded-xl border border-white/40">
              See How It Works
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

function RetroHero() {
  return (
    <div className="relative overflow-hidden rounded-lg bg-background border border-primary/50">
      {/* Grid Floor */}
      <div className="absolute inset-0" 
           style={{ 
             backgroundImage: 'linear-gradient(rgba(255, 0, 255, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 0, 255, 0.1) 1px, transparent 1px)',
             backgroundSize: '40px 40px',
             transform: 'perspective(500px) rotateX(60deg) translateY(-100px) scale(2)',
             opacity: 0.5
           }}>
      </div>
      
      {/* Sun */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-gradient-to-t from-warning to-primary rounded-full blur-[80px] opacity-40"></div>

      <div className="relative z-10 px-8 py-20 text-center">
        <h1 className="text-6xl md:text-8xl font-black text-transparent bg-clip-text bg-gradient-to-b from-primary to-purple-800 drop-shadow-[0_0_10px_rgba(255,0,255,0.5)]"
            style={{ fontFamily: "'Share Tech Mono', monospace" }}>
          CODRAG
        </h1>
        <p className="text-2xl text-primary font-bold tracking-[0.5em] mt-2 mb-12 uppercase drop-shadow-md">
          Context Engine
        </p>

        <div className="max-w-3xl mx-auto bg-black/50 backdrop-blur-sm border border-primary/50 p-6 rounded-lg shadow-[0_0_30px_rgba(255,0,255,0.2)]">
          <p className="text-lg text-white font-mono leading-relaxed">
            <span className="text-success">SYSTEM_INIT...</span><br/>
            &gt; TRACE_INDEX: <span className="text-success">RUST_CORE READY (72ms)</span><br/>
            &gt; MCP_SERVER: <span className="text-info">LISTENING ON :8400</span><br/>
            &gt; TOOLS_LOADED: <span className="text-warning">codrag (context), search, trace</span><br/>
            &gt; INTEGRATIONS: <span className="text-success">CURSOR=OK WINDSURF=OK CLAUDE=OK</span><br/><br/>
            <span className="animate-pulse flex items-center justify-center gap-2">_WAITING FOR EDITOR COMMAND... <Terminal className="w-4 h-4" /></span>
          </p>
        </div>

        <Button 
          className="mt-12 bg-transparent border-2 border-primary text-primary hover:bg-primary hover:text-background px-10 py-4 text-xl font-bold uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(255,0,255,0.4)] hover:shadow-[0_0_40px_rgba(255,0,255,0.8)] rounded-none h-auto"
        >
          Get CoDRAG
        </Button>
      </div>
    </div>
  );
}

function SplitHero() {
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
          CoDRAG's Rust engine adds the structural layer: semantics, symbols, and call graphs.
          The right context, delivered in under 100 ms.
        </p>

        <div className="mt-8 space-y-4">
          <FeaturePoint icon={<Search className="w-5 h-5 text-primary" />} text="Semantic search with built-in ONNX embeddings — Ollama or cloud API optional" />
          <FeaturePoint icon={<Layers className="w-5 h-5 text-primary" />} text="Rust-powered Code Graph maps imports, calls, and symbol hierarchies" />
          <FeaturePoint icon={<Zap className="w-5 h-5 text-primary" />} text="Path weights let you boost core modules and silence noise — instantly" />
          <FeaturePoint icon={<Shield className="w-5 h-5 text-primary" />} text="Smart compression for code (3–20× structural) and docs (language-aware) — built in" />
        </div>

        <Flex className="mt-10 gap-4">
          <Button size="lg" className="font-semibold">
            Download for Free
          </Button>
          <Button size="lg" variant="outline" className="font-semibold">
            See How It Works
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

function FeaturePoint({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xl">{icon}</span>
      <Text className="text-text">{text}</Text>
    </div>
  );
}

function StudioHero() {
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
              CoDRAG's Rust engine maps the semantics, symbols, and structure of your codebase
              so every AI prompt gets the context it needs. Runs locally, or connects to your cloud.
            </p>
          </div>

          <div className="flex gap-4 pt-4">
            <Button 
              className="px-8 py-6 bg-text text-background font-mono text-sm hover:bg-primary transition-colors gap-2 rounded-none"
              icon={Download}
            >
              [ GET_CODRAG ]
            </Button>
            <Button 
              variant="outline"
              className="px-8 py-6 border-text text-text font-serif italic hover:bg-surface-raised transition-colors gap-2 rounded-none"
            >
              How it works <ArrowRight className="w-4 h-4 ml-2" />
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

function YaleHero() {
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
            <p className="font-sans text-base text-text leading-relaxed mb-6">
              CoDRAG's Rust-powered engine indexes your codebase locally—semantics, symbols, and call graphs—with built-in
              ONNX embeddings, path weights for precision control, and smart compression for code and documentation. No cloud upload. No LLM required — Ollama and cloud APIs optional.
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
                <Button variant="ghost" className="justify-start px-0 hover:bg-transparent hover:text-primary h-auto py-2" icon={Download}>
                  Download Installer
                </Button>
                <Button variant="ghost" className="justify-start px-0 hover:bg-transparent hover:text-primary h-auto py-2" icon={Code}>
                  Documentation
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FocusHero() {
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
          <Button 
            size="lg" 
            className="w-full sm:w-auto px-8 py-6 text-lg font-bold shadow-lg transform hover:-translate-y-1 h-auto"
          >
            Download for Free
          </Button>
          <Button 
            size="lg" 
            variant="outline" 
            className="w-full sm:w-auto px-8 py-6 text-lg font-bold border-2 h-auto"
          >
            See How It Works
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

function EnterpriseHero() {
  return (
    <div className="bg-surface-raised min-h-[600px] border-b border-border">
      {/* Top Bar */}
      <div className="bg-background border-b border-border px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <span className="font-mono font-bold text-lg tracking-tight flex items-center gap-2"><LayoutGrid className="w-5 h-5" /> CoDRAG</span>
          <span className="px-2 py-0.5 bg-surface-raised border border-border text-xs text-text-subtle uppercase">Enterprise</span>
        </div>
        <div className="flex gap-4 text-sm font-medium text-text-muted">
          <span>Overview</span>
          <span>Deployments</span>
          <span>Security</span>
          <span className="text-primary">Docs</span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-12 grid grid-cols-12 gap-8">
        {/* Left: Content */}
        <div className="col-span-12 md:col-span-5 flex flex-col justify-center">
          <div className="mb-6">
            <span className="text-primary font-mono text-sm font-semibold mb-2 block">PLATFORM_V1.0</span>
            <h1 className="text-4xl md:text-5xl font-sans font-semibold text-text leading-tight mb-4">
              Give every engineer AI that understands your codebase.
            </h1>
            <p className="text-text-muted text-lg leading-relaxed">
              CoDRAG Enterprise standardizes Rust-powered semantic + structural indexing across your
              organization. Shared context layers accelerate onboarding, improve AI output
              quality, and keep all code on-premise.
            </p>
          </div>

          <div className="space-y-4 mb-8">
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-primary shadow-sm">
              <span className="text-primary font-bold">01</span>
              <span className="font-medium text-text">Air-Gapped Deployment & Governance</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-border shadow-sm opacity-70">
              <span className="text-text-subtle font-bold">02</span>
              <span className="font-medium text-text">Shared Context Across Teams</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-border shadow-sm opacity-70">
              <span className="text-text-subtle font-bold">03</span>
              <span className="font-medium text-text">SSO, SCIM & Audit Logging</span>
            </div>
          </div>

          <Button size="lg" className="w-fit shadow-sm">
            Contact Sales
          </Button>
        </div>

        {/* Right: Dashboard Preview */}
        <div className="col-span-12 md:col-span-7">
          <div className="bg-background border border-border shadow-md rounded-sm overflow-hidden h-full flex flex-col">
            <div className="bg-surface-raised border-b border-border p-3 flex justify-between items-center">
              <span className="font-mono text-xs text-text-muted flex items-center gap-2"><Lock className="w-3 h-3" /> admin_console</span>
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-border"></div>
                <div className="w-3 h-3 rounded-full bg-border"></div>
              </div>
            </div>
            <div className="p-6 grid grid-cols-2 gap-4 flex-1">
              <div className="bg-surface-raised border border-border rounded h-32"></div>
              <div className="bg-surface-raised border border-border rounded h-32"></div>
              <div className="col-span-2 bg-surface-raised border border-border rounded h-48"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

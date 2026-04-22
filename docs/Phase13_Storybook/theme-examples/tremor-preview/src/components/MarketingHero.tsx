import { Badge, Button, Flex, Text, Title } from '@tremor/react';
import {
  Terminal, Search, Cpu, Shield, Globe, Layers, Zap, Eye,
  Database, Server, Lock, Activity, FileText, Code,
  ChevronRight, Command, Hash, Download, ArrowRight, LayoutGrid,
  AlertTriangle
} from 'lucide-react';

interface MarketingHeroProps {
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
            Local-first • No cloud required
          </Badge>
        </div>

        {/* Headline */}
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-text leading-tight max-w-4xl mx-auto">
          Semantic search for your codebase.{' '}
          <span className="text-primary">Instant context for AI.</span>
        </h1>

        {/* Subheadline */}
        <p className="mt-6 text-lg md:text-xl text-text-muted max-w-2xl mx-auto leading-relaxed">
          Prep indexes your code locally, delivers trace-aware search results,
          and assembles perfect context for Cursor, Windsurf, and Copilot—all without
          sending your code to the cloud.
        </p>

        {/* CTAs */}
        <Flex className="mt-10 gap-4" justifyContent="center" alignItems="center">
          <Button size="lg" className="bg-primary hover:bg-primary-hover text-white px-8 py-3 text-base font-semibold shadow-lg shadow-primary/25">
            Download for macOS
          </Button>
          <Button size="lg" variant="secondary" className="border-2 border-border px-8 py-3 text-base font-semibold">
            View Documentation
          </Button>
        </Flex>

        {/* Trust indicators */}
        <div className="mt-12 flex flex-wrap justify-center gap-6 text-text-subtle text-sm">
          <span className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-success" /> Works offline
          </span>
          <span className="flex items-center gap-2">
            <Database className="w-4 h-4 text-success" /> Bring your own LLM
          </span>
          <span className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-success" /> Perpetual license available
          </span>
          <span className="flex items-center gap-2">
            <Server className="w-4 h-4 text-success" /> macOS, Windows & Linux
          </span>
        </div>
      </div>

      {/* Product screenshot placeholder */}
      <div className="relative mx-8 mb-8 md:mx-16">
        <div className="rounded-xl border border-border bg-background shadow-2xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-surface">
            <div className="flex gap-1.5">
              <span className="w-3 h-3 rounded-full bg-error/60" />
              <span className="w-3 h-3 rounded-full bg-warning/60" />
              <span className="w-3 h-3 rounded-full bg-success/60" />
            </div>
            <span className="text-xs text-text-subtle ml-2">Prep — LinuxBrain</span>
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
            Stop<br />
            Feeding<br />
            <span className="bg-primary text-white px-2">The AI</span><br />
            Beast.
          </h1>

          <p className="mt-6 text-xl text-text font-mono border-l-4 border-primary pl-4">
            Prep runs locally. Your code stays yours.
            Semantic search that actually respects your privacy.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row gap-4">
            <button className="border-2 border-border bg-primary text-white px-8 py-4 font-bold text-lg hover:translate-x-1 hover:translate-y-1 hover:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all flex items-center gap-2">
              <Download className="w-6 h-6" /> DOWNLOAD_NOW.EXE
            </button>
            <button className="border-2 border-border bg-surface text-text px-8 py-4 font-bold text-lg hover:translate-x-1 hover:translate-y-1 hover:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all flex items-center gap-2">
              <FileText className="w-6 h-6" /> READ_MANIFESTO
            </button>
          </div>
        </div>

        <div className="flex-1 w-full">
          <div className="border-4 border-border bg-background p-2 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
            <div className="border-b-4 border-border pb-2 mb-4 flex justify-between items-center px-2">
              <span className="font-bold flex items-center gap-2"><Terminal className="w-4 h-4" /> TERMINAL_PREVIEW</span>
              <div className="flex gap-2">
                <div className="w-4 h-4 bg-error border-2 border-black"></div>
                <div className="w-4 h-4 bg-warning border-2 border-black"></div>
              </div>
            </div>
            <div className="font-mono text-sm space-y-2 p-2">
              <div className="text-success">$ prep index --watch</div>
              <div className="text-text-muted">[info] watching 1,245 files</div>
              <div className="text-text-muted">[info] embedding model loaded (CPU)</div>
              <div className="text-success">$ prep search "auth flow"</div>
              <div className="bg-primary/20 p-2 border-2 border-primary border-dashed text-primary-dark">
                &gt; Found 3 matches in src/auth/
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
            Local.<br />
            Context.<br />
            Solved.
          </h1>
          <div className="mt-12 grid grid-cols-2 gap-8 border-t border-text pt-6">
            <div>
              <p className="text-sm font-bold uppercase mb-2 flex items-center gap-2"><Hash className="w-4 h-4" /> Problem</p>
              <p className="text-lg leading-snug text-text-muted">AI hallucinations due to missing context.</p>
            </div>
            <div>
              <p className="text-sm font-bold uppercase mb-2 flex items-center gap-2"><LayoutGrid className="w-4 h-4" /> Solution</p>
              <p className="text-lg leading-snug text-text-muted">Semantic indexing on your own machine.</p>
            </div>
          </div>
        </div>
        <div className="col-span-12 md:col-span-4 bg-primary p-8 flex flex-col justify-between text-white">
          <div className="text-6xl font-bold"><LayoutGrid className="w-16 h-16" /></div>
          <div className="space-y-4">
            <p className="text-2xl font-medium">Prep v1.0</p>
            <p className="opacity-80">International Typographic Style applied to developer tools.</p>
            <button className="mt-8 bg-white text-primary px-6 py-3 rounded-full font-bold w-full flex items-center justify-between group">
              Get Started <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
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
            <Zap className="w-4 h-4 text-warning" /> The future of local search
          </Badge>

          <h1 className="text-5xl md:text-7xl font-bold text-text bg-clip-text text-transparent bg-gradient-to-r from-text to-primary mb-6">
            Crystal Clear Context
          </h1>

          <p className="text-xl text-text-muted mb-8 max-w-2xl mx-auto">
            A beautiful, translucent layer between your code and your AI.
            See through the noise with semantic understanding.
          </p>

          <Flex className="gap-4" justifyContent="center">
            <button className="backdrop-blur-md bg-primary/80 hover:bg-primary text-white px-8 py-4 rounded-xl font-semibold transition-all shadow-lg hover:shadow-primary/30 border border-white/20">
              Download Beta
            </button>
            <button className="backdrop-blur-md bg-white/40 hover:bg-white/60 text-text px-8 py-4 rounded-xl font-semibold transition-all border border-white/40">
              Explore Features
            </button>
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
          PREP
        </h1>
        <p className="text-2xl text-primary font-bold tracking-[0.5em] mt-2 mb-12 uppercase drop-shadow-md">
          System Online
        </p>

        <div className="max-w-3xl mx-auto bg-black/50 backdrop-blur-sm border border-primary/50 p-6 rounded-lg shadow-[0_0_30px_rgba(255,0,255,0.2)]">
          <p className="text-lg text-white font-mono leading-relaxed">
            <span className="text-success">INITIALIZING...</span><br />
            &gt; LOCAL INDEX: <span className="text-success">ONLINE</span><br />
            &gt; CLOUD UPLOAD: <span className="text-error">DISABLED</span><br />
            &gt; SYMBOL TRACING: <span className="text-info">ACTIVE</span><br /><br />
            <span className="animate-pulse flex items-center justify-center gap-2">_READY FOR INPUT <Terminal className="w-4 h-4" /></span>
          </p>
        </div>

        <button className="mt-12 bg-transparent border-2 border-primary text-primary hover:bg-primary hover:text-white px-10 py-4 text-xl font-bold uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(255,0,255,0.4)] hover:shadow-[0_0_40px_rgba(255,0,255,0.8)]">
          Jack In
        </button>
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
          <Zap className="w-4 h-4" /> Now in Public Beta
        </Badge>

        <h1 className="text-4xl md:text-5xl font-bold text-text leading-tight">
          Your code. <br />
          <span className="text-primary">Your context.</span> <br />
          Your machine.
        </h1>

        <p className="mt-6 text-lg text-text-muted leading-relaxed">
          Stop wrestling with AI hallucinations. Prep builds a semantic index
          of your codebase and delivers precisely relevant context—locally and instantly.
        </p>

        <div className="mt-8 space-y-4">
          <FeaturePoint icon={<Search className="w-5 h-5 text-primary" />} text="Semantic search across all your projects" />
          <FeaturePoint icon={<Layers className="w-5 h-5 text-primary" />} text="Trace-aware context with symbol relationships" />
          <FeaturePoint icon={<Zap className="w-5 h-5 text-primary" />} text="Sub-100ms search, works completely offline" />
          <FeaturePoint icon={<Shield className="w-5 h-5 text-primary" />} text="Your code never leaves your machine" />
        </div>

        <Flex className="mt-10 gap-4">
          <Button className="bg-primary hover:bg-primary-hover text-white px-6 py-2.5 font-semibold">
            Get Early Access
          </Button>
          <Button variant="secondary" className="border border-border px-6 py-2.5">
            Watch Demo
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
              <Code className="w-3 h-3" /> Experimental Build v0.9
            </span>
          </div>

          <h1 className="text-6xl md:text-8xl font-serif text-text leading-[0.9] tracking-tight">
            Code as <br />
            <span className="italic text-primary">material.</span>
          </h1>

          <div className="max-w-md bg-surface/80 backdrop-blur-sm p-6 border-l-4 border-primary mt-8">
            <p className="text-lg font-sans text-text leading-relaxed">
              Prep reclaims your codebase from the cloud. A local-first studio for
              semantic indexing and intelligent retrieval.
            </p>
          </div>

          <div className="flex gap-4 pt-4">
            <button className="px-8 py-3 bg-text text-background font-mono text-sm hover:bg-primary transition-colors flex items-center gap-2">
              <Download className="w-4 h-4" /> [ DOWNLOAD_STUDIO ]
            </button>
            <button className="px-8 py-3 border border-text text-text font-serif italic hover:bg-surface-raised transition-colors flex items-center gap-2">
              Read the manifesto <ArrowRight className="w-4 h-4" />
            </button>
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
            <h3 className="font-serif text-2xl italic mb-2 flex items-center gap-2"><Eye className="w-5 h-5" /> Context Awareness</h3>
            <p className="font-sans text-sm text-text-muted">
              The machine sees what you see. Local traces enable deep understanding without data egress.
            </p>
          </div>

          <div className="absolute bottom-10 right-20 w-40 h-40 border-4 border-primary rounded-full flex items-center justify-center bg-background/50 backdrop-blur-sm z-30">
            <span className="font-mono text-xs text-center font-bold">
              100%<br />LOCAL<br />STORAGE
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
              <Command className="w-4 h-4" /> Prep Systems
            </span>
          </div>
          <div className="col-span-12 md:col-span-6">
            <h1 className="font-sans text-5xl md:text-6xl font-normal text-text leading-tight tracking-tight mb-8">
              Semantic indexing infrastructure for local development environments.
            </h1>
          </div>
          <div className="col-span-12 md:col-span-3 flex flex-col justify-end items-start md:items-end">
            <span className="font-mono text-xs text-text-muted mb-2">RELEASE 2025.1</span>
            <span className="font-mono text-xs text-text-muted">MACOS / LINUX</span>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-x-6 pt-12">
          {/* Column 1: Description */}
          <div className="col-span-12 md:col-span-3 md:col-start-4">
            <p className="font-sans text-base text-text leading-relaxed mb-6">
              Prep provides a unified interface for code retrieval and generation
              context, operating entirely within the local filesystem to ensure data sovereignty.
            </p>
            <a href="#" className="font-sans font-medium text-primary hover:underline underline-offset-4 decoration-2 flex items-center gap-1">
              Documentation <ArrowRight className="w-3 h-3" />
            </a>
          </div>

          {/* Column 2: Specs */}
          <div className="col-span-12 md:col-span-3">
            <ul className="space-y-4 font-mono text-sm text-text border-l border-border pl-6">
              <li className="flex justify-between">
                <span>Latency</span>
                <span className="text-text-muted">&lt;100ms</span>
              </li>
              <li className="flex justify-between">
                <span>Index</span>
                <span className="text-text-muted">Vector + Trace</span>
              </li>
              <li className="flex justify-between">
                <span>Model</span>
                <span className="text-text-muted">Nomic Embed</span>
              </li>
              <li className="flex justify-between">
                <span>Network</span>
                <span className="text-text-muted">Offline</span>
              </li>
            </ul>
          </div>

          {/* Column 3: Action - Removed "Card", just text and minimal buttons */}
          <div className="col-span-12 md:col-span-3 flex flex-col justify-between">
            <div className="pl-6 md:border-l md:border-border">
              <span className="font-sans font-bold text-sm mb-4 block">Get Started</span>
              <div className="flex flex-col gap-2">
                <button className="text-left py-2 font-sans font-medium text-sm hover:text-primary transition-colors flex items-center gap-2">
                  <Download className="w-4 h-4" /> Download Installer
                </button>
                <button className="text-left py-2 font-sans font-medium text-sm hover:text-primary transition-colors flex items-center gap-2">
                  <Code className="w-4 h-4" /> View Source
                </button>
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
          <span>Accessible Context Intelligence</span>
        </div>

        <h1 className="text-5xl md:text-7xl font-bold text-text mb-8 tracking-tight">
          Clear code context.<br />
          <span className="text-primary underline decoration-4 underline-offset-8 decoration-primary/30">Zero distractions.</span>
        </h1>

        <p className="text-xl md:text-2xl text-text-muted max-w-2xl mx-auto mb-12 leading-relaxed font-medium">
          Prep helps you focus by handling the complexity of code context automatically.
          Local, fast, and designed for clarity.
        </p>

        <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
          <button className="w-full sm:w-auto px-8 py-4 bg-primary text-white text-lg font-bold rounded-lg hover:bg-primary-hover focus:ring-4 focus:ring-primary/50 transition-all shadow-lg transform hover:-translate-y-1">
            Install for macOS
          </button>
          <button className="w-full sm:w-auto px-8 py-4 bg-surface text-text border-2 border-text text-lg font-bold rounded-lg hover:bg-surface-raised focus:ring-4 focus:ring-text/30 transition-all">
            View Live Demo
          </button>
        </div>

        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
          <div className="bg-surface p-6 rounded-xl border border-border shadow-sm">
            <div className="w-12 h-12 bg-success/20 rounded-lg flex items-center justify-center text-2xl mb-4 text-success"><Lock className="w-6 h-6" /></div>
            <h3 className="font-bold text-lg text-text mb-2">Private by Design</h3>
            <p className="text-text-muted">Your code never leaves your device. We prioritize privacy and security first.</p>
          </div>
          <div className="bg-surface p-6 rounded-xl border border-border shadow-sm">
            <div className="w-12 h-12 bg-warning/20 rounded-lg flex items-center justify-center text-2xl mb-4 text-warning"><Zap className="w-6 h-6" /></div>
            <h3 className="font-bold text-lg text-text mb-2">Instant Retrieval</h3>
            <p className="text-text-muted">Sub-100ms semantic search means you never lose your flow state.</p>
          </div>
          <div className="bg-surface p-6 rounded-xl border border-border shadow-sm">
            <div className="w-12 h-12 bg-primary/20 rounded-lg flex items-center justify-center text-2xl mb-4 text-primary"><Eye className="w-6 h-6" /></div>
            <h3 className="font-bold text-lg text-text mb-2">High Visibility</h3>
            <p className="text-text-muted">Trace-aware visualization shows you exactly how your code connects.</p>
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
          <span className="font-mono font-bold text-lg tracking-tight flex items-center gap-2"><LayoutGrid className="w-5 h-5" /> Prep</span>
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
              Scale your development context securely.
            </h1>
            <p className="text-text-muted text-lg leading-relaxed">
              Standardize semantic indexing across your engineering organization.
              Enforce governance, manage access, and accelerate onboarding with shared context layers.
            </p>
          </div>

          <div className="space-y-4 mb-8">
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-primary shadow-sm">
              <span className="text-primary font-bold">01</span>
              <span className="font-medium text-text">Centralized Governance & Compliance</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-border shadow-sm opacity-70">
              <span className="text-text-subtle font-bold">02</span>
              <span className="font-medium text-text">On-Premise Deployment Options</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-border shadow-sm opacity-70">
              <span className="text-text-subtle font-bold">03</span>
              <span className="font-medium text-text">SSO & Audit Logging</span>
            </div>
          </div>

          <button className="bg-primary text-white px-6 py-3 font-medium text-sm w-fit hover:bg-primary-hover shadow-sm">
            Contact Sales
          </button>
        </div>

        {/* Right: Dashboard Preview */}
        <div className="col-span-12 md:col-span-7">
          <div className="bg-background border border-border shadow-md rounded-sm overflow-hidden h-full flex flex-col">
            <div className="bg-surface-raised border-b border-border p-3 flex justify-between items-center">
              <span className="font-mono text-xs text-text-muted flex items-center gap-2"><Lock className="w-3 h-3" /> admin_console</span>
              <div className="flex gap-2">
                <span className="w-3 h-3 bg-border rounded-full"></span>
                <span className="w-3 h-3 bg-border rounded-full"></span>
              </div>
            </div>

            <div className="p-6 grid grid-cols-2 gap-4">
              <div className="col-span-2 bg-surface border border-border p-4">
                <div className="text-xs text-text-subtle uppercase mb-2">Total Context Usage</div>
                <div className="h-32 flex items-end gap-2">
                  <div className="w-full bg-primary/20 h-[40%] relative"><div className="absolute top-0 w-full h-1 bg-primary"></div></div>
                  <div className="w-full bg-primary/20 h-[60%] relative"><div className="absolute top-0 w-full h-1 bg-primary"></div></div>
                  <div className="w-full bg-primary/20 h-[55%] relative"><div className="absolute top-0 w-full h-1 bg-primary"></div></div>
                  <div className="w-full bg-primary/20 h-[80%] relative"><div className="absolute top-0 w-full h-1 bg-primary"></div></div>
                  <div className="w-full bg-primary/20 h-[75%] relative"><div className="absolute top-0 w-full h-1 bg-primary"></div></div>
                </div>
              </div>

              <div className="bg-surface border border-border p-4">
                <div className="text-xs text-text-subtle uppercase mb-1">Active Seats</div>
                <div className="text-3xl font-mono font-medium text-text">1,248</div>
                <div className="text-xs text-success mt-1">+12% vs last month</div>
              </div>

              <div className="bg-surface border border-border p-4">
                <div className="text-xs text-text-subtle uppercase mb-1">System Status</div>
                <div className="text-lg font-medium text-text flex items-center gap-2">
                  <span className="w-2 h-2 bg-success rounded-full"></span>
                  Operational
                </div>
                <div className="text-xs text-text-subtle mt-1">Uptime: 99.99%</div>
              </div>

              <div className="col-span-2 bg-surface border border-border p-4">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="text-text-subtle border-b border-border">
                      <th className="pb-2 font-medium">Project</th>
                      <th className="pb-2 font-medium">Owner</th>
                      <th className="pb-2 font-medium">Size</th>
                      <th className="pb-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="text-text">
                    <tr className="border-b border-border-subtle">
                      <td className="py-2">frontend-core</td>
                      <td className="py-2 text-text-muted">@sarah</td>
                      <td className="py-2">4.2 GB</td>
                      <td className="py-2 text-success">Synced</td>
                    </tr>
                    <tr className="border-b border-border-subtle">
                      <td className="py-2">backend-api</td>
                      <td className="py-2 text-text-muted">@mike</td>
                      <td className="py-2">1.8 GB</td>
                      <td className="py-2 text-warning">Indexing</td>
                    </tr>
                    <tr>
                      <td className="py-2">data-pipeline</td>
                      <td className="py-2 text-text-muted">@team-data</td>
                      <td className="py-2">12.5 GB</td>
                      <td className="py-2 text-success">Synced</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


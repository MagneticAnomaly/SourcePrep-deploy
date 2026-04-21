"use client";

import { Button } from '../../primitives/Button';
import { Terminal } from 'lucide-react';

export function RetroHero({ isBetaMode }: { isBetaMode: boolean }) {
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
          Context Engine
        </p>

        <div className="max-w-3xl mx-auto bg-black/50 backdrop-blur-sm border border-primary/50 p-6 rounded-lg shadow-[0_0_30px_rgba(255,0,255,0.2)]">
          <p className="text-lg text-white font-mono leading-relaxed">
            <span className="text-success">SYSTEM_INIT...</span><br/>
            &gt; TRACE_INDEX: <span className="text-success">RUST_CORE READY (72ms)</span><br/>
            &gt; MCP_SERVER: <span className="text-info">LISTENING ON :8400</span><br/>
            &gt; TOOLS_LOADED: <span className="text-warning">prep (context), search, trace</span><br/>
            &gt; INTEGRATIONS: <span className="text-success">CURSOR=OK WINDSURF=OK CLAUDE=OK</span><br/><br/>
            <span className="animate-pulse flex items-center justify-center gap-2">_WAITING FOR EDITOR COMMAND... <Terminal className="w-4 h-4" /></span>
          </p>
        </div>

        {isBetaMode ? (
          <Button 
            className="mt-12 bg-transparent border-2 border-primary text-primary hover:bg-primary hover:text-background px-10 py-4 text-xl font-bold uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(255,0,255,0.4)] hover:shadow-[0_0_40px_rgba(255,0,255,0.8)] rounded-none h-auto"
            asChild
          >
            <a href="mailto:support@runprep.io?subject=Prep%20Beta%20Access%20Request">Join Beta</a>
          </Button>
        ) : (
          <Button 
            className="mt-12 bg-transparent border-2 border-primary text-primary hover:bg-primary hover:text-background px-10 py-4 text-xl font-bold uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(255,0,255,0.4)] hover:shadow-[0_0_40px_rgba(255,0,255,0.8)] rounded-none h-auto"
            asChild
          >
            <a href="/download">Get Prep</a>
          </Button>
        )}
      </div>
    </div>
  );
}

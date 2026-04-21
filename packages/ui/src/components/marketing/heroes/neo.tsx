"use client";

import { Button } from '../../primitives/Button';
import { AlertTriangle, Download, FileText, Terminal } from 'lucide-react';

export function NeoBrutalistHero({ isBetaMode }: { isBetaMode: boolean }) {
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
            Prep adds the structural layer your AI tools are missing.
            Imports, calls, symbol graphs — indexed in Rust, instantly served.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row gap-4">
            {isBetaMode ? (
              <Button 
                size="lg"
                className="border-2 border-border bg-primary text-background font-bold text-lg hover:translate-x-1 hover:translate-y-1 hover:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all rounded-none"
                icon={Download}
                asChild
              >
                <a href="mailto:support@runprep.io?subject=Prep%20Beta%20Access%20Request">JOIN_BETA</a>
              </Button>
            ) : (
              <Button 
                size="lg"
                className="border-2 border-border bg-primary text-background font-bold text-lg hover:translate-x-1 hover:translate-y-1 hover:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all rounded-none"
                icon={Download}
                asChild
              >
                <a href="/download">GET_PREP</a>
              </Button>
            )}
            <Button 
              size="lg"
              variant="outline"
              className="border-2 border-border bg-surface text-text font-bold text-lg hover:translate-x-1 hover:translate-y-1 hover:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all rounded-none"
              icon={FileText}
              asChild
            >
              <a href="/docs">SEE_HOW_IT_WORKS</a>
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
                {`"prep": { "url": "http://localhost:8400/mcp/sse", "transport": "sse" }`}
              </div>
              
              <div className="text-success">$ cascade_agent --connect prep</div>
              <div className="text-text-muted">[mcp] tools loaded: prep (primary), prep_search, prep_trace</div>
              
              <div className="mt-4">
                <span className="text-primary font-bold">USER:</span> "Graph the auth flow and find where tokens expire"
              </div>
              
              <div className="bg-primary/10 p-2 border-l-2 border-primary mt-2">
                <div className="text-xs text-text-subtle mb-1">TOOL CALL: prep(trace_expand=true)</div>
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

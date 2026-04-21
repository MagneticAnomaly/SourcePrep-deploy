import React from "react";
import { VsCodeApi } from "../global";
import { Network, Lock } from "lucide-react";
import { Button } from "@prep/ui";

interface TracePanelProps {
  data: any;
  vscode: VsCodeApi;
}

export const TracePanel: React.FC<TracePanelProps> = ({ data, vscode }) => {
  const isFree = data?.isFree ?? true;
  const results = data?.nodes || [];
  const query = data?.query || "";

  if (!isFree) {
    return (
      <div className="p-4 h-screen flex flex-col">
        <div className="mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Network className="w-5 h-5" />
            Trace: "{query}"
          </h2>
          <p className="text-xs opacity-70">{results.length} nodes found</p>
        </div>
        <div className="flex-1 overflow-auto bg-[var(--vscode-editor-background)] border border-[var(--vscode-editorWidget-border)] rounded-md p-4">
          <pre className="text-xs font-mono whitespace-pre-wrap">
            {JSON.stringify(results, null, 2)}
          </pre>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 h-screen flex flex-col items-center justify-center text-center">
      <div className="relative mb-6">
        <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full"></div>
        <Network className="w-16 h-16 stroke-1 text-[var(--vscode-textLink-foreground)] relative z-10" />
        <div className="absolute -top-2 -right-2 bg-[var(--vscode-statusBarItem-errorBackground)] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full flex items-center gap-1">
          <Lock className="w-3 h-3" />
          PRO
        </div>
      </div>
      
      <h2 className="text-2xl font-bold mb-2">Trace Index</h2>
      <p className="text-[var(--vscode-descriptionForeground)] max-w-sm mb-8">
        Understand your codebase structure with graph-based trace analysis. Navigate calls, imports, and dependencies visually.
      </p>
      
      <div className="bg-[var(--vscode-editorWidget-background)] border border-[var(--vscode-editorWidget-border)] rounded-lg p-6 max-w-sm w-full mb-8 text-left">
        <h3 className="font-semibold mb-4 text-sm uppercase tracking-wider opacity-80">Pro Features</h3>
        <ul className="space-y-3 text-sm">
          <li className="flex items-center gap-2">
            <CheckIcon />
            <span>Structural Code Graph</span>
          </li>
          <li className="flex items-center gap-2">
            <CheckIcon />
            <span>Symbol & Reference Search</span>
          </li>
          <li className="flex items-center gap-2">
            <CheckIcon />
            <span>Dependency Visualization</span>
          </li>
          <li className="flex items-center gap-2">
            <CheckIcon />
            <span>Deep Context Expansion</span>
          </li>
        </ul>
      </div>
      
      <Button 
        size="lg"
        onClick={() => {
          vscode.postMessage({ command: "openPricing" });
        }}
      >
        Upgrade to Pro
      </Button>
    </div>
  );
};

function CheckIcon() {
  return (
    <svg className="w-4 h-4 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

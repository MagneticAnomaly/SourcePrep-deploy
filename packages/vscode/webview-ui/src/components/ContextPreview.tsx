import React, { useState } from "react";
import { VsCodeApi } from "../global";
import { Copy, Check, FileCode } from "lucide-react";
import { Button } from "@codrag/ui";

interface ContextChunk {
  content?: string;
  source_path?: string;
  score?: number;
}

interface ContextResponse {
  context: string;
  chunks?: ContextChunk[];
  total_chars?: number;
  estimated_tokens?: number;
}

interface ContextPreviewProps {
  data: {
    query: string;
    response: ContextResponse;
  };
  vscode: VsCodeApi;
}

export const ContextPreview: React.FC<ContextPreviewProps> = ({ data }) => {
  const { query, response } = data || { query: "", response: { context: "" } };
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(response.context).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const chars = response.total_chars ?? response.context.length;
  const tokens = response.estimated_tokens ?? Math.ceil(chars / 4);

  return (
    <div className="p-4 h-screen flex flex-col">
      <div className="mb-4 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FileCode className="w-5 h-5" />
            Assembled Context
          </h2>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleCopy}
            className="gap-2"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        
        <div className="flex items-center justify-between bg-[var(--vscode-editorWidget-background)] p-3 rounded-md border border-[var(--vscode-editorWidget-border)]">
          <div className="flex flex-col gap-1">
            <span className="text-xs opacity-60 uppercase font-bold tracking-wider">Query</span>
            <span className="text-sm font-mono truncate max-w-[300px]" title={query}>{query}</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex flex-col items-end gap-1">
              <span className="text-xs opacity-60 uppercase font-bold tracking-wider">Chars</span>
              <span className="text-sm font-mono">{chars.toLocaleString()}</span>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="text-xs opacity-60 uppercase font-bold tracking-wider">Tokens</span>
              <span className="text-sm font-mono">~{tokens.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 relative border border-[var(--vscode-editorWidget-border)] rounded-md bg-[var(--vscode-editor-background)]">
        <div className="absolute inset-0 overflow-auto p-4">
          <pre className="font-mono text-xs whitespace-pre-wrap break-all text-[var(--vscode-editor-foreground)]">
            {response.context}
          </pre>
        </div>
      </div>
    </div>
  );
};

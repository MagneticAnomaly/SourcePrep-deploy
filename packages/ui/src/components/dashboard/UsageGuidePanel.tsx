import { cn } from '../../lib/utils';
import { ExternalLink, Copy, Check } from 'lucide-react';
import { useState, useCallback } from 'react';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface UsageGuidePanelProps {
  className?: string;
  bare?: boolean;
  docsUrl?: string;
}

const MCP_TOOLS = [
  {
    name: 'codrag',
    description: 'Get assembled context for your current task — the primary tool your AI uses.',
    example: '"Use codrag to understand this codebase"',
    primary: true,
  },
  {
    name: 'codrag_search',
    description: 'Semantic search across your indexed code and docs.',
    example: '"Use codrag_search to find authentication logic"',
  },
  {
    name: 'codrag_status',
    description: 'Check if CoDRAG is connected and the index is ready.',
    example: '"Use codrag_status to check the index"',
  },
  {
    name: 'codrag_build',
    description: 'Trigger an index rebuild when your code has changed.',
    example: '"Use codrag_build to re-index the project"',
  },
  {
    name: 'codrag_trace_search',
    description: 'Search the structural code graph for symbols (functions, classes, modules).',
    example: '"Use codrag_trace_search to find the UserService class"',
  },
  {
    name: 'codrag_trace_neighbors',
    description: 'Explore imports, callers, and callees of a symbol in the code graph.',
    example: '"Use codrag_trace_neighbors to see what calls handleAuth"',
  },
  {
    name: 'codrag_trace_coverage',
    description: 'Check which files are traced, stale, or missing from the code graph.',
    example: '"Use codrag_trace_coverage to check graph completeness"',
  },
];

function CopyBadge({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 font-mono text-xs px-2 py-1 rounded bg-surface-raised border border-border hover:border-primary/40 hover:bg-primary/5 transition-colors cursor-pointer group"
      title={`Copy "${text}"`}
    >
      <span className="text-primary font-semibold">{text}</span>
      {copied ? (
        <Check className="w-3 h-3 text-success" />
      ) : (
        <Copy className="w-3 h-3 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </button>
  );
}

export function UsageGuidePanel({ className, bare = false, docsUrl = 'https://docs.codrag.io' }: UsageGuidePanelProps) {
  return (
    <div className={cn(
      !bare && 'border border-border bg-surface shadow-sm rounded-lg p-4',
      className
    )}>
      {!bare && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-text">Quick Start</h3>
            <InfoTooltip 
              content="Learn how to invoke CoDRAG tools." 
              href="https://docs.codrag.io/getting-started/quick-start" 
            />
          </div>
        </div>
      )}

      <div className="space-y-4">
        {/* Intro */}
        <p className="text-xs text-text-muted leading-relaxed">
          CoDRAG serves context to your AI tools via <span className="font-semibold text-text">MCP</span> (Model Context Protocol).
          Just ask your AI assistant to use these tools by name.
        </p>

        {/* Primary tool highlight */}
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <CopyBadge text={MCP_TOOLS[0].name} />
            <span className="text-[10px] font-medium uppercase tracking-wider text-primary">Most used</span>
          </div>
          <p className="text-xs text-text-muted">{MCP_TOOLS[0].description}</p>
          <p className="text-[11px] text-text-muted/70 italic">{MCP_TOOLS[0].example}</p>
        </div>

        {/* Other tools */}
        <div className="space-y-1.5">
          {MCP_TOOLS.slice(1).map((tool) => (
            <div key={tool.name} className="flex items-start gap-2 py-1.5">
              <CopyBadge text={tool.name} />
              <span className="text-xs text-text-muted leading-snug pt-0.5">{tool.description}</span>
            </div>
          ))}
        </div>

        {/* Docs link */}
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors font-medium"
        >
          Read the full documentation
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}

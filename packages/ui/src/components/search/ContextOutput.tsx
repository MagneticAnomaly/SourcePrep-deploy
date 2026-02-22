import { useState } from 'react';
import { cn } from '../../lib/utils';
import { FileText, Map, ChevronDown, ChevronUp } from 'lucide-react';
import { Card, Title, Flex, Badge } from '@tremor/react';

export interface ContextMeta {
  chunks?: { source_path: string; section: string; score: number; truncated: boolean }[];
  total_chars?: number;
  estimated_tokens?: number;
}

export interface ContextOutputProps {
  context: string;
  meta?: ContextMeta | null;
  className?: string;
  bare?: boolean;
}

/**
 * Regex to extract an [ATLAS] block from context text.
 * The Atlas block starts with "[ATLAS]" and ends before the next "---" separator.
 */
const ATLAS_BLOCK_RE = /\[ATLAS\][^\n]*\n([\s\S]*?)(?=\n---\n|$)/;

/**
 * ContextOutput - Displays assembled context with metadata.
 * 
 * Features:
 * - Monospace code display
 * - Metadata bar (chunks, chars, tokens)
 * - Scrollable content area
 * - Collapsible Atlas block with styled left border
 */
export function ContextOutput({
  context,
  meta,
  className,
  bare = false,
}: ContextOutputProps) {
  const [atlasExpanded, setAtlasExpanded] = useState(true);

  if (!context) {
    return null;
  }

  // Extract Atlas block from context text
  const atlasMatch = context.match(ATLAS_BLOCK_RE);
  const atlasContent = atlasMatch ? atlasMatch[1].trim() : null;
  // Context with Atlas block removed (for separate rendering)
  const contextWithoutAtlas = atlasContent
    ? context.replace(ATLAS_BLOCK_RE, '').replace(/^\n---\n/, '').trim()
    : context;

  const Container = bare ? 'div' : Card;

  return (
    <Container className={cn(!bare && 'border border-border bg-surface shadow-sm', className)}>
      {!bare && (
        <Flex justifyContent="between" alignItems="center" className="mb-4">
          <Flex justifyContent="start" alignItems="center" className="gap-2">
            <FileText className="w-5 h-5 text-primary" />
            <Title className="text-text">Prompt Buffer</Title>
          </Flex>
          {meta && (
            <Flex justifyContent="end" className="gap-2">
               <Badge color="gray" size="xs">{meta.chunks?.length ?? 0} chunks</Badge>
               <Badge color="gray" size="xs">{meta.total_chars?.toLocaleString()} chars</Badge>
               <Badge color="blue" size="xs">~{meta.estimated_tokens?.toLocaleString()} tokens</Badge>
            </Flex>
          )}
        </Flex>
      )}

      {/* Atlas block — collapsible, styled distinctly */}
      {atlasContent && (
        <div className="mb-3 rounded-lg border border-primary/20 bg-primary/5 overflow-hidden">
          <button
            onClick={() => setAtlasExpanded(!atlasExpanded)}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10 transition-colors"
          >
            <Map className="w-3.5 h-3.5" />
            <span>ATLAS</span>
            <Badge color="blue" size="xs" className="ml-1">{atlasContent.length} chars</Badge>
            <span className="flex-1" />
            {atlasExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {atlasExpanded && (
            <div className="border-l-2 border-primary/40 mx-3 mb-3">
              <pre className="pl-3 pr-2 py-2 text-xs whitespace-pre-wrap font-mono text-text overflow-y-auto max-h-48 custom-scrollbar">
                {atlasContent}
              </pre>
            </div>
          )}
        </div>
      )}
      
      <div className={cn(
        "bg-surface-raised border border-border rounded-lg overflow-hidden",
        bare && "h-full"
      )}>
        <pre className={cn(
          "p-4 text-xs whitespace-pre-wrap font-mono text-text overflow-y-auto custom-scrollbar",
          bare ? "h-full" : "max-h-96"
        )}>
          {contextWithoutAtlas}
        </pre>
      </div>
    </Container>
  );
}

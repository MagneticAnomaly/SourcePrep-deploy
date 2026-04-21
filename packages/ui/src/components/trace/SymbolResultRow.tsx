import { Badge } from '@tremor/react';
import { cn } from '../../lib/utils';
import type { TraceNode } from '../../types';

export interface SymbolResultRowProps {
  node: TraceNode;
  onClick?: () => void;
  selected?: boolean;
  className?: string;
}

const kindColors: Record<string, 'blue' | 'green' | 'gray'> = {
  symbol: 'blue',
  file: 'green',
  external_module: 'gray',
};

const symbolTypeLabels: Record<string, string> = {
  function: 'fn',
  class: 'class',
  method: 'method',
  module: 'mod',
};

export function SymbolResultRow({
  node,
  onClick,
  selected = false,
  className,
}: SymbolResultRowProps) {
  const symbolType = node.metadata.symbol_type as string | undefined;
  
  return (
    <div
      onClick={onClick}
      className={cn(
        'prep-symbol-result-row cursor-pointer rounded border p-3 transition-colors',
        selected
          ? 'border-primary bg-primary/5 shadow-md'
          : 'border-border-subtle bg-surface-raised hover:border-border hover:shadow-sm',
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono font-medium truncate">{node.name}</span>
            {symbolType && (
              <Badge size="xs" color={kindColors[node.kind] || 'gray'}>
                {symbolTypeLabels[symbolType] || symbolType}
              </Badge>
            )}
            {node.metadata.is_async && (
              <Badge size="xs" color="blue">async</Badge>
            )}
          </div>
          
          <p className="text-xs text-gray-500 truncate mt-1">
            {node.file_path}
            {node.span && `:${node.span.start_line}-${node.span.end_line}`}
          </p>
          
          {node.metadata.docstring && (
            <p className="text-xs text-gray-400 truncate mt-1">
              {(node.metadata.docstring as string).slice(0, 100)}
            </p>
          )}
        </div>
        
        {node.language && (
          <Badge size="xs" color="gray">{node.language}</Badge>
        )}
      </div>
    </div>
  );
}

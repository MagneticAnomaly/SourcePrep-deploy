import { TextInput, Select, SelectItem } from '@tremor/react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { NodeKind } from '../../types';

export interface SymbolSearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  kindFilter?: NodeKind | 'all';
  onKindFilterChange?: (kind: NodeKind | 'all') => void;
  loading?: boolean;
  placeholder?: string;
  className?: string;
}

export function SymbolSearchInput({
  value,
  onChange,
  onSubmit,
  kindFilter = 'all',
  onKindFilterChange,
  loading = false,
  placeholder = 'Search symbols...',
  className,
}: SymbolSearchInputProps) {
  return (
    <div className={cn('prep-symbol-search flex gap-3', className)}>
      <div className="flex-1">
        <TextInput
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSubmit?.()}
          disabled={loading}
        />
      </div>
      
      {onKindFilterChange && (
        <Select
          value={kindFilter}
          onValueChange={(val) => onKindFilterChange(val as NodeKind | 'all')}
          className="w-36"
        >
          <SelectItem value="all">All</SelectItem>
          <SelectItem value="symbol">Symbols</SelectItem>
          <SelectItem value="file">Files</SelectItem>
        </Select>
      )}
      
      {loading && (
        <div className="flex items-center px-1">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
        </div>
      )}
    </div>
  );
}

import { Search } from 'lucide-react';
import { Card, Flex, Title, TextInput } from '@tremor/react';
import { Button } from '../primitives/Button';
import { StepperNumberInput } from '../primitives/StepperNumberInput';
import { InfoTooltip } from '../primitives/InfoTooltip';
import { cn } from '../../lib/utils';
import type { KeyboardEvent } from 'react';

export interface SearchPanelProps {
  query: string;
  onQueryChange: (value: string) => void;
  k: number;
  onKChange: (value: number) => void;
  minScore: number;
  onMinScoreChange: (value: number) => void;
  onSearch: () => void;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  bare?: boolean;
}

/**
 * SearchPanel - Search input with configurable parameters.
 * 
 * Provides:
 * - Query text input with Enter key support
 * - Number of results (k) input
 * - Minimum score threshold input
 * - Search button with loading state
 */
export function SearchPanel({
  query,
  onQueryChange,
  k,
  onKChange,
  minScore,
  onMinScoreChange,
  onSearch,
  loading = false,
  disabled = false,
  className,
  bare = false,
}: SearchPanelProps) {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !loading && !disabled && query.trim()) {
      onSearch();
    }
  };

  const Container = bare ? 'div' : Card;

  return (
    <Container className={cn(!bare && "border border-border bg-surface shadow-sm", className)}>
      {!bare && (
        <Flex justifyContent="between" alignItems="center" className="mb-4">
          <div className="flex items-center gap-2">
            <Search className="w-5 h-5 text-primary" />
            <Title className="text-text">Knowledge Query</Title>
            <InfoTooltip 
              content="Learn how semantic search works." 
              href="https://docs.codrag.io/concepts/indexing" 
            />
          </div>
        </Flex>
      )}

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-text-muted mb-2">
            Concept / Question
          </label>
          <TextInput
            icon={Search}
            value={query}
            onValueChange={onQueryChange}
            onKeyDown={handleKeyDown}
            placeholder="Search for concepts, definitions, or questions..."
            disabled={disabled}
            className="w-full"
          />
        </div>
        
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[12rem]">
            <div className="flex items-center gap-2 mb-2">
              <label className="block text-sm font-medium text-text-muted">
                Results (K)
              </label>
              <InfoTooltip content="The maximum number of relevant code chunks to retrieve from the knowledge base." />
            </div>
            <StepperNumberInput value={k} onValueChange={onKChange} min={1} max={50} disabled={disabled} />
          </div>
          <div className="flex-1 min-w-[12rem]">
            <div className="flex items-center gap-2 mb-2">
              <label className="block text-sm font-medium text-text-muted">
                Min Score
              </label>
              <InfoTooltip content="Relevance threshold (0.0 - 1.0). Higher values return fewer, more precise results. Lower values include more broad matches." />
            </div>
            <StepperNumberInput value={minScore} onValueChange={onMinScoreChange} min={0} max={1} step={0.05} disabled={disabled} />
          </div>
          <Button
            onClick={onSearch}
            disabled={loading || disabled || !query.trim()}
            className="px-8"
            loading={loading}
          >
            {loading ? 'Searching...' : 'Search'}
          </Button>
        </div>
      </div>
    </Container>
  );
}

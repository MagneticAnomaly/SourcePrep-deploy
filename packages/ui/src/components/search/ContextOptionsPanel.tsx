import { Copy, Settings2 } from 'lucide-react';
import { Card, Title, Text, Flex, Switch } from '@tremor/react';
import { Button } from '../primitives/Button';
import { StepperNumberInput } from '../primitives/StepperNumberInput';
import { InfoTooltip } from '../primitives/InfoTooltip';
import { cn } from '../../lib/utils';

export interface ContextOptionsPanelProps {
  k: number;
  onKChange: (value: number) => void;
  maxChars: number;
  onMaxCharsChange: (value: number) => void;
  includeSources: boolean;
  onIncludeSourcesChange: (value: boolean) => void;
  includeScores: boolean;
  onIncludeScoresChange: (value: boolean) => void;
  structured: boolean;
  onStructuredChange: (value: boolean) => void;
  includeAtlas?: boolean;
  onIncludeAtlasChange?: (value: boolean) => void;
  onGetContext: () => void;
  onCopyContext?: () => void;
  hasContext?: boolean;
  disabled?: boolean;
  className?: string;
  bare?: boolean;
}

/**
 * ContextOptionsPanel - Controls for context assembly.
 * 
 * Provides:
 * - k (number of chunks) input
 * - max_chars limit input
 * - include_sources toggle
 * - include_scores toggle
 * - structured response toggle
 * - Get Context / Copy buttons
 */
export function ContextOptionsPanel({
  k,
  onKChange,
  maxChars,
  onMaxCharsChange,
  includeSources,
  onIncludeSourcesChange,
  includeScores,
  onIncludeScoresChange,
  structured,
  onStructuredChange,
  includeAtlas = true,
  onIncludeAtlasChange,
  onGetContext,
  onCopyContext,
  hasContext = false,
  disabled = false,
  className,
  bare = false,
}: ContextOptionsPanelProps) {
  const Container = bare ? 'div' : Card;

  return (
    <Container className={cn(!bare && 'border border-border bg-surface shadow-sm', className)}>
      {!bare && (
        <div className="flex flex-wrap justify-between items-center mb-4 gap-2">
          <div className="flex items-center gap-2">
            <Settings2 className="w-5 h-5 text-primary shrink-0" />
            <Title className="text-text truncate">Context Assembler</Title>
            <InfoTooltip 
              content="Learn about context assembly." 
              href="https://docs.sourceprep.io/concepts/context" 
            />
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              onClick={onGetContext}
              disabled={disabled}
              className="whitespace-nowrap"
            >
              Assemble
            </Button>
            {onCopyContext && (
              <Button
                size="sm"
                variant="outline"
                onClick={onCopyContext}
                disabled={!hasContext}
                className="whitespace-nowrap"
                icon={Copy}
              >
                Copy
              </Button>
            )}
          </div>
        </div>
      )}

      <div className="space-y-6">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[12rem]">
            <div className="flex items-center gap-2 mb-2">
              <label className="block text-sm font-medium text-text-muted">
                Chunks (k)
              </label>
              <InfoTooltip content="Number of retrieval chunks to include in the final prompt context." />
            </div>
            <StepperNumberInput value={k} onValueChange={onKChange} min={1} max={50} disabled={disabled} />
          </div>

          <div className="flex-1 min-w-[12rem]">
            <div className="flex items-center gap-2 mb-2">
              <label className="block text-sm font-medium text-text-muted">
                Max Chars
              </label>
              <InfoTooltip content="Hard limit on total characters for the context window to prevent token overflow." />
            </div>
            <StepperNumberInput value={maxChars} onValueChange={onMaxCharsChange} min={200} max={200000} step={100} disabled={disabled} />
          </div>
        </div>

        <div className="border-t border-border" />

        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <label className="block text-sm font-medium text-text-muted">
              Inclusions
            </label>
            <InfoTooltip content="Toggle what metadata is appended to each code chunk in the prompt." />
          </div>
          <Flex className="gap-6 w-auto" justifyContent="start">
            <label className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity">
              <Switch
                checked={includeSources}
                onChange={onIncludeSourcesChange}
                disabled={disabled}
              />
              <Text className="text-sm text-text">Sources</Text>
            </label>

            <label className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity">
              <Switch
                checked={includeScores}
                onChange={onIncludeScoresChange}
                disabled={disabled}
              />
              <Text className="text-sm text-text">Scores</Text>
            </label>

            <label className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity">
              <Switch
                checked={structured}
                onChange={onStructuredChange}
                disabled={disabled}
              />
              <Text className="text-sm text-text">Structured</Text>
            </label>

            {onIncludeAtlasChange && (
              <label className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity">
                <Switch
                  checked={includeAtlas}
                  onChange={onIncludeAtlasChange}
                  disabled={disabled}
                />
                <Text className="text-sm text-text">Atlas</Text>
              </label>
            )}
          </Flex>
        </div>

      </div>
    </Container>
  );
}

import { Card, Title, Text, TextInput } from '@tremor/react';
import { Play, RefreshCw, Folder } from 'lucide-react';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';
import { cn } from '../../lib/utils';

export interface BuildCardProps {
  repoRoot: string;
  onRepoRootChange: (value: string) => void;
  onBuild: () => void;
  building?: boolean;
  className?: string;
  bare?: boolean;
}

export function BuildCard({
  repoRoot,
  onRepoRootChange,
  onBuild,
  building = false,
  className,
  bare = false,
}: BuildCardProps) {
  const Container = bare ? 'div' : Card;

  return (
    <Container className={cn(!bare && 'border border-border bg-surface shadow-sm', className)}>
      <div className="flex items-center gap-3 mb-4">
        {!bare && <RefreshCw className={cn("w-6 h-6 text-primary", building && "animate-spin")} />}
        <div className="flex-1">
          {!bare && (
            <div className="flex items-center gap-2">
              <Title className="text-text">Build Index</Title>
              <InfoTooltip 
                content="Learn how the index is built." 
                href="https://docs.codrag.io/concepts/indexing" 
              />
            </div>
          )}
          <Text className="text-sm text-text-subtle">
            Manually trigger a rebuild of the index.
          </Text>
        </div>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-text-subtle flex items-center gap-1.5">
            <Folder className="w-3.5 h-3.5" />
            Project Root
          </label>
          <TextInput
            value={repoRoot}
            onValueChange={onRepoRootChange}
            placeholder="/path/to/project"
            className="font-mono text-sm"
            disabled={building}
          />
        </div>

        <Button
          onClick={onBuild}
          disabled={building || !repoRoot}
          className="w-full justify-center"
          icon={building ? RefreshCw : Play}
        >
          {building ? 'Building...' : 'Start Build'}
        </Button>
      </div>
    </Container>
  );
}

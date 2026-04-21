import { useCallback, useState } from 'react';
import { Button, ConfirmDialog, Section } from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

type ConfirmAction = 'atlas' | 'group_reasoning' | 'deep_enrichment' | null;

export interface SelectiveResetPageProps {
  projectName: string | null;
  projectId: string | null;
  onDestroyAtlas: () => void;
  onDestroyGroupReasoning: () => void;
  onDestroyDeepEnrichment: () => void;
}

export function SelectiveResetPage({
  projectName,
  projectId,
  onDestroyAtlas,
  onDestroyGroupReasoning,
  onDestroyDeepEnrichment,
}: SelectiveResetPageProps) {
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);

  const handleConfirmedAction = useCallback(() => {
    if (confirmAction === 'atlas') onDestroyAtlas();
    if (confirmAction === 'group_reasoning') onDestroyGroupReasoning();
    if (confirmAction === 'deep_enrichment') onDestroyDeepEnrichment();
    setConfirmAction(null);
  }, [confirmAction, onDestroyAtlas, onDestroyGroupReasoning, onDestroyDeepEnrichment]);

  const description = `Reset individual pipeline stages for ${projectName || 'the active project'}.`;

  return (
    <SettingsPage title="Selective Reset" scope="developer" description={description}>
      <Section title="Reset pipeline stages">
        <div className="grid grid-cols-3 gap-3 py-4">
          <div className="p-3 rounded border border-border bg-surface-raised text-center">
            <h4 className="text-xs font-semibold text-text mb-1">Reset Atlas</h4>
            <p className="text-[10px] text-text-muted mb-2">Deletes atlas and routing data only.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmAction('atlas')}
              disabled={!projectId}
              className="w-full text-xs"
            >
              Reset
            </Button>
          </div>
          <div className="p-3 rounded border border-border bg-surface-raised text-center">
            <h4 className="text-xs font-semibold text-text mb-1">Reset Group Reasoning</h4>
            <p className="text-[10px] text-text-muted mb-2">Deletes group reasoning data only.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmAction('group_reasoning')}
              disabled={!projectId}
              className="w-full text-xs"
            >
              Reset
            </Button>
          </div>
          <div className="p-3 rounded border border-error/40 bg-error/5 text-center">
            <h4 className="text-xs font-semibold text-error mb-1">Reset Deep Enrichment</h4>
            <p className="text-[10px] text-text-muted mb-2">Deletes all 6 deep stages.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmAction('deep_enrichment')}
              disabled={!projectId}
              className="w-full text-xs border-error/40 text-error hover:bg-error/10"
            >
              Reset All
            </Button>
          </div>
        </div>
      </Section>

      {/* ── Confirmation Dialog (portals to body) — drawer parity ── */}
      <ConfirmDialog
        open={confirmAction !== null}
        onConfirm={handleConfirmedAction}
        onCancel={() => setConfirmAction(null)}
        title={
          confirmAction === 'atlas'
            ? `Reset Atlas for ${projectName || 'Project'}?`
            : confirmAction === 'group_reasoning'
              ? `Reset Group Reasoning for ${projectName || 'Project'}?`
              : `Reset Deep Enrichment for ${projectName || 'Project'}?`
        }
        description={
          confirmAction === 'atlas'
            ? 'Permanently deletes the atlas and routing data for this project. Other enrichment stages remain intact.'
            : confirmAction === 'group_reasoning'
              ? 'Permanently deletes the group reasoning data for this project. Other enrichment stages remain intact.'
              : 'Permanently deletes ALL deep enrichment data (epistemic, group reasoning, modules, atlas, deepening, knowledge embeddings). Fast Sync stages (graph, augmentation, inferred edges) remain intact.'
        }
        confirmLabel={
          confirmAction === 'atlas'
            ? 'Reset Atlas'
            : confirmAction === 'group_reasoning'
              ? 'Reset Group Reasoning'
              : 'Reset Deep Enrichment'
        }
      />
    </SettingsPage>
  );
}

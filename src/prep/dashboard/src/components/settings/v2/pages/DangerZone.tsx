import { useCallback, useState } from 'react';
import {
  Button,
  ConfirmDialog,
  InfoTooltip,
  RecoverStagePanel,
  Section,
  Select,
  SettingRow,
  useApiClient,
  type EnrichmentStageId,
} from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

// Stage labels for the Recover picker.
// All 15 stages have checkpoint coverage (see src/prep/services/pipeline_checkpoint.py).
const RECOVER_STAGE_OPTIONS: { value: EnrichmentStageId; label: string }[] = [
  { value: 'structural', label: 'Structural' },
  { value: 'inferred_edges', label: 'Inferred Edges' },
  { value: 'catalogue', label: 'Catalogue' },
  { value: 'validation', label: 'Validation' },
  { value: 'knowledge', label: 'Knowledge Embedding' },
  { value: 'enrichment', label: 'Epistemic Enrichment' },
  { value: 'group_reasoning', label: 'Group Reasoning' },
  { value: 'clustering', label: 'Module Synthesis' },
  { value: 'deepening', label: 'Continuous Deepening' },
  { value: 'deep_knowledge', label: 'Deep Knowledge Embedding' },
  { value: 'atlas', label: 'Atlas' },
  { value: 'rules', label: 'Rules' },
  { value: 'concepts', label: 'Concepts' },
  { value: 'audit', label: 'Audit' },
  { value: 'antibodies', label: 'Antibodies' },
];

type ConfirmAction = 'index' | 'rebuild' | 'enrichment_full' | 'finalize_full' | null;

export interface DangerZonePageProps {
  projectName: string | null;
  /** Selected project id — required for per-stage Recover; null when no project is active. */
  projectId: string | null;
  /** True when any pipeline stage is actively running — disables Recover to prevent mid-run conflicts. */
  pipelineRunning: boolean;
  onRebuildPipeline: () => void;
  onDestroyIndex: () => void;
  onDestroyEnrichmentFull: () => void;
  onDestroyFinalizeFull: () => void;
}

/**
 * Danger Zone settings page (Project scope).
 *
 * Lifts the drawer's Project-tab Danger Zone into the v2 overlay. No
 * dirty/save (actions are one-shot). Preserves the Phase 114 typed-confirm
 * UX byte-for-byte by reusing the shared `<ConfirmDialog>` primitive with
 * the same `confirmAction` state machine the drawer uses.
 *
 * Absorbs the drawer's "Reset All" (index wipe) — the per-numeric "Reset
 * All" from the legacy advanced settings panel (removed in T24) is obsoleted
 * by T15's per-field reset affordances on Trace Limits and is intentionally
 * NOT re-added here.
 *
 * Developer-tier resets (Atlas / Group Reasoning / Deep Enrichment) live on
 * the Developer → Selective Reset page (T23), not here.
 */
export function DangerZonePage({
  projectName,
  projectId,
  pipelineRunning,
  onRebuildPipeline,
  onDestroyIndex,
  onDestroyEnrichmentFull,
  onDestroyFinalizeFull,
}: DangerZonePageProps) {
  const api = useApiClient();

  // ── Confirm-dialog state machine (mirrors SettingsDrawer:205-226) ──
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const [rebuildTypedName, setRebuildTypedName] = useState('');
  const [recoverStageId, setRecoverStageId] = useState<EnrichmentStageId | ''>('');

  const handleConfirmedAction = useCallback(() => {
    if (confirmAction === 'index') onDestroyIndex();
    if (confirmAction === 'rebuild') onRebuildPipeline();
    if (confirmAction === 'enrichment_full') onDestroyEnrichmentFull();
    if (confirmAction === 'finalize_full') onDestroyFinalizeFull();
    setConfirmAction(null);
    setRebuildTypedName('');
  }, [
    confirmAction,
    onDestroyIndex,
    onRebuildPipeline,
    onDestroyEnrichmentFull,
    onDestroyFinalizeFull,
  ]);

  // ── Row controls ────────────────────────────────────────────────
  const rebuildButton = (
    <Button
      variant="outline"
      size="sm"
      onClick={() => setConfirmAction('rebuild')}
      className="border-warning/40 text-warning hover:bg-warning/10"
    >
      Wipe & Rebuild All
    </Button>
  );

  const resetAllButton = (
    <Button variant="destructive" size="sm" onClick={() => setConfirmAction('index')}>
      Reset All
    </Button>
  );

  const resetEnrichmentButton = (
    <Button variant="destructive" size="sm" onClick={() => setConfirmAction('enrichment_full')}>
      Reset Enrichment
    </Button>
  );

  const resetFinalizeButton = (
    <Button variant="destructive" size="sm" onClick={() => setConfirmAction('finalize_full')}>
      Reset Finalize
    </Button>
  );

  const recoverControl = (
    <div className="w-full space-y-2">
      <Select
        size="sm"
        options={RECOVER_STAGE_OPTIONS}
        placeholder="Choose a stage to recover…"
        value={recoverStageId}
        onChange={(e) => setRecoverStageId((e.target.value as EnrichmentStageId) || '')}
        disabled={!projectId || pipelineRunning}
        aria-label="Stage to recover"
      />
      {!projectId && (
        <p className="text-xs text-text-muted">Select a project first.</p>
      )}
      {projectId && pipelineRunning && (
        <p className="text-xs text-warning">
          Pipeline is running — pause or wait for the active run to finish before restoring a stage.
        </p>
      )}
      {projectId && recoverStageId && (
        <RecoverStagePanel
          projectId={projectId}
          stageId={recoverStageId}
          stageLabel={
            RECOVER_STAGE_OPTIONS.find((o) => o.value === recoverStageId)?.label ?? recoverStageId
          }
          apiClient={api}
          disabled={pipelineRunning}
        />
      )}
    </div>
  );

  const description = projectName
    ? `Destructive operations for ${projectName}. Each requires typed confirmation.`
    : 'Destructive operations. Each requires typed confirmation.';

  return (
    <SettingsPage title="Danger Zone" scope="project" description={description}>
      <Section title="Reset data">
        <SettingRow
          label="Rebuild Pipeline"
          description={
            <>
              Wipes all 15 stages and rebuilds from scratch. Current index data stays readable
              during the rebuild and is atomically swapped in as each stage finishes. Incremental
              progress from prior runs is <strong>not preserved</strong>.
            </>
          }
          control={rebuildButton}
        />
        <SettingRow
          label="Reset All"
          description="Wipes every project artifact — trace graph, embeddings, search index, enrichment, SQLite stores, checkpoints. Blocks selfheal until the next finalize completes."
          control={resetAllButton}
        />
        <SettingRow
          label="Reset Enrichment"
          description="Wipes stages 6-15 (deep enrichment + finalize). Fast sync stays intact, so the next run starts fresh at epistemic enrichment."
          control={resetEnrichmentButton}
        />
        <SettingRow
          label="Reset Finalize"
          description="Wipes stages 11-15 (atlas, rules, concepts, audit, antibodies). Enrichment and fast sync stay intact, so the next run starts fresh at atlas."
          control={resetFinalizeButton}
          last
        />
      </Section>

      <Section title="Recover from snapshot">
        <StackedSettingRow
          label="Recover Stage from Snapshot"
          tooltip="Restore a single stage from a prior run's backup without re-running earlier stages. Bypasses the reset barrier."
          description={
            <>
              Restore a single stage from a prior run&apos;s backup without re-running earlier
              stages. Uses the golden snapshot or any branch snapshot available for that stage.{' '}
              <strong>Bypasses the reset barrier.</strong>
            </>
          }
          control={recoverControl}
          last
        />
      </Section>

      {/* ── Confirmation Dialog (portals to body) — drawer parity ── */}
      <ConfirmDialog
        open={confirmAction !== null}
        onConfirm={handleConfirmedAction}
        onCancel={() => {
          setConfirmAction(null);
          setRebuildTypedName('');
        }}
        confirmDisabled={
          confirmAction === 'rebuild' && (!projectName || rebuildTypedName !== projectName)
        }
        title={
          confirmAction === 'rebuild'
            ? `Rebuild Pipeline for ${projectName || 'Project'}?`
            : confirmAction === 'enrichment_full'
              ? `Reset Enrichment for ${projectName || 'Project'}?`
              : confirmAction === 'finalize_full'
                ? `Reset Finalize for ${projectName || 'Project'}?`
                : `Reset All for ${projectName || 'Project'}?`
        }
        description={
          confirmAction === 'rebuild'
            ? 'Re-runs every pipeline stage from scratch. Existing data stays live throughout — each stage atomically replaces its output when the new version is ready. Selfheal is blocked until finalize completes so no stale data resurrects.'
            : confirmAction === 'enrichment_full'
              ? 'Wipes stages 6-15 (deep enrichment and finalize): epistemic, group reasoning, modules, deepening, deep knowledge, atlas, rules, concepts, audit, and antibodies. Clears the concept and antibody SQLite stores so the UI reflects the clean slate. Fast sync (stages 1-5) and observations (user notes) are preserved. Export any hand-authored concepts first if you want to keep them.'
              : confirmAction === 'finalize_full'
                ? 'Wipes stages 11-15 (atlas, rules, concepts, audit, antibodies) and the concept + antibody SQLite stores so the UI reflects the clean slate. Fast sync, deep enrichment, and observations are preserved. Export any hand-authored concepts first if you want to keep them.'
                : 'Wipes every project artifact — embeddings, search index, trace graph, enrichment, SQLite stores, checkpoints, branch snapshots. Writes a reset barrier so selfheal cannot resurrect anything until the next finalize run completes.'
        }
        confirmLabel={
          confirmAction === 'rebuild'
            ? 'Start Rebuild'
            : confirmAction === 'enrichment_full'
              ? 'Reset Enrichment'
              : confirmAction === 'finalize_full'
                ? 'Reset Finalize'
                : 'Reset Everything'
        }
      >
        {confirmAction === 'rebuild' ? (
          <div className="space-y-2">
            <p className="text-xs text-text">
              Type the project name (
              <code className="px-1 rounded bg-muted">{projectName || ''}</code>) to confirm:
            </p>
            <input
              type="text"
              value={rebuildTypedName}
              onChange={(e) => setRebuildTypedName(e.target.value)}
              className="w-full rounded border border-border bg-surface px-2 py-1 text-sm text-text focus:outline-none focus:ring-1 focus:ring-warning"
              placeholder={projectName || 'project name'}
              autoFocus
            />
          </div>
        ) : undefined}
      </ConfirmDialog>
    </SettingsPage>
  );
}

// ── Local layout helper ───────────────────────────────────────────────
// The Recover composite (Select + RecoverStagePanel) is multi-line and
// needs the full page width. The shared `SettingRow` primitive locks the
// control to a ~260px right column, so we render a stacked row ourselves
// when a control needs full width. Mirrors the pattern in Sources.tsx.

interface StackedSettingRowProps {
  label: string;
  tooltip?: string;
  description?: React.ReactNode;
  control: React.ReactNode;
  last?: boolean;
  id?: string;
}

function StackedSettingRow({
  label,
  tooltip,
  description,
  control,
  last,
  id,
}: StackedSettingRowProps) {
  return (
    <div className={last ? 'py-4' : 'py-4 border-b border-border-subtle'}>
      <div className="flex items-center gap-2 mb-1">
        {id ? (
          <label htmlFor={id} className="text-sm font-medium text-text">
            {label}
          </label>
        ) : (
          <div className="text-sm font-medium text-text">{label}</div>
        )}
        {tooltip && <InfoTooltip content={tooltip} />}
      </div>
      {description && <div className="text-sm text-text-muted mb-3">{description}</div>}
      <div className="mt-2">{control}</div>
    </div>
  );
}

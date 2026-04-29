import { useCallback, useMemo, useState } from 'react';
import {
  ConfirmDialog,
  InfoTooltip,
  RecoverStagePanel,
  ScopedActionRow,
  Section,
  Select,
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

type RebuildScope = 'all' | 'sync' | 'enrichment';
type ResetScope = 'all' | 'enrichment' | 'finalize' | 'code-index';
type ConfirmAction = 'rebuild' | 'reset' | null;

const REBUILD_OPTIONS: { value: RebuildScope; label: string }[] = [
  { value: 'all', label: 'All stages (1-15)' },
  { value: 'sync', label: 'Sync (1-5)' },
  { value: 'enrichment', label: 'Enrichment (6-10)' },
];

const RESET_OPTIONS: { value: ResetScope; label: string }[] = [
  { value: 'all', label: 'All stages (1-15)' },
  { value: 'enrichment', label: 'Enrichment (6-15)' },
  { value: 'finalize', label: 'Finalize (11-15)' },
  { value: 'code-index', label: 'Code Index only (RAG embeddings)' },
];

export interface DangerZonePageProps {
  projectName: string | null;
  /** Selected project id — required for per-stage Recover; null when no project is active. */
  projectId: string | null;
  /** True when any pipeline stage is actively running — disables Recover to prevent mid-run conflicts. */
  pipelineRunning: boolean;
  /** Trigger a scoped rebuild. 'all' wipes & rebuilds everything; 'sync' / 'enrichment' rebuild that group only. */
  onRebuildScoped: (scope: RebuildScope) => void;
  /** Trigger a scoped reset. 'all' wipes everything; 'enrichment' wipes 6-15; 'finalize' wipes 11-15. */
  onResetScoped: (scope: ResetScope) => void;
}

/**
 * Normalize a string for typed-confirm comparison.
 *
 * Project names with spaces (e.g. "My Test Project") were silently failing
 * the rebuild typed-confirm gate because either side could carry trailing
 * whitespace from input handling, or differ only by Unicode normalization
 * form (NFC vs NFD — common when names round-trip through macOS HFS+ paths
 * or get composed/decomposed at different points). Normalizing both sides
 * to NFC and trimming makes the comparison robust to those differences
 * without softening the gate (a wrong name still fails).
 */
function normalizeForConfirm(value: string): string {
  return value.normalize('NFC').trim();
}

/**
 * Danger Zone settings page (Project scope).
 *
 * Two scoped action rows — one for Rebuild (1-15 / 1-5 / 6-10) and one
 * for Reset (1-15 / 6-15 / 11-15). Each row is a `<Select>` + `<Button>`
 * pair; clicking the button opens the shared `<ConfirmDialog>` with the
 * Phase 114 typed-confirm UX preserved for rebuild.
 *
 * Developer-tier resets (Atlas / Group Reasoning / Deep Enrichment) live on
 * the Developer → Selective Reset page (T23), not here.
 */
export function DangerZonePage({
  projectName,
  projectId,
  pipelineRunning,
  onRebuildScoped,
  onResetScoped,
}: DangerZonePageProps) {
  const api = useApiClient();

  // ── Scoped row state ──────────────────────────────────────────
  const [rebuildScope, setRebuildScope] = useState<RebuildScope>('all');
  const [resetScope, setResetScope] = useState<ResetScope>('all');

  // ── Confirm-dialog state machine ──────────────────────────────
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const [pendingRebuildScope, setPendingRebuildScope] = useState<RebuildScope>('all');
  const [pendingResetScope, setPendingResetScope] = useState<ResetScope>('all');
  const [rebuildTypedName, setRebuildTypedName] = useState('');
  const [recoverStageId, setRecoverStageId] = useState<EnrichmentStageId | ''>('');

  const handleConfirmedAction = useCallback(() => {
    if (confirmAction === 'rebuild') onRebuildScoped(pendingRebuildScope);
    if (confirmAction === 'reset') onResetScoped(pendingResetScope);
    setConfirmAction(null);
    setRebuildTypedName('');
  }, [
    confirmAction,
    pendingRebuildScope,
    pendingResetScope,
    onRebuildScoped,
    onResetScoped,
  ]);

  const openRebuildConfirm = useCallback(() => {
    setPendingRebuildScope(rebuildScope);
    setRebuildTypedName('');
    setConfirmAction('rebuild');
  }, [rebuildScope]);

  const openResetConfirm = useCallback(() => {
    setPendingResetScope(resetScope);
    setConfirmAction('reset');
  }, [resetScope]);

  // ── Typed-confirm normalization (project names with spaces / Unicode) ──
  const typedConfirmReady = useMemo(() => {
    if (confirmAction !== 'rebuild') return true;
    if (!projectName) return false;
    return normalizeForConfirm(rebuildTypedName) === normalizeForConfirm(projectName);
  }, [confirmAction, rebuildTypedName, projectName]);

  // ── Confirm dialog copy (action × scope) ──────────────────────
  // Reuses the existing description strings verbatim (Phase 114 / Phase 117 wording).
  const dialogTitle = (() => {
    const projLabel = projectName || 'Project';
    if (confirmAction === 'rebuild') {
      return `Rebuild Pipeline for ${projLabel}?`;
    }
    if (confirmAction === 'reset') {
      if (pendingResetScope === 'enrichment') return `Reset Enrichment for ${projLabel}?`;
      if (pendingResetScope === 'finalize') return `Reset Finalize for ${projLabel}?`;
      if (pendingResetScope === 'code-index') return `Reset Code Index for ${projLabel}?`;
      return `Reset All for ${projLabel}?`;
    }
    return '';
  })();

  const dialogDescription = (() => {
    if (confirmAction === 'rebuild') {
      // Single, scope-agnostic message — the existing Rebuild dialog text
      // didn't change between sync/enrichment/all because rebuild semantics
      // are the same: re-run the chosen stages, hot-swap when done.
      return 'Re-runs every pipeline stage from scratch. Existing data stays live throughout — each stage atomically replaces its output when the new version is ready. Selfheal is blocked until finalize completes so no stale data resurrects.';
    }
    if (confirmAction === 'reset') {
      if (pendingResetScope === 'enrichment') {
        return 'Wipes stages 6-15 (deep enrichment and finalize): epistemic, group reasoning, modules, deepening, deep knowledge, atlas, rules, concepts, audit, and antibodies. Clears the concept and antibody SQLite stores so the UI reflects the clean slate. Fast sync (stages 1-5) and observations (user notes) are preserved. Export any hand-authored concepts first if you want to keep them.';
      }
      if (pendingResetScope === 'finalize') {
        return 'Wipes stages 11-15 (atlas, rules, concepts, audit, antibodies) and the concept + antibody SQLite stores so the UI reflects the clean slate. Fast sync, deep enrichment, and observations are preserved. Export any hand-authored concepts first if you want to keep them.';
      }
      if (pendingResetScope === 'code-index') {
        return 'Wipes only the CodeIndex (the RAG verbatim-source embeddings): documents.json, embeddings.npy, manifest.json, fts.sqlite3, plus team-sync directories (local_deltas/, remote/). Trace graph, atlas, concepts, observations, audit, antibodies, and your Knowledge Scope / FolderTree selections are all preserved. The next CodeIndex build re-embeds whatever your Knowledge Scope currently includes — exactly the user-selected files, no more.';
      }
      return 'Wipes every project artifact — embeddings, search index, trace graph, enrichment, SQLite stores, checkpoints, branch snapshots. Writes a reset barrier so selfheal cannot resurrect anything until the next finalize run completes.';
    }
    return '';
  })();

  const dialogConfirmLabel = (() => {
    if (confirmAction === 'rebuild') return 'Start Rebuild';
    if (confirmAction === 'reset') {
      if (pendingResetScope === 'enrichment') return 'Reset Enrichment';
      if (pendingResetScope === 'finalize') return 'Reset Finalize';
      if (pendingResetScope === 'code-index') return 'Reset Code Index';
      return 'Reset Everything';
    }
    return 'Confirm';
  })();

  // ── Recover row control (unchanged) ───────────────────────────
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
        <ScopedActionRow<RebuildScope>
          label="Rebuild Pipeline"
          description={
            <>
              Re-runs the chosen stages from scratch. Current index data stays readable
              during the rebuild and is atomically swapped in as each stage finishes.
              Incremental progress from prior runs is <strong>not preserved</strong>.
            </>
          }
          options={REBUILD_OPTIONS}
          value={rebuildScope}
          onChange={setRebuildScope}
          buttonLabel="Rebuild"
          buttonVariant="outline"
          buttonClassName="border-warning/40 text-warning hover:bg-warning/10"
          onClick={openRebuildConfirm}
          testId="pipeline-danger-rebuild"
        />
        <ScopedActionRow<ResetScope>
          label="Reset"
          description="Wipes the chosen scope's artifacts — embeddings, manifests, SQLite stores, checkpoints. Blocks selfheal until the next finalize completes so nothing stale resurrects."
          options={RESET_OPTIONS}
          value={resetScope}
          onChange={setResetScope}
          buttonLabel="Reset"
          buttonVariant="destructive"
          onClick={openResetConfirm}
          testId="pipeline-danger-reset"
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
        confirmDisabled={confirmAction === 'rebuild' && !typedConfirmReady}
        title={dialogTitle}
        description={dialogDescription}
        confirmLabel={dialogConfirmLabel}
        testId="pipeline-danger-confirm"
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
              data-testid="pipeline-danger-confirm-typed-name-input"
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

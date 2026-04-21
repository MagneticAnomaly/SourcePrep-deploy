/**
 * useStageRegenerate — Phase 105b shared hook.
 *
 * Handles the "Regenerate this stage" click for any finalize stage
 * (atlas, concepts, audit). Wraps the orchestrator-backed endpoint,
 * polls for completion, and fires a caller-supplied refresh callback
 * when the pipeline stage finishes.
 *
 * Usage:
 *   const { regenerating, error, runStage } = useStageRegenerate({
 *     projectId,
 *     stageId: 'atlas',
 *     onComplete: refreshAtlasData,
 *   });
 *   return <StageRegenerateButton regenerating={regenerating} onRegenerate={runStage} />;
 */
import { useCallback, useState } from 'react';

export interface UseStageRegenerateOptions {
  projectId: string | null;
  stageId: 'atlas' | 'rules' | 'concepts' | 'audit' | 'antibodies';
  /** Called after the pipeline stage finishes (or short-circuits).
   *  Typically refreshes the panel's underlying data. */
  onComplete?: () => Promise<void> | void;
}

export interface UseStageRegenerateReturn {
  regenerating: boolean;
  error: string | null;
  runStage: () => Promise<void>;
}

function unwrap<T = unknown>(body: { data?: T } | T): T {
  if (body && typeof body === 'object' && 'data' in (body as object)) {
    return (body as { data: T }).data;
  }
  return body as T;
}

/**
 * Poll /pipeline/status until the named stage is no longer running.
 *
 * Solo finalize runs surface through the orchestrator's `finalize`
 * slot (Phase 105a C1 fix). Resolves when the stage transitions from
 * active→inactive, when the initial-grace window elapses without ever
 * seeing it active (fast path / skip), or on timeout.
 */
async function pollUntilStageDone(
  projectId: string,
  stageId: string,
  opts: { timeoutMs?: number; intervalMs?: number; initialGraceMs?: number } = {},
): Promise<void> {
  const timeoutMs = opts.timeoutMs ?? 5 * 60 * 1000;
  const intervalMs = opts.intervalMs ?? 1500;
  const initialGraceMs = opts.initialGraceMs ?? 6000;

  const deadline = Date.now() + timeoutMs;
  const startedAt = Date.now();
  let sawRunning = false;

  while (Date.now() < deadline) {
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/pipeline/status`,
      );
      if (!res.ok) return;
      const body = await res.json();
      const data = unwrap<{ finalize?: { is_active?: boolean; current_stage?: string } }>(body);
      const fin = data?.finalize;
      const isStageActive = Boolean(
        fin?.is_active && fin?.current_stage === stageId,
      );
      if (isStageActive) {
        sawRunning = true;
      } else if (sawRunning) {
        return;
      } else if (Date.now() - startedAt >= initialGraceMs) {
        return;
      }
    } catch {
      // transient — try next tick
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export function useStageRegenerate(
  opts: UseStageRegenerateOptions,
): UseStageRegenerateReturn {
  const { projectId, stageId, onComplete } = opts;
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runStage = useCallback(async () => {
    if (!projectId) return;
    setRegenerating(true);
    setError(null);
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/pipeline/stages/${encodeURIComponent(stageId)}/run?force=true`,
        { method: 'POST' },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const msg =
          body?.error?.message ?? `run ${stageId} failed: ${res.status}`;
        throw new Error(msg);
      }
      // Wait for the orchestrator to finish, then let the caller refresh
      // its own data. Polling the pipeline status is cheap and matches the
      // existing llm-config cadence.
      await pollUntilStageDone(projectId, stageId);
      if (onComplete) {
        await onComplete();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRegenerating(false);
    }
  }, [projectId, stageId, onComplete]);

  return { regenerating, error, runStage };
}

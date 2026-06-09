/**
 * Wraps the queue X-button cancel action with:
 *   - a toast showing the project's current auto state (transparency)
 *   - a 5-minute rolling counter per project_id; on the 2nd cancel
 *     within the window, emit a sticky warning toast offering a
 *     one-click switch to manual.
 *
 * Design: docs/superpowers/plans/2026-06-08-pipeline-reliability-ux-fixes.md P3
 */
import { useCallback, useRef } from 'react';
import { useToast } from '../components/primitives/Toast';

const WINDOW_MS = 5 * 60 * 1000;
const ESCALATE_AT = 2;

export interface UseCancelToastOpts {
  /** Resolve the project's current auto mode. */
  resolveAutoMode: (projectId: string) => Promise<'auto' | 'manual' | 'scheduled' | string>;
  /** Flip the project to manual via the per-project settings endpoint. */
  switchToManual: (projectId: string) => Promise<void>;
  /** Send the cancel HTTP call, returning success. */
  sendCancel: (projectId: string, group: string, reason: string) => Promise<boolean>;
  /** Display name for the project in toast copy. */
  projectName?: (projectId: string) => string;
}

export function useCancelToast(opts: UseCancelToastOpts) {
  const { push } = useToast();
  const recent = useRef<Map<string, number[]>>(new Map());

  return useCallback(
    async (projectId: string, group: string) => {
      const ok = await opts.sendCancel(projectId, group, 'user_action');
      if (!ok) {
        push({
          title: 'Cancel failed',
          body: 'Could not cancel — see daemon logs.',
          variant: 'error',
        });
        return;
      }

      const now = Date.now();
      const list = (recent.current.get(projectId) ?? []).filter(
        (t) => now - t < WINDOW_MS,
      );
      list.push(now);
      recent.current.set(projectId, list);

      const mode = await opts.resolveAutoMode(projectId).catch(() => 'unknown');
      const name = opts.projectName?.(projectId) ?? projectId.slice(0, 8);

      if (list.length >= ESCALATE_AT) {
        push({
          title: 'Looks like this keeps restarting',
          body: `You've cancelled ${name} ${list.length} times in the last 5 minutes. Switch to manual to break the loop?`,
          action: {
            label: 'Switch to Manual',
            onClick: () => {
              opts.switchToManual(projectId).catch(() => {});
            },
          },
          variant: 'warn',
          durationMs: 0,
        });
        return;
      }

      if (mode === 'auto') {
        push({
          title: `Run cancelled for ${name}`,
          body: 'Auto is enabled — next file change or 5-min watcher check will restart it.',
          action: {
            label: 'Switch to Manual',
            onClick: () => {
              opts.switchToManual(projectId).catch(() => {});
            },
          },
          variant: 'info',
        });
      } else if (mode === 'scheduled') {
        push({
          title: `Run cancelled for ${name}`,
          body: 'Next scheduled run still applies.',
          action: {
            label: 'Switch to Manual',
            onClick: () => {
              opts.switchToManual(projectId).catch(() => {});
            },
          },
          variant: 'info',
        });
      } else {
        push({
          title: `Run cancelled for ${name}`,
          body: "Won't restart automatically (mode is manual).",
          variant: 'info',
        });
      }
    },
    [push, opts.sendCancel, opts.resolveAutoMode, opts.switchToManual, opts.projectName],
  );
}

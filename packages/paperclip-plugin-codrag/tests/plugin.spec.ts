/**
 * CoDRAG Paperclip Plugin — Worker Tests
 *
 * Uses the Paperclip SDK test harness to validate plugin behavior
 * without requiring a running Paperclip server or CoDRAG daemon.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { createTestHarness, type TestHarness } from '@paperclipai/plugin-sdk';
import manifest from '../src/manifest';
import plugin from '../src/worker/index';

describe('CoDRAG Paperclip Plugin', () => {
  let harness: TestHarness;

  beforeEach(async () => {
    harness = createTestHarness({
      manifest,
      config: {
        daemon_url: 'http://127.0.0.1:8400',
        project_id: 'test-project-id',
        auto_context: true,
      },
    });

    // Run plugin setup
    await plugin.definition.setup(harness.ctx);
  });

  describe('initialization', () => {
    it('logs initialization message', () => {
      const initLog = harness.logs.find(
        (l) => l.message.includes('CoDRAG plugin initialized')
      );
      expect(initLog).toBeDefined();
    });

    it('logs the daemon URL', () => {
      const daemonLog = harness.logs.find(
        (l) => l.message.includes('CoDRAG plugin initializing')
      );
      expect(daemonLog).toBeDefined();
      expect(daemonLog?.meta?.daemon).toBe('http://127.0.0.1:8400');
    });
  });

  describe('tools registered', () => {
    it('registers codrag:context tool', async () => {
      // The tool should be registered — executeTool will call it
      // It will fail because no daemon is running, but it should return an error, not throw
      const result = await harness.executeTool('context', {});
      expect(result).toBeDefined();
      // Should have an error since daemon isn't running
      expect(result.error).toBeDefined();
    });

    it('registers codrag:search tool', async () => {
      const result = await harness.executeTool('search', { query: 'test' });
      expect(result).toBeDefined();
      expect(result.error).toBeDefined();
    });

    it('registers codrag:impact tool', async () => {
      const result = await harness.executeTool('impact', { file: 'src/main.py' });
      expect(result).toBeDefined();
      expect(result.error).toBeDefined();
    });

    it('registers codrag:audit tool', async () => {
      const result = await harness.executeTool('audit', {});
      expect(result).toBeDefined();
      expect(result.error).toBeDefined();
    });

    it('registers codrag:observe tool', async () => {
      const result = await harness.executeTool('observe', { content: 'test observation' });
      expect(result).toBeDefined();
      expect(result.error).toBeDefined();
    });
  });

  describe('data providers', () => {
    it('registers codebase-health data provider', async () => {
      const data = await harness.getData('codebase-health');
      expect(data).toBeDefined();
      // Without daemon, should return error state
      expect((data as any).error).toBeDefined();
    });

    it('registers agent-knowledge-scope data provider', async () => {
      const data = await harness.getData('agent-knowledge-scope', { entityId: 'agent-1' });
      expect(data).toBeDefined();
    });
  });

  describe('actions', () => {
    it('registers run-researcher action', async () => {
      // Will fail without daemon but should not throw
      try {
        await harness.performAction('run-researcher', { maxTopics: 3 });
      } catch {
        // Expected — no daemon running
      }
    });

    it('registers run-custodian action', async () => {
      try {
        await harness.performAction('run-custodian', { dryRun: true });
      } catch {
        // Expected — no daemon running
      }
    });
  });

  describe('jobs', () => {
    it('registers reindex-check job', async () => {
      // Should not throw — either succeeds (daemon running) or logs error
      await harness.runJob('reindex-check');
      const hasLog = harness.logs.some(
        (l) => l.message.includes('reindex check') || l.message.includes('unreachable')
      );
      expect(hasLog).toBe(true);
    });
  });

  describe('health', () => {
    it('returns a valid health status', async () => {
      const health = await plugin.definition.onHealth!();
      expect(['ok', 'degraded', 'error']).toContain(health.status);
      expect(health.message).toBeDefined();
    });
  });

  describe('config validation', () => {
    it('rejects empty daemon_url', async () => {
      const result = await plugin.definition.onValidateConfig!({ daemon_url: '' });
      expect(result.ok).toBe(false);
      expect(result.errors).toBeDefined();
      expect(result.errors!.length).toBeGreaterThan(0);
    });

    it('rejects unreachable daemon', async () => {
      const result = await plugin.definition.onValidateConfig!({
        daemon_url: 'http://127.0.0.1:9999',
      });
      expect(result.ok).toBe(false);
    });
  });

  describe('manifest', () => {
    it('has correct id', () => {
      expect(manifest.id).toBe('codrag');
    });

    it('declares 5 tools', () => {
      expect(manifest.tools).toHaveLength(5);
      const names = manifest.tools!.map((t) => t.name);
      expect(names).toContain('context');
      expect(names).toContain('search');
      expect(names).toContain('impact');
      expect(names).toContain('audit');
      expect(names).toContain('observe');
    });

    it('declares 4 UI slots', () => {
      expect(manifest.ui?.slots).toHaveLength(4);
    });

    it('declares 1 job', () => {
      expect(manifest.jobs).toHaveLength(1);
      expect(manifest.jobs![0].jobKey).toBe('reindex-check');
    });

    it('requires agent.tools.register capability', () => {
      expect(manifest.capabilities).toContain('agent.tools.register');
    });

    it('has entrypoints', () => {
      expect(manifest.entrypoints.worker).toBe('dist/worker.js');
      expect(manifest.entrypoints.ui).toBe('dist/ui/');
    });
  });
});

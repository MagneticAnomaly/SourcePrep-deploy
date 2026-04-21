import * as vscode from 'vscode';
import { PrepDaemonClient } from '../client';
import { DaemonManager } from '../daemon';
import type { ProjectStatus } from '../types';

type StatusItem = vscode.TreeItem;

export class IndexStatusTreeDataProvider implements vscode.TreeDataProvider<StatusItem> {
  private _client: PrepDaemonClient;
  private readonly _daemon: DaemonManager;
  private _projectId: string | undefined;
  private _status: ProjectStatus | undefined;

  private readonly _onDidChangeTreeData = new vscode.EventEmitter<StatusItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(client: PrepDaemonClient, daemon: DaemonManager) {
    this._client = client;
    this._daemon = daemon;

    daemon.onStateChange(() => {
      if (daemon.state !== 'connected') {
        this._status = undefined;
        this._onDidChangeTreeData.fire(undefined);
      }
    });
  }

  updateClient(client: PrepDaemonClient): void {
    this._client = client;
    this.refresh();
  }

  setProject(projectId: string): void {
    this._projectId = projectId;
    this.refresh();
  }

  async refresh(): Promise<void> {
    if (!this._projectId || this._daemon.state !== 'connected') {
      this._status = undefined;
      this._onDidChangeTreeData.fire(undefined);
      return;
    }

    try {
      this._status = await this._client.getProjectStatus(this._projectId);
    } catch {
      this._status = undefined;
    }

    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: StatusItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<StatusItem[]> {
    if (this._daemon.state !== 'connected') {
      const item = new vscode.TreeItem('Daemon offline');
      item.iconPath = new vscode.ThemeIcon('warning');
      return [item];
    }

    if (!this._status) {
      const item = new vscode.TreeItem('Select a project');
      item.iconPath = new vscode.ThemeIcon('info');
      return [item];
    }

    const items: StatusItem[] = [];
    const s = this._status;

    // Building status
    if (s.building) {
      const item = new vscode.TreeItem('Building...');
      item.iconPath = new vscode.ThemeIcon('sync~spin');
      items.push(item);
    }

    // Index info
    const chunkItem = new vscode.TreeItem(`Chunks: ${s.index.total_chunks}`);
    chunkItem.iconPath = new vscode.ThemeIcon('symbol-array');
    items.push(chunkItem);

    if (s.index.embedding_model) {
      const modelItem = new vscode.TreeItem(`Model: ${s.index.embedding_model}`);
      modelItem.iconPath = new vscode.ThemeIcon('hubot');
      modelItem.contextValue = 'model';
      items.push(modelItem);
    }

    // Last build
    if (s.index.last_build_at) {
      const d = new Date(s.index.last_build_at);
      const lastBuild = new vscode.TreeItem(`Last build: ${formatRelative(d)}`);
      lastBuild.iconPath = new vscode.ThemeIcon('history');
      lastBuild.tooltip = d.toLocaleString();
      items.push(lastBuild);
    } else {
      const noBuild = new vscode.TreeItem('Not yet built');
      noBuild.iconPath = new vscode.ThemeIcon('circle-slash');
      items.push(noBuild);
    }

    // Staleness
    if (s.stale) {
      const staleItem = new vscode.TreeItem('Index is stale — rebuild recommended');
      staleItem.iconPath = new vscode.ThemeIcon('warning');
      staleItem.command = { command: 'prep.buildIndex', title: 'Build Index' };
      staleItem.contextValue = 'stale';
      items.push(staleItem);
    }

    // Trace
    const traceLabel = s.trace.enabled
      ? `Trace: ${s.trace.counts.nodes} nodes, ${s.trace.counts.edges} edges`
      : 'Trace: disabled';
    const traceItem = new vscode.TreeItem(traceLabel);
    traceItem.iconPath = new vscode.ThemeIcon(s.trace.enabled ? 'type-hierarchy' : 'lock');
    traceItem.contextValue = 'trace';
    if (!s.trace.enabled && this._daemon.tier === 'free') {
      traceItem.description = 'PRO';
      traceItem.tooltip = 'Trace Index requires a Pro license';
    }
    items.push(traceItem);

    // Watcher
    const watchLabel = s.watch.enabled
      ? `Watcher: ${s.watch.state}`
      : 'Watcher: disabled';
    const watchItem = new vscode.TreeItem(watchLabel);
    watchItem.iconPath = new vscode.ThemeIcon(s.watch.enabled ? 'eye' : 'eye-closed');
    watchItem.contextValue = s.watch.enabled ? 'watcher_enabled' : 'watcher_disabled';
    if (!s.watch.enabled && this._daemon.tier === 'free') {
      watchItem.description = 'PRO';
      watchItem.tooltip = 'Real-time watcher requires a Pro license';
    }
    items.push(watchItem);

    return items;
  }
}

function formatRelative(date: Date): string {
  const now = Date.now();
  const diff = now - date.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) { return 'just now'; }
  if (mins < 60) { return `${mins}m ago`; }
  const hours = Math.floor(mins / 60);
  if (hours < 24) { return `${hours}h ago`; }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

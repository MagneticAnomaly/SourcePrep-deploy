import * as vscode from 'vscode';
import { CodragDaemonClient } from '../client';
import { DaemonManager } from '../daemon';
import type { FileTreeNode } from '../types';

export class FileTreeItem extends vscode.TreeItem {
  constructor(
    public readonly node: FileTreeNode,
    public readonly projectId: string,
    public readonly parentPath: string,
    isPinned: boolean
  ) {
    super(
      node.name,
      node.type === 'folder'
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None,
    );

    const fullPath = parentPath ? `${parentPath}/${node.name}` : node.name;

    if (node.type === 'file') {
      this.contextValue = isPinned ? 'pinnedFile' : 'file';
      this.iconPath = isPinned ? new vscode.ThemeIcon('pinned') : vscode.ThemeIcon.File;
      this.resourceUri = vscode.Uri.file(fullPath);
      this.command = {
        command: 'vscode.open',
        title: 'Open File',
        arguments: [vscode.Uri.file(fullPath)],
      };
    } else {
      this.contextValue = 'folder';
      this.iconPath = vscode.ThemeIcon.Folder;
    }

    this.tooltip = fullPath;
    if (isPinned) {
      this.description = '(pinned)';
    }
  }

  get fullPath(): string {
    return this.parentPath ? `${this.parentPath}/${this.node.name}` : this.node.name;
  }
}

export class FileTreeDataProvider implements vscode.TreeDataProvider<FileTreeItem> {
  private _client: CodragDaemonClient;
  private readonly _daemon: DaemonManager;
  private readonly _context: vscode.ExtensionContext;
  private _projectId: string | undefined;
  private _projectPath: string | undefined;
  private _roots: FileTreeNode[] = [];

  private readonly _onDidChangeTreeData = new vscode.EventEmitter<FileTreeItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(client: CodragDaemonClient, daemon: DaemonManager, context: vscode.ExtensionContext) {
    this._client = client;
    this._daemon = daemon;
    this._context = context;

    daemon.onStateChange(() => {
      if (daemon.state !== 'connected') {
        this._roots = [];
        this._onDidChangeTreeData.fire(undefined);
      }
    });
  }

  updateClient(client: CodragDaemonClient): void {
    this._client = client;
    this.refresh();
  }

  setProject(projectId: string, projectPath: string): void {
    this._projectId = projectId;
    this._projectPath = projectPath;
    this.refresh();
  }

  async refresh(): Promise<void> {
    if (!this._projectId || this._daemon.state !== 'connected') {
      this._roots = [];
      this._onDidChangeTreeData.fire(undefined);
      return;
    }

    try {
      const resp = await this._client.getProjectFiles(this._projectId, '', 2);
      this._roots = resp.tree;
    } catch {
      this._roots = [];
    }

    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: FileTreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: FileTreeItem): Promise<FileTreeItem[]> {
    if (!this._projectId || this._daemon.state !== 'connected') {
      if (!this._projectId) {
        const item = new vscode.TreeItem('Select a project first');
        item.iconPath = new vscode.ThemeIcon('info');
        return [item as unknown as FileTreeItem];
      }
      return [];
    }

    let items: FileTreeItem[] = [];

    if (!element) {
      // Root level
      items = this._roots.map(
        (node) => new FileTreeItem(
          node, 
          this._projectId!, 
          this._projectPath ?? '', 
          this.isPinned(node.name)
        ),
      );
    } else if (element.node.children) {
      // Child level — use the node's children if available
      items = element.node.children.map(
        (child) => new FileTreeItem(
          child, 
          this._projectId!, 
          element.fullPath,
          this.isPinned(element.fullPath + '/' + child.name)
        ),
      );
    } else {
      // Lazy load children from the daemon
      try {
        const relativePath = element.fullPath.replace(this._projectPath ?? '', '').replace(/^\//, '');
        const resp = await this._client.getProjectFiles(this._projectId!, relativePath, 2);
        items = resp.tree.map(
          (child) => new FileTreeItem(
            child, 
            this._projectId!, 
            element.fullPath,
            this.isPinned(element.fullPath + '/' + child.name)
          ),
        );
      } catch {
        items = [];
      }
    }

    // Sort: Pinned files first, then folders, then files
    return items.sort((a, b) => {
      const aPinned = a.contextValue === 'pinnedFile';
      const bPinned = b.contextValue === 'pinnedFile';
      if (aPinned && !bPinned) return -1;
      if (!aPinned && bPinned) return 1;
      
      const aFolder = a.node.type === 'folder';
      const bFolder = b.node.type === 'folder';
      if (aFolder && !bFolder) return -1;
      if (!aFolder && bFolder) return 1;
      
      return a.label!.toString().localeCompare(b.label!.toString());
    });
  }

  // ── Pinning Logic ─────────────────────────────────────────────

  private get storageKey(): string {
    return `codrag.pinnedFiles.${this._projectId}`;
  }

  isPinned(path: string): boolean {
    if (!this._projectId) return false;
    const pinned = this._context.workspaceState.get<string[]>(this.storageKey, []);
    // Normalize path just in case
    const normPath = path.replace(this._projectPath + '/', '');
    return pinned.includes(normPath) || pinned.includes(path);
  }

  async pinFile(item: FileTreeItem): Promise<void> {
    if (!this._projectId) return;
    const pinned = this._context.workspaceState.get<string[]>(this.storageKey, []);
    const path = item.fullPath.replace(this._projectPath + '/', '');
    
    if (!pinned.includes(path)) {
      await this._context.workspaceState.update(this.storageKey, [...pinned, path]);
      this._onDidChangeTreeData.fire(undefined);
    }
  }

  async unpinFile(item: FileTreeItem): Promise<void> {
    if (!this._projectId) return;
    const pinned = this._context.workspaceState.get<string[]>(this.storageKey, []);
    const path = item.fullPath.replace(this._projectPath + '/', '');
    
    const newPinned = pinned.filter(p => p !== path);
    await this._context.workspaceState.update(this.storageKey, newPinned);
    this._onDidChangeTreeData.fire(undefined);
  }
}

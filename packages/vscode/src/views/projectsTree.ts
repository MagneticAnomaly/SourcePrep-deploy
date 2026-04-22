import * as vscode from 'vscode';
import { PrepDaemonClient } from '../client';
import { DaemonManager } from '../daemon';
import type { ProjectListItem } from '../types';

export class ProjectTreeItem extends vscode.TreeItem {
  constructor(
    public readonly project: ProjectListItem,
    public readonly isSelected: boolean,
  ) {
    super(project.name, vscode.TreeItemCollapsibleState.None);
    this.contextValue = 'project';
    this.description = project.mode;
    this.tooltip = `${project.name}\n${project.path}\nMode: ${project.mode}`;
    this.iconPath = new vscode.ThemeIcon(isSelected ? 'folder-opened' : 'folder');

    if (isSelected) {
      this.description = `${project.mode} ★`;
    }
  }
}

export class OfflineTreeItem extends vscode.TreeItem {
  constructor() {
    super('Daemon offline', vscode.TreeItemCollapsibleState.None);
    this.description = 'Click to start';
    this.iconPath = new vscode.ThemeIcon('warning');
    this.command = { command: 'prep.startDaemon', title: 'Start Daemon' };
  }
}

export class ProjectsTreeDataProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private _client: PrepDaemonClient;
  private readonly _daemon: DaemonManager;
  private _projects: ProjectListItem[] = [];
  private _selectedProjectId: string | undefined;

  private readonly _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private readonly _onDidSelectProject = new vscode.EventEmitter<ProjectListItem>();
  readonly onDidSelectProject = this._onDidSelectProject.event;

  constructor(client: PrepDaemonClient, daemon: DaemonManager) {
    this._client = client;
    this._daemon = daemon;

    daemon.onStateChange(() => this.refresh());
  }

  get selectedProjectId(): string | undefined { return this._selectedProjectId; }
  get projects(): ProjectListItem[] { return this._projects; }

  updateClient(client: PrepDaemonClient): void {
    this._client = client;
    this.refresh();
  }

  selectProject(projectId: string): void {
    const prevId = this._selectedProjectId;
    this._selectedProjectId = projectId;
    this._onDidChangeTreeData.fire(undefined);

    if (projectId !== prevId) {
      const project = this._projects.find((p) => p.id === projectId);
      if (project) {
        this._onDidSelectProject.fire(project);
      }
    }
  }

  selectProjectByFile(filePath: string): string | undefined {
    if (!this._projects.length) { return undefined; }

    // Find project with longest path that contains filePath
    let bestMatch: ProjectListItem | undefined;
    
    // Normalize file separator to forward slash for simple comparison if needed, 
    // but assuming consistency from VS Code and Daemon for now on the same OS.
    // We add a trailing separator to the project path to ensure we match directory boundaries.
    const separator = filePath.includes('\\') ? '\\' : '/';

    for (const project of this._projects) {
      const projectPath = project.path.endsWith(separator) ? project.path : `${project.path}${separator}`;
      
      // Check if file is inside the project directory (starts with project path + separator)
      // OR if it is the project directory itself (exact match, though rare for a file path)
      const isInside = filePath.startsWith(projectPath) || filePath === project.path;

      if (isInside) {
        // Use the longest matching path (most specific project)
        if (!bestMatch || project.path.length > bestMatch.path.length) {
          bestMatch = project;
        }
      }
    }

    if (bestMatch && bestMatch.id !== this._selectedProjectId) {
      this.selectProject(bestMatch.id);
      return bestMatch.id;
    }
    
    return this._selectedProjectId;
  }

  async refresh(): Promise<void> {
    if (this._daemon.state !== 'connected') {
      this._projects = [];
      this._onDidChangeTreeData.fire(undefined);
      return;
    }

    try {
      const resp = await this._client.listProjects();
      this._projects = resp.projects;

      // Auto-select first project if none selected
      if (!this._selectedProjectId && this._projects.length > 0) {
        this._selectedProjectId = this._projects[0].id;
      }

      // If selected project was removed, reset
      if (this._selectedProjectId && !this._projects.find((p) => p.id === this._selectedProjectId)) {
        this._selectedProjectId = this._projects.length > 0 ? this._projects[0].id : undefined;
      }
    } catch {
      this._projects = [];
    }

    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<vscode.TreeItem[]> {
    if (this._daemon.state !== 'connected') {
      return [new OfflineTreeItem()];
    }

    if (this._projects.length === 0) {
      const item = new vscode.TreeItem('No projects registered');
      item.description = 'Use "SourcePrep: Add Project"';
      item.iconPath = new vscode.ThemeIcon('info');
      return [item];
    }

    return this._projects.map(
      (p) => new ProjectTreeItem(p, p.id === this._selectedProjectId),
    );
  }
}

import * as vscode from 'vscode';
import { DaemonManager } from './daemon';

/**
 * Persistent status bar item showing daemon state, project, and tier.
 */
export class StatusBarManager implements vscode.Disposable {
  private readonly _item: vscode.StatusBarItem;
  private readonly _disposables: vscode.Disposable[] = [];

  constructor(private readonly _daemon: DaemonManager) {
    this._item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
    this._item.command = 'prep.startDaemon';
    this._item.show();

    this._disposables.push(
      this._daemon.onStateChange(() => this.render()),
      this._daemon.onLicenseChange(() => this.render()),
    );

    this.render();
  }

  refresh(): void {
    this.render();
  }

  private render(): void {
    const state = this._daemon.state;
    const tier = this._daemon.tier.toUpperCase();

    switch (state) {
      case 'connected': {
        const ver = this._daemon.version ? ` v${this._daemon.version}` : '';
        this._item.text = `$(check) SourcePrep${ver}`;
        this._item.tooltip = `SourcePrep daemon connected (${tier})`;
        this._item.backgroundColor = undefined;
        this._item.command = 'prep.openDashboard';
        break;
      }
      case 'starting':
        this._item.text = '$(sync~spin) SourcePrep';
        this._item.tooltip = 'Starting SourcePrep daemon...';
        this._item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        this._item.command = undefined;
        break;
      case 'disconnected':
      default:
        this._item.text = '$(error) SourcePrep';
        this._item.tooltip = 'SourcePrep daemon is not running. Click to start.';
        this._item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
        this._item.command = 'prep.startDaemon';
        break;
    }
  }

  dispose(): void {
    this._item.dispose();
    this._disposables.forEach((d) => d.dispose());
  }
}

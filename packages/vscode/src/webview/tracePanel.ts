import * as vscode from 'vscode';
import { getWebviewHtml } from './helper';

export class TracePanel {
  public static currentPanel: TracePanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];
  private _pendingData: any | undefined;

  private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
    this._panel = panel;

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      (message: { command: string }) => {
        if (message.command === 'webviewReady') {
          if (this._pendingData) {
            this.postMessage(this._pendingData);
          }
        } else if (message.command === 'openPricing') {
          vscode.env.openExternal(vscode.Uri.parse('https://runprep.io/pricing'));
        }
      },
      null,
      this._disposables,
    );
  }

  public static createOrShow(
    extensionUri: vscode.Uri,
    data: any,
  ): TracePanel {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (TracePanel.currentPanel) {
      TracePanel.currentPanel._panel.reveal(column);
      TracePanel.currentPanel.update(data);
      return TracePanel.currentPanel;
    }

    const panel = vscode.window.createWebviewPanel(
      'prepTrace',
      'RunPrep Trace',
      column || vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'dist', 'webview')]
      },
    );

    panel.webview.html = getWebviewHtml(panel.webview, extensionUri);

    TracePanel.currentPanel = new TracePanel(panel, extensionUri);
    TracePanel.currentPanel.update(data);
    
    return TracePanel.currentPanel;
  }

  public update(data: any): void {
    this._pendingData = data;
    this.postMessage(data);
  }

  private postMessage(data: any) {
    this._panel.webview.postMessage({
      command: 'showTracePanel',
      data: data
    });
  }

  private dispose(): void {
    TracePanel.currentPanel = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) { d.dispose(); }
    }
  }
}

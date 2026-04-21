import * as vscode from 'vscode';
import { getWebviewHtml } from './helper';

interface ContextResponse {
  context: string;
  chunks?: unknown[];
  total_chars?: number;
  estimated_tokens?: number;
}

export class ContextPreviewPanel {
  public static currentPanel: ContextPreviewPanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];
  private _pendingQuery: string | undefined;
  private _pendingResponse: ContextResponse | undefined;

  private constructor(panel: vscode.WebviewPanel) {
    this._panel = panel;

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      (message: { command: string }) => {
        if (message.command === 'webviewReady') {
          if (this._pendingQuery && this._pendingResponse) {
            this.postMessage(this._pendingQuery, this._pendingResponse);
          }
        }
      },
      null,
      this._disposables,
    );
  }

  public static createOrShow(
    extensionUri: vscode.Uri,
    query: string,
    response: ContextResponse,
  ): ContextPreviewPanel {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (ContextPreviewPanel.currentPanel) {
      ContextPreviewPanel.currentPanel._panel.reveal(column);
      ContextPreviewPanel.currentPanel.update(query, response);
      return ContextPreviewPanel.currentPanel;
    }

    const panel = vscode.window.createWebviewPanel(
      'prepContext',
      `RunPrep Context: ${query}`,
      column || vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'dist', 'webview')]
      },
    );

    panel.webview.html = getWebviewHtml(panel.webview, extensionUri);

    ContextPreviewPanel.currentPanel = new ContextPreviewPanel(panel);
    ContextPreviewPanel.currentPanel.update(query, response);
    
    return ContextPreviewPanel.currentPanel;
  }

  public update(query: string, response: ContextResponse): void {
    this._panel.title = `RunPrep Context: ${query}`;
    this._pendingQuery = query;
    this._pendingResponse = response;
    this.postMessage(query, response);
  }

  private postMessage(query: string, response: ContextResponse) {
    this._panel.webview.postMessage({
      command: 'showContextPreview',
      data: { query, response }
    });
  }

  private dispose(): void {
    ContextPreviewPanel.currentPanel = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) { d.dispose(); }
    }
  }
}


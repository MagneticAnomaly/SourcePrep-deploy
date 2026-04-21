import * as vscode from 'vscode';
import type { SearchResult } from '../types';
import { getWebviewHtml } from './helper';

export class SearchResultsPanel {
  public static currentPanel: SearchResultsPanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];
  private _pendingQuery: string | undefined;
  private _pendingResults: SearchResult[] | undefined;

  private constructor(panel: vscode.WebviewPanel) {
    this._panel = panel;

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      (message: { command: string; file?: string; line?: number }) => {
        if (message.command === 'webviewReady') {
          if (this._pendingQuery && this._pendingResults) {
            this.postMessage(this._pendingQuery, this._pendingResults);
          }
        } else if (message.command === 'openFile' && message.file) {
          const uri = vscode.Uri.file(message.file);
          const line = message.line ? message.line - 1 : 0;
          vscode.window.showTextDocument(uri, {
            selection: new vscode.Range(line, 0, line, 0),
          });
        }
      },
      null,
      this._disposables,
    );
  }

  public static createOrShow(
    extensionUri: vscode.Uri,
    query: string,
    results: SearchResult[],
  ): SearchResultsPanel {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (SearchResultsPanel.currentPanel) {
      SearchResultsPanel.currentPanel._panel.reveal(column);
      SearchResultsPanel.currentPanel.update(query, results);
      return SearchResultsPanel.currentPanel;
    }

    const panel = vscode.window.createWebviewPanel(
      'prepSearch',
      `RunPrep Search: ${query}`,
      column || vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'dist', 'webview')]
      },
    );

    panel.webview.html = getWebviewHtml(panel.webview, extensionUri);

    SearchResultsPanel.currentPanel = new SearchResultsPanel(panel);
    SearchResultsPanel.currentPanel.update(query, results);
    
    return SearchResultsPanel.currentPanel;
  }

  public update(query: string, results: SearchResult[]): void {
    this._panel.title = `RunPrep Search: ${query}`;
    this._pendingQuery = query;
    this._pendingResults = results;
    this.postMessage(query, results);
  }

  private postMessage(query: string, results: SearchResult[]) {
    this._panel.webview.postMessage({
      command: 'showSearchResults',
      data: { query, results }
    });
  }

  private dispose(): void {
    SearchResultsPanel.currentPanel = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) { d.dispose(); }
    }
  }
}


/**
 * Base CSS styles for all Prep WebView panels.
 * Uses VS Code CSS variables for native theme integration.
 */
export function getWebviewBaseStyles(): string {
  return `
    * { box-sizing: border-box; }
    body {
      background: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, sans-serif);
      font-size: var(--vscode-font-size, 13px);
      line-height: 1.5;
      padding: 16px;
      margin: 0;
    }
    h1, h2, h3 {
      color: var(--vscode-foreground);
      font-weight: 600;
    }
    a {
      color: var(--vscode-textLink-foreground);
      text-decoration: none;
    }
    a:hover {
      color: var(--vscode-textLink-activeForeground);
      text-decoration: underline;
    }
    code, pre {
      font-family: var(--vscode-editor-font-family, 'Menlo', 'Monaco', monospace);
      font-size: var(--vscode-editor-font-size, 12px);
    }
    button {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 6px 14px;
      border-radius: 2px;
      cursor: pointer;
      font-size: inherit;
      font-family: inherit;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    button.secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    button.secondary:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }
    input, textarea {
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, transparent);
      padding: 4px 8px;
      font-family: inherit;
      font-size: inherit;
      border-radius: 2px;
    }
    input:focus, textarea:focus {
      outline: 1px solid var(--vscode-focusBorder);
      outline-offset: -1px;
    }
    .badge {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 0.8em;
      font-weight: 600;
      background: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
    }
    .badge-pro {
      background: var(--vscode-statusBarItem-prominentBackground, #5a4fcf);
      color: var(--vscode-statusBarItem-prominentForeground, #fff);
    }
  `;
}

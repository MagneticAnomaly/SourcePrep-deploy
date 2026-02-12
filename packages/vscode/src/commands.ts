import * as vscode from 'vscode';
import { DaemonManager } from './daemon';
import { ProjectsTreeDataProvider, ProjectTreeItem } from './views/projectsTree';
import { FileTreeDataProvider, FileTreeItem } from './views/fileTree';
import { IndexStatusTreeDataProvider } from './views/indexStatus';
import { SearchResultsPanel } from './webview/searchResults';
import { ContextPreviewPanel } from './webview/contextPreview';
import { TracePanel } from './webview/tracePanel';
import { CodragDaemonClient } from './client';

export function registerCommands(
  context: vscode.ExtensionContext,
  daemon: DaemonManager,
  projectsTree: ProjectsTreeDataProvider,
  fileTree: FileTreeDataProvider,
  indexStatus: IndexStatusTreeDataProvider,
  output: vscode.OutputChannel,
): void {
  const reg = (id: string, handler: (...args: unknown[]) => unknown) => {
    context.subscriptions.push(vscode.commands.registerCommand(id, handler));
  };

  // ── Daemon ──────────────────────────────────────────────────

  reg('codrag.startDaemon', () => daemon.startDaemon());
  reg('codrag.stopDaemon', () => daemon.stopDaemon());

  // ── Projects ────────────────────────────────────────────────

  reg('codrag.refreshProjects', () => projectsTree.refresh());
  reg('codrag.refreshFileTree', () => fileTree.refresh());

  reg('codrag.selectProject', async (item: unknown) => {
    if (item instanceof ProjectTreeItem) {
      projectsTree.selectProject(item.project.id);
      fileTree.setProject(item.project.id, item.project.path);
      indexStatus.setProject(item.project.id);
    }
  });

  reg('codrag.addProject', async () => {
    if (!(await daemon.requireConnected())) { return; }

    const uris = await vscode.window.showOpenDialog({
      canSelectFiles: false,
      canSelectFolders: true,
      canSelectMany: false,
      openLabel: 'Add Project',
    });

    if (!uris || uris.length === 0) { return; }
    const folderPath = uris[0].fsPath;

    const name = await vscode.window.showInputBox({
      prompt: 'Project name (optional — leave empty for folder name)',
      placeHolder: folderPath.split('/').pop() || 'my-project',
    });

    try {
      await daemon.client.createProject(folderPath, name || undefined);
      vscode.window.showInformationMessage(`Project added: ${name || folderPath}`);
      projectsTree.refresh();
    } catch (err) {
      vscode.window.showErrorMessage(`Failed to add project: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  reg('codrag.removeProject', async (item: unknown) => {
    if (!(item instanceof ProjectTreeItem)) { return; }
    if (!(await daemon.requireConnected())) { return; }

    const confirm = await vscode.window.showWarningMessage(
      `Remove project "${item.project.name}"?`,
      { modal: true },
      'Remove',
      'Remove & Purge Data',
    );

    if (!confirm) { return; }

    try {
      await daemon.client.deleteProject(item.project.id, confirm === 'Remove & Purge Data');
      vscode.window.showInformationMessage(`Project "${item.project.name}" removed.`);
      projectsTree.refresh();
    } catch (err) {
      vscode.window.showErrorMessage(`Failed to remove project: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // ── Build ───────────────────────────────────────────────────

  reg('codrag.buildIndex', async () => {
    if (!(await daemon.requireConnected())) { return; }
    const projectId = getSelectedProjectId(projectsTree);
    if (!projectId) { return; }

    try {
      const resp = await daemon.client.buildProject(projectId);
      if (resp.started) {
        vscode.window.showInformationMessage('Index build started.');
      } else if (resp.building) {
        vscode.window.showInformationMessage('Build already in progress.');
      }
      // Start polling status
      pollBuildStatus(daemon.client, projectId, indexStatus, output);
    } catch (err) {
      vscode.window.showErrorMessage(`Build failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  reg('codrag.rebuildProject', async (item: unknown) => {
    if (!(item instanceof ProjectTreeItem)) { return; }
    if (!(await daemon.requireConnected())) { return; }

    try {
      await daemon.client.buildProject(item.project.id, true);
      vscode.window.showInformationMessage(`Full rebuild started for "${item.project.name}".`);
      pollBuildStatus(daemon.client, item.project.id, indexStatus, output);
    } catch (err) {
      vscode.window.showErrorMessage(`Rebuild failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // ── Search ──────────────────────────────────────────────────

  reg('codrag.search', async () => {
    if (!(await daemon.requireConnected())) { return; }
    const projectId = getSelectedProjectId(projectsTree);
    if (!projectId) { return; }

    const query = await vscode.window.showInputBox({
      prompt: 'Search your codebase',
      placeHolder: 'e.g. authentication middleware',
    });

    if (!query) { return; }

    try {
      const resp = await daemon.client.search(projectId, query);
      SearchResultsPanel.createOrShow(context.extensionUri, query, resp.results);
    } catch (err) {
      vscode.window.showErrorMessage(`Search failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // ── Context Assembly ────────────────────────────────────────

  reg('codrag.assembleContext', async () => {
    if (!(await daemon.requireConnected())) { return; }
    const projectId = getSelectedProjectId(projectsTree);
    if (!projectId) { return; }

    const query = await vscode.window.showInputBox({
      prompt: 'Assemble context for a query',
      placeHolder: 'e.g. how does the login flow work',
    });

    if (!query) { return; }

    try {
      const resp = await daemon.client.assembleContext(projectId, query, { structured: true });
      ContextPreviewPanel.createOrShow(context.extensionUri, query, resp);
    } catch (err) {
      vscode.window.showErrorMessage(`Context assembly failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // ── MCP Config ──────────────────────────────────────────────

  reg('codrag.copyMCPConfig', async (item?: unknown) => {
    const projectId = item instanceof ProjectTreeItem ? item.project.id : getSelectedProjectId(projectsTree);

    const config = {
      mcpServers: {
        codrag: {
          command: 'codrag',
          args: projectId
            ? ['mcp', '--project', projectId, '--daemon', daemon.client.baseUrl]
            : ['mcp', '--auto', '--daemon', daemon.client.baseUrl],
        },
      },
    };

    await vscode.env.clipboard.writeText(JSON.stringify(config, null, 2));
    vscode.window.showInformationMessage('MCP config copied to clipboard.');
  });

  // ── Dashboard ───────────────────────────────────────────────

  reg('codrag.openDashboard', () => {
    vscode.env.openExternal(vscode.Uri.parse(daemon.client.baseUrl));
  });

  // ── License ─────────────────────────────────────────────────

  reg('codrag.enterLicenseKey', async () => {
    if (!(await daemon.requireConnected())) { return; }

    const key = await vscode.window.showInputBox({
      prompt: 'Enter your CoDRAG license key',
      placeHolder: 'CODRAG-XXXX-XXXX-XXXX',
      password: true,
    });

    if (!key) { return; }

    try {
      const result = await daemon.client.activateLicense(key);
      if (result.license.valid) {
        vscode.window.showInformationMessage(`License activated! Tier: ${result.license.tier.toUpperCase()}`);
        // Force refresh of daemon state to update UI
        daemon.updateClient(daemon.client); 
      } else {
        vscode.window.showErrorMessage('License activation failed: Invalid key.');
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes('ACTIVATION_LIMIT_REACHED')) {
        const action = await vscode.window.showErrorMessage(
          'Activation limit reached. Deactivate an old machine to continue.',
          'Manage Licenses'
        );
        if (action === 'Manage Licenses') {
          vscode.env.openExternal(vscode.Uri.parse('https://codrag.io/account'));
        }
      } else {
        vscode.window.showErrorMessage(`Activation failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
  });

  reg('codrag.deactivateLicense', async () => {
    if (!(await daemon.requireConnected())) { return; }

    const confirm = await vscode.window.showWarningMessage(
      'Are you sure you want to deactivate the license on this machine?',
      { modal: true },
      'Deactivate'
    );

    if (confirm !== 'Deactivate') { return; }

    try {
      await daemon.client.deactivateLicense();
      vscode.window.showInformationMessage('License deactivated. Reverted to Free tier.');
      daemon.updateClient(daemon.client);
    } catch (err) {
      vscode.window.showErrorMessage(`Deactivation failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // ── Watcher (Pro) ───────────────────────────────────────────

  reg('codrag.startWatcher', async () => {
    if (!(await daemon.requireFeature('auto_rebuild', 'Real-time Watcher'))) { return; }
    const projectId = getSelectedProjectId(projectsTree);
    if (!projectId) { return; }

    try {
      await daemon.client.startWatch(projectId);
      vscode.window.showInformationMessage('File watcher started.');
      indexStatus.refresh();
    } catch (err) {
      vscode.window.showErrorMessage(`Failed to start watcher: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  reg('codrag.stopWatcher', async () => {
    if (!(await daemon.requireConnected())) { return; }
    const projectId = getSelectedProjectId(projectsTree);
    if (!projectId) { return; }

    try {
      await daemon.client.stopWatch(projectId);
      vscode.window.showInformationMessage('File watcher stopped.');
      indexStatus.refresh();
    } catch (err) {
      vscode.window.showErrorMessage(`Failed to stop watcher: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // ── Trace (Pro) ─────────────────────────────────────────────

  reg('codrag.traceLookup', async () => {
    const projectId = getSelectedProjectId(projectsTree);
    if (!projectId) { return; }

    // If Free tier, show upsell panel immediately
    if (!daemon.isFeatureAvailable('trace_search')) {
      TracePanel.createOrShow(context.extensionUri, { isFree: true });
      return;
    }

    const query = await vscode.window.showInputBox({
      prompt: 'Search for a symbol in the trace index',
      placeHolder: 'e.g. authenticate_request',
    });

    if (!query) { return; }

    try {
      const resp = await daemon.client.searchTrace(projectId, query);
      TracePanel.createOrShow(context.extensionUri, { isFree: false, query, ...resp });
    } catch (err) {
      vscode.window.showErrorMessage(`Trace lookup failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // ── Refresh ─────────────────────────────────────────────────

  reg('codrag.refreshIndexStatus', () => indexStatus.refresh());

  // ── Pin / Unpin ─────────────────────────────────────────────

  reg('codrag.pinFile', async (item: unknown) => {
    if (item instanceof FileTreeItem) {
      await fileTree.pinFile(item);
    }
  });

  reg('codrag.unpinFile', async (item: unknown) => {
    if (item instanceof FileTreeItem) {
      await fileTree.unpinFile(item);
    }
  });
}

// ── Helpers ─────────────────────────────────────────────────

function getSelectedProjectId(tree: ProjectsTreeDataProvider): string | undefined {
  if (!tree.selectedProjectId) {
    vscode.window.showWarningMessage('No project selected. Select one in the CoDRAG sidebar.');
    return undefined;
  }
  return tree.selectedProjectId;
}

async function pollBuildStatus(
  client: CodragDaemonClient,
  projectId: string,
  indexStatus: IndexStatusTreeDataProvider,
  output: vscode.OutputChannel,
): Promise<void> {
  let attempts = 0;
  const maxAttempts = 120; // 2 minutes at 1s intervals
  const interval = setInterval(async () => {
    attempts++;
    try {
      const status = await client.getProjectStatus(projectId);
      indexStatus.refresh();
      if (!status.building || attempts >= maxAttempts) {
        clearInterval(interval);
        if (!status.building) {
          output.appendLine(`Build complete. Chunks: ${status.index.total_chunks}`);
        }
      }
    } catch {
      clearInterval(interval);
    }
  }, 1000);
}

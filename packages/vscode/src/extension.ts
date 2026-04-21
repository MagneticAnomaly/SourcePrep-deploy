import * as vscode from 'vscode';
import { PrepDaemonClient } from './client';
import { DaemonManager } from './daemon';
import { ProjectsTreeDataProvider } from './views/projectsTree';
import { FileTreeDataProvider } from './views/fileTree';
import { IndexStatusTreeDataProvider } from './views/indexStatus';
import { StatusBarManager } from './statusBar';
import { registerCommands } from './commands';
import { registerChatParticipant } from './chat';

let daemonManager: DaemonManager | undefined;
let statusBarManager: StatusBarManager | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const outputChannel = vscode.window.createOutputChannel('Prep');
  context.subscriptions.push(outputChannel);
  outputChannel.appendLine('Prep extension activating...');

  // Build the daemon client from settings
  const client = createClientFromConfig();

  // Daemon lifecycle manager
  daemonManager = new DaemonManager(client, outputChannel);
  context.subscriptions.push(daemonManager);

  // Tree data providers
  const projectsTree = new ProjectsTreeDataProvider(client, daemonManager);
  const fileTree = new FileTreeDataProvider(client, daemonManager, context);
  const indexStatus = new IndexStatusTreeDataProvider(client, daemonManager);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('prep.projects', projectsTree),
    vscode.window.registerTreeDataProvider('prep.fileTree', fileTree),
    vscode.window.registerTreeDataProvider('prep.indexStatus', indexStatus),
  );

  // Status bar
  statusBarManager = new StatusBarManager(daemonManager);
  context.subscriptions.push(statusBarManager);

  // Register all commands
  registerCommands(context, daemonManager, projectsTree, fileTree, indexStatus, outputChannel);

  // Register chat participant
  registerChatParticipant(context, client);

  // Synchronize views when project selection changes
  context.subscriptions.push(
    projectsTree.onDidSelectProject((project) => {
      fileTree.setProject(project.id, project.path);
      indexStatus.setProject(project.id);
    })
  );

  // Auto-select project based on active file
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor && editor.document.uri.scheme === 'file') {
        projectsTree.selectProjectByFile(editor.document.fileName);
      }
    })
  );

  // React to config changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('prep.daemon')) {
        const newClient = createClientFromConfig();
        daemonManager?.updateClient(newClient);
        projectsTree.updateClient(newClient);
        fileTree.updateClient(newClient);
        indexStatus.updateClient(newClient);
        statusBarManager?.refresh();
        outputChannel.appendLine(`Daemon config changed → ${newClient.baseUrl}`);
      }
    }),
  );

  // Start health polling
  daemonManager.startPolling();

  // Auto-start daemon if configured
  const autoStart = vscode.workspace.getConfiguration('prep.daemon').get<boolean>('autoStart', false);
  if (autoStart) {
    daemonManager.startDaemon();
  }

  outputChannel.appendLine('Prep extension activated.');
}

export function deactivate(): void {
  daemonManager?.dispose();
  statusBarManager?.dispose();
}

function createClientFromConfig(): PrepDaemonClient {
  const config = vscode.workspace.getConfiguration('prep.daemon');
  const host = config.get<string>('host') || process.env.PREP_HOST || '127.0.0.1';
  const port = config.get<number>('port') || (process.env.PREP_PORT ? parseInt(process.env.PREP_PORT, 10) : 8400);
  return new PrepDaemonClient(`http://${host}:${port}`);
}

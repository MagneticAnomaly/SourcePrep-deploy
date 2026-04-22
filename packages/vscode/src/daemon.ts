import * as vscode from 'vscode';
import { PrepDaemonClient } from './client';
import type { LicenseStatus, LicenseTier } from './types';

export type DaemonState = 'connected' | 'disconnected' | 'starting';

/**
 * Manages daemon lifecycle, health polling, and license state.
 * Emits events so other components can react.
 */
export class DaemonManager implements vscode.Disposable {
  private _client: PrepDaemonClient;
  private readonly _output: vscode.OutputChannel;

  private _state: DaemonState = 'disconnected';
  private _version = '';
  private _tier: LicenseTier = 'free';
  private _license: LicenseStatus | undefined;
  private _daemonProcess: ReturnType<typeof import('child_process').spawn> | undefined;
  private _pollTimer: ReturnType<typeof setInterval> | undefined;

  private readonly _onStateChange = new vscode.EventEmitter<DaemonState>();
  readonly onStateChange = this._onStateChange.event;

  private readonly _onLicenseChange = new vscode.EventEmitter<LicenseStatus>();
  readonly onLicenseChange = this._onLicenseChange.event;

  constructor(client: PrepDaemonClient, output: vscode.OutputChannel) {
    this._client = client;
    this._output = output;
  }

  get state(): DaemonState { return this._state; }
  get version(): string { return this._version; }
  get tier(): LicenseTier { return this._tier; }
  get license(): LicenseStatus | undefined { return this._license; }
  get client(): PrepDaemonClient { return this._client; }

  updateClient(client: PrepDaemonClient): void {
    this._client = client;
    this.poll();
  }

  // ── Health Polling ──────────────────────────────────────────

  startPolling(): void {
    this.poll();
    const interval = vscode.workspace.getConfiguration('prep').get<number>('pollingInterval', 10_000);
    this._pollTimer = setInterval(() => this.poll(), interval);
  }

  private async poll(): Promise<void> {
    try {
      const health = await this._client.getHealth();
      this._version = health.version ?? '';
      this.setState('connected');
      await this.fetchLicense();
    } catch {
      this.setState('disconnected');
    }
  }

  private async fetchLicense(): Promise<void> {
    try {
      const lic = await this._client.getLicense();
      this._license = lic;
      this._tier = (lic.license.tier as LicenseTier) || 'free';
      this._onLicenseChange.fire(lic);
    } catch {
      // License endpoint may not exist yet — treat as free
      this._tier = 'free';
    }
  }

  private setState(state: DaemonState): void {
    if (this._state !== state) {
      this._state = state;
      this._onStateChange.fire(state);
    }
  }

  // ── Daemon Lifecycle ────────────────────────────────────────

  async startDaemon(): Promise<void> {
    if (this._state === 'connected') {
      vscode.window.showInformationMessage('SourcePrep daemon is already running.');
      return;
    }

    this.setState('starting');
    this._output.appendLine('Starting SourcePrep daemon...');

    try {
      const cp = await import('child_process');
      const config = vscode.workspace.getConfiguration('prep.daemon');
      const host = config.get<string>('host', '127.0.0.1');
      const port = config.get<number>('port', 8400);
      const executable = config.get<string>('executable', 'prep');

      this._daemonProcess = cp.spawn(executable, ['serve', '--host', host, '--port', String(port)], {
        detached: true,
        stdio: 'ignore',
      });

      this._daemonProcess.unref();
      this._daemonProcess.on('error', (err) => {
        this._output.appendLine(`Failed to start daemon: ${err.message}`);
        vscode.window.showErrorMessage(
          `Could not start SourcePrep daemon. Is 'prep' on your PATH?\n${err.message}`,
        );
        this.setState('disconnected');
      });

      this._daemonProcess.on('exit', (code) => {
        this._output.appendLine(`Daemon process exited (code ${code})`);
        this._daemonProcess = undefined;
        this.setState('disconnected');
      });

      // Wait for it to become reachable
      let attempts = 0;
      const maxAttempts = 20;
      while (attempts < maxAttempts) {
        await delay(500);
        if (await this._client.isReachable()) {
          this._output.appendLine('Daemon started successfully.');
          this.setState('connected');
          await this.fetchLicense();
          return;
        }
        attempts++;
      }

      this._output.appendLine('Daemon started but did not become reachable in time.');
      this.setState('disconnected');
    } catch (err) {
      this._output.appendLine(`Error starting daemon: ${err}`);
      this.setState('disconnected');
    }
  }

  async stopDaemon(): Promise<void> {
    if (this._daemonProcess) {
      this._daemonProcess.kill();
      this._daemonProcess = undefined;
      this._output.appendLine('Daemon process killed.');
    }
    this.setState('disconnected');
  }

  // ── Feature Gating Helpers ──────────────────────────────────

  isFeatureAvailable(feature: keyof LicenseStatus['features']): boolean {
    if (!this._license) { return false; }
    return !!this._license.features[feature];
  }

  async requireFeature(feature: keyof LicenseStatus['features'], label: string): Promise<boolean> {
    if (this._state !== 'connected') {
      vscode.window.showWarningMessage('SourcePrep daemon is not running. Start it first.');
      return false;
    }
    if (!this.isFeatureAvailable(feature)) {
      const action = await vscode.window.showWarningMessage(
        `"${label}" requires a Pro license. Upgrade at sourceprep.io/pricing`,
        'Open Pricing',
      );
      if (action === 'Open Pricing') {
        vscode.env.openExternal(vscode.Uri.parse('https://sourceprep.io/pricing'));
      }
      return false;
    }
    return true;
  }

  async requireConnected(): Promise<boolean> {
    if (this._state !== 'connected') {
      const action = await vscode.window.showWarningMessage(
        'SourcePrep daemon is not running.',
        'Start Daemon',
      );
      if (action === 'Start Daemon') {
        await this.startDaemon();
      }
      return this.state === 'connected';
    }
    return true;
  }

  // ── Disposable ──────────────────────────────────────────────

  dispose(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
    }
    this._onStateChange.dispose();
    this._onLicenseChange.dispose();
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

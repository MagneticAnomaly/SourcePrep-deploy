import type { Meta, StoryObj } from '@storybook/react';
import { EnterpriseAdminPanel } from '../../components/enterprise/EnterpriseAdminPanel';
import type { SyncFleetEntry, UsageData, TokenUsageSummary, SecurityHealthResult } from '../../components/enterprise/EnterpriseAdminPanel';
import type { ComputeNode, SchedulerStatus, AdminPolicy } from '../../types';

const meta: Meta<typeof EnterpriseAdminPanel> = {
  title: 'Enterprise/EnterpriseAdminPanel',
  component: EnterpriseAdminPanel,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Full enterprise admin panel with 5 tabs: Fleet (compute nodes), Sync (team index fleet), Usage (tokens, costs, seats), Security (health checks, events), and Policy (provider/model/DLP restrictions from team_config.json).' } },
  },
  decorators: [(Story) => <div style={{ maxWidth: 800 }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof EnterpriseAdminPanel>;

const now = Date.now() / 1000;

const mockComputeNodes: ComputeNode[] = [
  { id: 'n1', name: 'Local Mac Studio', type: 'local', max_concurrent: 2, gpu_name: 'M3 Max', gpu_vram_gb: 64, endpoint_ids: ['e1'] },
  { id: 'n2', name: 'RunPod A4000', type: 'cloud', max_concurrent: 4, gpu_name: 'A4000', gpu_vram_gb: 16, endpoint_ids: ['e2'] },
  { id: 'n3', name: 'Jenkins Worker', type: 'remote', max_concurrent: 1, endpoint_ids: ['e3'] },
];

const mockScheduler: SchedulerStatus = {
  nodes: {
    n1: { max_concurrent: 2, current_load: 1, active: { 'proj-1': 'enrichment' }, queued: [] },
    n2: { max_concurrent: 4, current_load: 3, active: { 'proj-2': 'catalogue', 'proj-3': 'embedding', 'proj-4': 'inferred_edges' }, queued: [{ project_id: 'proj-5', stage: 'enrichment', waiting_seconds: 12 }] },
    n3: { max_concurrent: 1, current_load: 0, active: {}, queued: [] },
  },
};

const mockSyncFleet: SyncFleetEntry[] = [
  { projectId: 'p1', projectName: 'prep-core', lastSync: now - 300, lastCommit: 'a1b2c3d4e5f6', status: 'synced' },
  { projectId: 'p2', projectName: 'frontend-app', lastSync: now - 3600, lastCommit: 'abc123def456', status: 'syncing' },
  { projectId: 'p3', projectName: 'ml-pipeline', lastSync: now - 86400, lastCommit: 'xyz789', status: 'stale' },
  { projectId: 'p4', projectName: 'infra-platform', lastSync: null, lastCommit: null, status: 'error', error: 'S3 access denied — check IAM role.' },
];

const mockUsage: UsageData = {
  currentMonth: { indexingMinutes: 245, indexingRuns: 38, storageGb: 2.4, activeSeats: 7 },
  limits: { maxIndexingMinutes: 1000, maxStorageGb: 10, maxSeats: 10 },
};

const mockTokenUsage: TokenUsageSummary = {
  total_tokens: 4_250_000,
  call_count: 1820,
  by_provider: { openai: 3_200_000, anthropic: 1_050_000 },
  by_model: { 'gpt-4.1-mini': 2_800_000, 'gpt-4.1': 400_000, 'claude-sonnet-4': 1_050_000 },
  estimated_cost_usd: 42.50,
};

const mockSecurityHealth: SecurityHealthResult = {
  score: 11, total: 14, status: 'warnings',
  checks: [
    { name: 'Network Security', status: 'pass', issues: [], details: {} },
    { name: 'Daemon Authentication', status: 'pass', issues: [], details: {} },
    { name: 'CORS Configuration', status: 'pass', issues: [], details: {} },
    { name: 'License Verification', status: 'pass', issues: [], details: {} },
    { name: 'Dev Mode Detection', status: 'warn', issues: ['Dev mode enabled — disable in production.'], details: {} },
    { name: 'DLP Compliance', status: 'pass', issues: [], details: {} },
    { name: 'Content Sanitization', status: 'pass', issues: [], details: {} },
    { name: 'S3 Endpoint Security', status: 'pass', issues: [], details: {} },
    { name: 'Index Integrity', status: 'pass', issues: [], details: {} },
    { name: 'API Key Hygiene', status: 'warn', issues: ['2 API keys stored in plaintext config.'], details: {} },
    { name: 'Secret Detection Coverage', status: 'pass', issues: [], details: {} },
    { name: 'MCP Rate Limiting', status: 'pass', issues: [], details: {} },
    { name: 'Secrets & Credentials', status: 'warn', issues: ['AWS key found in env without rotation policy.'], details: {} },
    { name: 'Data Exposure Summary', status: 'pass', issues: [], details: {} },
  ],
};

const mockAdminPolicy: AdminPolicy = {
  enforcement_mode: 'enforce',
  provider: {
    allowed_providers: ['openai', 'anthropic', 'google'],
    blocked_providers: ['deepseek'],
    allow_local_providers: true,
    allow_user_endpoints: false,
    allow_user_api_keys: false,
    locked_endpoints: [
      { name: 'Corp OpenAI', provider: 'openai', url: 'https://api.openai.com/v1' },
      { name: 'Corp Anthropic', provider: 'anthropic', url: 'https://api.anthropic.com' },
    ],
  },
  model: {
    allowed_models: ['gpt-4.1', 'gpt-4.1-mini', 'claude-sonnet-4', 'claude-haiku-3.5'],
    blocked_models: [],
    require_approved_models: true,
    allow_any_local_model: true,
    slot_overrides: {
      large: { allowed_models: ['gpt-4.1', 'claude-sonnet-4'], require_approved_models: true },
    },
  },
  data: {
    never_send_globs: ['**/secrets/**', '**/.env*', '**/credentials*'],
    redact_patterns: ['sk-[a-zA-Z0-9]{40,}', 'AKIA[A-Z0-9]{16}'],
    block_unapproved_cloud: true,
    allowed_destinations: ['api.openai.com', 'api.anthropic.com'],
  },
  sync: { require_s3_https: true, allowed_s3_endpoints: ['https://*.r2.cloudflarestorage.com'] },
  network: { block_metadata_endpoints: true, allowed_ports: [443, 8400] },
  budgets: { monthly_token_limit: 10_000_000, monthly_cost_limit_usd: 500, alert_threshold_percent: 80 },
};

const mockSeatStatus = {
  seats_used: 7,
  seats_total: 10,
  tier: 'team',
  email: 'admin@acme.com',
  activation_method: 'license_key',
  last_validated: now - 600,
  grace_days_remaining: 28,
  activations: [
    { instance_id: 'i1', machine: 'mac-studio-dev', platform: 'darwin-arm64', activated_at: now - 86400 * 30, is_current: true },
    { instance_id: 'i2', machine: 'ubuntu-ci-runner', platform: 'linux-x64', activated_at: now - 86400 * 7, is_current: false },
    { instance_id: 'i3', machine: 'windows-designer', platform: 'win32-x64', activated_at: now - 86400 * 14, is_current: false },
  ],
};

/** Full enterprise panel with all data populated */
export const FullAdmin: Story = {
  args: {
    tier: 'enterprise',
    role: 'admin',
    computeNodes: mockComputeNodes,
    schedulerStatus: mockScheduler,
    syncFleet: mockSyncFleet,
    usage: mockUsage,
    tokenUsage: mockTokenUsage,
    securityHealth: mockSecurityHealth,
    securityEvents: [
      { timestamp: now - 3600, event_type: 'LOGIN', severity: 'INFO', message: 'Admin login from 192.168.1.10' },
      { timestamp: now - 7200, event_type: 'POLICY_CHANGE', severity: 'WARNING', message: 'DLP policy updated: added **/secrets/** glob' },
      { timestamp: now - 86400, event_type: 'AUTH_FAILURE', severity: 'CRITICAL', message: 'Failed authentication attempt from 10.0.0.55' },
    ],
    adminPolicy: mockAdminPolicy,
    seatStatus: mockSeatStatus,
    onSyncProject: (id) => console.log('Sync project:', id),
    onExportSecurityReport: () => console.log('Export security'),
    onExportAuditLog: () => console.log('Export audit'),
    onProvisionSeat: async (email) => ({ provisioned: true, message: `Seat provisioned for ${email}` }),
    defaultTab: 'fleet',
  },
};

/** Sync tab active */
export const SyncTab: Story = {
  args: {
    ...FullAdmin.args,
    defaultTab: 'sync',
  },
};

/** Usage tab active */
export const UsageTab: Story = {
  args: {
    ...FullAdmin.args,
    defaultTab: 'usage',
  },
};

/** Security tab active */
export const SecurityTab: Story = {
  args: {
    ...FullAdmin.args,
    defaultTab: 'security',
  },
};

/** Policy tab active */
export const PolicyTab: Story = {
  args: {
    ...FullAdmin.args,
    defaultTab: 'policy',
  },
};

/** Access denied — non-admin or wrong tier */
export const AccessDenied: Story = {
  args: {
    tier: 'pro',
    role: 'user',
    computeNodes: [],
    syncFleet: [],
  },
};

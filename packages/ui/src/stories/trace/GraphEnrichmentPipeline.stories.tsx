import type { Meta, StoryObj } from '@storybook/react';
import { GraphEnrichmentPipeline } from '../../components/trace/GraphEnrichmentPipeline';
import type { AugmentationStatus, DeepAnalysisRunStatus, InferredEdgesStatus, EpistemicStatus, ModuleStatus, DeepeningStatus, KnowledgeEmbeddingStatus, AtlasStatus } from '../../types';
import type { EnrichmentAutoConfig } from '../../components/trace/GraphEnrichmentPipeline';

const meta: Meta<typeof GraphEnrichmentPipeline> = {
  title: 'Dashboard/Widgets/Trace/GraphEnrichmentPipeline',
  component: GraphEnrichmentPipeline,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
  // Phase 117: scoped rebuild + stop are required props. Stories override
  // via their own args when they need to assert specific behaviour.
  args: {
    onRebuild: (scope) => console.log('onRebuild', scope),
    onStopRebuild: () => console.log('onStopRebuild'),
  },
};

export default meta;
type Story = StoryObj<typeof GraphEnrichmentPipeline>;

const traceDisabled = {
  enabled: false,
  exists: false,
  building: false,
  counts: { nodes: 0, edges: 0 },
  last_build_at: null,
};

const traceNotBuilt = {
  enabled: true,
  exists: false,
  building: false,
  counts: { nodes: 0, edges: 0 },
  last_build_at: null,
};

const traceBuilding = {
  enabled: true,
  exists: false,
  building: true,
  counts: { nodes: 0, edges: 0 },
  last_build_at: null,
};

const traceReady = {
  enabled: true,
  exists: true,
  building: false,
  counts: { nodes: 1245, edges: 3890 },
  last_build_at: new Date(Date.now() - 3_600_000).toISOString(),
};

const augNone: AugmentationStatus = {
  enabled: false,
  total_nodes: 0,
  augmented_nodes: 0,
  validated_nodes: 0,
  avg_confidence: 0,
  low_confidence_count: 0,
};

const augPartial: AugmentationStatus = {
  enabled: true,
  total_nodes: 1245,
  augmented_nodes: 620,
  validated_nodes: 0,
  avg_confidence: 0.72,
  low_confidence_count: 180,
  last_augment_at: new Date(Date.now() - 86_400_000).toISOString(),
  model: 'llama3.2:3b',
};

const augFull: AugmentationStatus = {
  enabled: true,
  total_nodes: 1245,
  augmented_nodes: 1200,
  validated_nodes: 450,
  avg_confidence: 0.85,
  low_confidence_count: 45,
  last_augment_at: new Date(Date.now() - 7_200_000).toISOString(),
  model: 'llama3.2:3b',
};

const deepNone: DeepAnalysisRunStatus = {
  queue_size: 180,
  avg_confidence: 0.72,
  running: false,
};

const deepRan: DeepAnalysisRunStatus = {
  last_run_at: new Date(Date.now() - 604_800_000).toISOString(), // 1 week ago
  last_run_items: 47,
  last_run_tokens: 23_450,
  queue_size: 133,
  avg_confidence: 0.78,
  running: false,
};

export const Disabled: Story = {
  args: {
    trace: traceDisabled,
  },
};

export const HeroInitialize: Story = {
  name: 'Hero — Initialize Trace Graph',
  args: {
    trace: traceNotBuilt,
    onRunFastSync: () => alert('Building trace graph...'),
  },
};

export const HeroBuilding: Story = {
  name: 'Hero — Building In Progress',
  args: {
    trace: traceBuilding,
  },
};

export const ReadyToAugment: Story = {
  args: {
    trace: traceReady,
    augmentation: augNone,
    onRunAugmentation: () => alert('Running augmentation...'),
  },
};

export const Augmenting: Story = {
  args: {
    trace: traceReady,
    augmentation: augPartial,
    augmenting: true,
  },
};

export const ReadyToValidate: Story = {
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepNone,
    onRunDeepAnalysis: () => alert('Running validation...'),
  },
};

export const Validating: Story = {
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    deepAnalyzing: true,
  },
};

export const Paused: Story = {
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    fastPaused: true,
  },
};

export const FullPipelineRunning: Story = {
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    fastPaused: false,
  },
};

// ── Group-level controls stories ────────────────────────────

const manualConfig: EnrichmentAutoConfig = { fastSync: false, deepEnrichment: 'manual', finalize: 'manual' };
const autoConfig: EnrichmentAutoConfig = { fastSync: true, deepEnrichment: 'auto', finalize: 'manual' };
const scheduledConfig: EnrichmentAutoConfig = { fastSync: true, deepEnrichment: 'scheduled', finalize: 'manual' };

export const ManualWithRunButtons: Story = {
  name: 'Manual — Run Buttons Visible',
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    autoConfig: manualConfig,
    onAutoConfigChange: (cfg) => console.log('Config changed:', cfg),
    onRunFastSync: () => alert('Running Fast Sync set...'),
    onRunDeepEnrichment: () => alert('Running Deep Enrichment set...'),
    isPro: true,
  },
};

export const AutoMode: Story = {
  name: 'Auto — No Run Buttons',
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    autoConfig: autoConfig,
    onAutoConfigChange: (cfg) => console.log('Config changed:', cfg),
    onRunFastSync: () => alert('Running Fast Sync set...'),
    onRunDeepEnrichment: () => alert('Running Deep Enrichment set...'),
    isPro: true,
  },
};

export const ScheduledDeep: Story = {
  name: 'Scheduled Deep Enrichment',
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    autoConfig: scheduledConfig,
    onAutoConfigChange: (cfg) => console.log('Config changed:', cfg),
    onRunFastSync: () => alert('Running Fast Sync set...'),
    onRunDeepEnrichment: () => alert('Running Deep Enrichment set...'),
    isPro: true,
  },
};

export const FreeUser: Story = {
  name: 'Free User — Toggles Disabled',
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    autoConfig: manualConfig,
    onAutoConfigChange: (cfg) => console.log('Config changed:', cfg),
    onRunFastSync: () => alert('Running Fast Sync set...'),
    onRunDeepEnrichment: () => alert('Running Deep Enrichment set...'),
    isPro: false,
  },
};

export const FastSyncRunning: Story = {
  name: 'Fast Sync Running (Manual)',
  args: {
    trace: { ...traceReady, building: true },
    augmentation: augFull,
    deepAnalysis: deepRan,
    autoConfig: manualConfig,
    onAutoConfigChange: (cfg) => console.log('Config changed:', cfg),
    onRunFastSync: () => alert('Running Fast Sync set...'),
    onRunDeepEnrichment: () => alert('Running Deep Enrichment set...'),
    isPro: true,
  },
};

// ── Full 10-stage pipeline story ────────────────────────────

const ieComplete: InferredEdgesStatus = { enabled: true, exists: true, edge_count: 42 };
const epComplete: EpistemicStatus = { enabled: true, enriched_nodes: 1200, avg_confidence: 0.82, running: false };
const modComplete: ModuleStatus = { enabled: true, module_count: 8, total_files_clustered: 1100, running: false };
const atlasComplete: AtlasStatus = { exists: true, content: null, mode: 'structural', module_count: 8, file_count: 1100, routing: true, stale: false };
const deepComplete: DeepeningStatus = { running: false, total_scored: 1200, settled_count: 1080, settled_ratio: 0.90, avg_score: 0.84 };
const knowComplete: KnowledgeEmbeddingStatus = { enabled: true, running: false, chunks_embedded: 3200, deep_chunks_embedded: 3200, last_run_at: new Date().toISOString() };

export const FullPipeline10Stages: Story = {
  name: 'Full 10-Stage Pipeline (5+5)',
  args: {
    trace: traceReady,
    inferredEdges: ieComplete,
    augmentation: augFull,
    epistemic: epComplete,
    modules: modComplete,
    atlas: atlasComplete,
    deepening: deepComplete,
    knowledge: knowComplete,
    autoConfig: manualConfig,
    onAutoConfigChange: (cfg) => console.log('Config changed:', cfg),
    onRunFastSync: () => alert('Running Fast Sync...'),
    onRunDeepEnrichment: () => alert('Running Deep Enrichment...'),
    isPro: true,
  },
};

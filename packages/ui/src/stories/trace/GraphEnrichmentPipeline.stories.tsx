import type { Meta, StoryObj } from '@storybook/react';
import { GraphEnrichmentPipeline } from '../../components/trace/GraphEnrichmentPipeline';
import type { AugmentationStatus, DeepAnalysisRunStatus } from '../../types';

const meta: Meta<typeof GraphEnrichmentPipeline> = {
  title: 'Dashboard/Widgets/Trace/GraphEnrichmentPipeline',
  component: GraphEnrichmentPipeline,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
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

export const TraceNotBuilt: Story = {
  args: {
    trace: traceNotBuilt,
    onBuildTrace: () => alert('Building trace...'),
  },
};

export const TraceBuilding: Story = {
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
    paused: true,
    onTogglePause: () => alert('Toggling pause...'),
  },
};

export const FullPipelineRunning: Story = {
  args: {
    trace: traceReady,
    augmentation: augFull,
    deepAnalysis: deepRan,
    paused: false,
    onTogglePause: () => alert('Toggling pause...'),
  },
};

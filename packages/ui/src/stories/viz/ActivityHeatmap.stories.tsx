import type { Meta, StoryObj } from '@storybook/react';
import { ActivityHeatmap, generateSampleActivityData, type ActivityHeatmapData } from '../../components/viz/ActivityHeatmap';

const meta: Meta<typeof ActivityHeatmap> = {
  title: 'Dashboard/Visualization/ActivityHeatmap',
  component: ActivityHeatmap,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
  argTypes: {
    weeks: {
      control: { type: 'range', min: 4, max: 52 },
      description: 'Number of weeks to display',
    },
    showLegend: {
      control: 'boolean',
      description: 'Show color legend',
    },
    showLabels: {
      control: 'boolean',
      description: 'Show day/month labels',
    },
  },
};

export default meta;
type Story = StoryObj<typeof ActivityHeatmap>;

// Generate sample data
const sampleData12Weeks = generateSampleActivityData(12);
const sampleData26Weeks = generateSampleActivityData(26);
const sampleData52Weeks = generateSampleActivityData(52);

// Embedding-only data
const embeddingOnlyData: ActivityHeatmapData = {
  days: Array.from({ length: 84 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (83 - i));
    return {
      date: date.toISOString().split('T')[0],
      embeddings: Math.random() > 0.4 ? Math.floor(Math.random() * 50) : 0,
      trace: 0,
      builds: 0,
    };
  }),
  totals: { embeddings: 1234, trace: 0, builds: 47 },
};

// Trace-only data
const traceOnlyData: ActivityHeatmapData = {
  days: Array.from({ length: 84 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (83 - i));
    return {
      date: date.toISOString().split('T')[0],
      embeddings: 0,
      trace: Math.random() > 0.5 ? Math.floor(Math.random() * 30) : 0,
      builds: 0,
    };
  }),
  totals: { embeddings: 0, trace: 567, builds: 23 },
};

// Empty data
const emptyData: ActivityHeatmapData = {
  days: [],
  totals: { embeddings: 0, trace: 0, builds: 0 },
};

// Sparse data (low activity)
const sparseData: ActivityHeatmapData = {
  days: Array.from({ length: 84 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (83 - i));
    const hasActivity = Math.random() > 0.85;
    return {
      date: date.toISOString().split('T')[0],
      embeddings: hasActivity ? Math.floor(Math.random() * 10) : 0,
      trace: hasActivity && Math.random() > 0.5 ? Math.floor(Math.random() * 5) : 0,
      builds: 0,
    };
  }),
  totals: { embeddings: 89, trace: 34, builds: 5 },
};

// Dense data (high activity)
const denseData: ActivityHeatmapData = {
  days: Array.from({ length: 84 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (83 - i));
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    return {
      date: date.toISOString().split('T')[0],
      embeddings: isWeekend ? Math.floor(Math.random() * 20) : Math.floor(Math.random() * 80) + 20,
      trace: Math.floor(Math.random() * 50) + 10,
      builds: Math.floor(Math.random() * 5),
    };
  }),
  totals: { embeddings: 4567, trace: 2341, builds: 156 },
};

export const Default: Story = {
  args: {
    data: sampleData12Weeks,
    weeks: 12,
    showLegend: true,
    showLabels: true,
  },
};

export const HalfYear: Story = {
  args: {
    data: sampleData26Weeks,
    weeks: 26,
    showLegend: true,
    showLabels: true,
  },
};

export const FullYear: Story = {
  args: {
    data: sampleData52Weeks,
    weeks: 52,
    showLegend: true,
    showLabels: true,
  },
};

export const EmbeddingsOnly: Story = {
  args: {
    data: embeddingOnlyData,
    weeks: 12,
    showLegend: true,
    showLabels: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows only embedding activity (cyan colors)',
      },
    },
  },
};

export const TraceOnly: Story = {
  args: {
    data: traceOnlyData,
    weeks: 12,
    showLegend: true,
    showLabels: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows only trace activity (amber/yellow colors)',
      },
    },
  },
};

export const MixedActivity: Story = {
  args: {
    data: denseData,
    weeks: 12,
    showLegend: true,
    showLabels: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'High activity with both embeddings and trace (mixed green colors)',
      },
    },
  },
};

export const SparseActivity: Story = {
  args: {
    data: sparseData,
    weeks: 12,
    showLegend: true,
    showLabels: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Low/sparse activity pattern',
      },
    },
  },
};

export const Empty: Story = {
  args: {
    data: emptyData,
    weeks: 12,
    showLegend: true,
    showLabels: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'No activity recorded',
      },
    },
  },
};

export const Compact: Story = {
  args: {
    data: sampleData12Weeks,
    weeks: 12,
    showLegend: false,
    showLabels: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Compact view without labels or legend',
      },
    },
  },
};

export const InDarkMode: Story = {
  args: {
    data: sampleData12Weeks,
    weeks: 12,
    showLegend: true,
    showLabels: true,
  },
  parameters: {
    backgrounds: { default: 'dark' },
  },
  decorators: [
    (Story) => (
      <div className="dark" data-theme="dark">
        {Story()}
      </div>
    ),
  ],
};

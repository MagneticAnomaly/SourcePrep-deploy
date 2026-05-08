import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Database, Search, Settings2, FileText, FolderTree, Hammer, SlidersHorizontal, List } from 'lucide-react';
import { PanelPicker } from '../../components/layout/PanelPicker';
import type { DashboardLayout, PanelDefinition } from '../../types/layout';

const meta: Meta<typeof PanelPicker> = {
  title: 'Patterns/PanelPicker',
  component: PanelPicker,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof PanelPicker>;

const samplePanelDefinitions: PanelDefinition[] = [
  { id: 'status', title: 'Index Status', icon: Database, minHeight: 2, defaultHeight: 2, category: 'status', closeable: true },
  { id: 'build', title: 'Build', icon: Hammer, minHeight: 2, defaultHeight: 2, category: 'status', closeable: true },
  { id: 'search', title: 'Search', icon: Search, minHeight: 2, defaultHeight: 3, category: 'search', closeable: false },
  { id: 'context-options', title: 'Context Options', icon: SlidersHorizontal, minHeight: 1, defaultHeight: 2, category: 'context', closeable: true },
  { id: 'results', title: 'Search Results', icon: List, minHeight: 2, defaultHeight: 4, category: 'search', closeable: true },
  { id: 'context-output', title: 'Context Output', icon: FileText, minHeight: 2, defaultHeight: 4, category: 'context', closeable: true },
  { id: 'roots', title: 'Index Roots', icon: FolderTree, minHeight: 2, defaultHeight: 5, category: 'config', closeable: true },
  { id: 'settings', title: 'Settings', icon: Settings2, minHeight: 2, defaultHeight: 4, category: 'config', closeable: true },
];

const createSampleLayout = (visibleIds: string[]): DashboardLayout => ({
  version: 1,
  panels: samplePanelDefinitions.map((def) => ({
    id: def.id,
    visible: visibleIds.includes(def.id),
    height: def.defaultHeight,
    collapsed: false,
  })),
});

export const Default: Story = {
  render: () => {
    const [layout, setLayout] = useState<DashboardLayout>(
      createSampleLayout(['status', 'build', 'search', 'results'])
    );

    const handleToggle = (panelId: string) => {
      setLayout((current) => ({
        ...current,
        panels: current.panels.map((p) =>
          p.id === panelId ? { ...p, visible: !p.visible } : p
        ),
      }));
    };

    const handleReset = () => {
      setLayout(createSampleLayout(['status', 'build', 'search', 'results']));
    };

    return (
      <div className="p-4">
        <PanelPicker
          layout={layout}
          panelDefinitions={samplePanelDefinitions}
          onTogglePanel={handleToggle}
          onResetLayout={handleReset}
        />
        <div className="mt-4 p-4 bg-surface-raised rounded-lg">
          <p className="text-xs text-text-muted mb-2">Current visible panels:</p>
          <p className="text-sm text-text">
            {layout.panels.filter((p) => p.visible).map((p) => p.id).join(', ') || 'None'}
          </p>
        </div>
      </div>
    );
  },
};

export const AllPanelsVisible: Story = {
  render: () => {
    const allIds = samplePanelDefinitions.map((d) => d.id);
    const [layout, setLayout] = useState<DashboardLayout>(createSampleLayout(allIds));

    const handleToggle = (panelId: string) => {
      setLayout((current) => ({
        ...current,
        panels: current.panels.map((p) =>
          p.id === panelId ? { ...p, visible: !p.visible } : p
        ),
      }));
    };

    return (
      <PanelPicker
        layout={layout}
        panelDefinitions={samplePanelDefinitions}
        onTogglePanel={handleToggle}
        onResetLayout={() => setLayout(createSampleLayout(allIds))}
      />
    );
  },
};

export const NoPanelsVisible: Story = {
  render: () => {
    const [layout, setLayout] = useState<DashboardLayout>(createSampleLayout([]));

    const handleToggle = (panelId: string) => {
      setLayout((current) => ({
        ...current,
        panels: current.panels.map((p) =>
          p.id === panelId ? { ...p, visible: !p.visible } : p
        ),
      }));
    };

    return (
      <PanelPicker
        layout={layout}
        panelDefinitions={samplePanelDefinitions}
        onTogglePanel={handleToggle}
        onResetLayout={() => setLayout(createSampleLayout(['search']))}
      />
    );
  },
};

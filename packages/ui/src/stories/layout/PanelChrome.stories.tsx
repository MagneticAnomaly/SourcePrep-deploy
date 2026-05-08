import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Database, Search, Settings2 } from 'lucide-react';
import { PanelChrome } from '../../components/layout/PanelChrome';
import { Button } from '../../components/primitives/Button';

const meta: Meta<typeof PanelChrome> = {
  title: 'Patterns/PanelChrome',
  component: PanelChrome,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    title: { control: 'text' },
    collapsed: { control: 'boolean' },
    closeable: { control: 'boolean' },
  },
};

export default meta;
type Story = StoryObj<typeof PanelChrome>;

export const Default: Story = {
  args: {
    title: 'Panel Title',
    children: (
      <div className="p-4">
        <p className="text-sm text-text">Panel content goes here. This is a basic panel with default styling.</p>
      </div>
    ),
  },
};

export const WithIcon: Story = {
  args: {
    title: 'Index Status',
    icon: Database,
    children: (
      <div className="p-4 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-text-muted">Documents</span>
          <span className="text-text font-medium">1,234</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-text-muted">Last Build</span>
          <span className="text-text font-medium">2 hours ago</span>
        </div>
      </div>
    ),
  },
};

export const Collapsible: Story = {
  render: () => {
    const [collapsed, setCollapsed] = useState(false);
    return (
      <PanelChrome
        title="Collapsible Panel"
        icon={Search}
        collapsed={collapsed}
        onCollapse={() => setCollapsed(!collapsed)}
      >
        <div className="p-4">
          <p className="text-sm text-text">
            This panel can be collapsed by clicking the chevron button.
          </p>
        </div>
      </PanelChrome>
    );
  },
};

export const Collapsed: Story = {
  args: {
    title: 'Collapsed Panel',
    icon: Settings2,
    collapsed: true,
    onCollapse: () => {},
    children: (
      <div className="p-4">
        <p className="text-sm text-text">This content is hidden when collapsed.</p>
      </div>
    ),
  },
};

export const NotCloseable: Story = {
  args: {
    title: 'Essential Panel',
    icon: Search,
    closeable: false,
    children: (
      <div className="p-4">
        <p className="text-sm text-text">
          This panel cannot be closed - it has no close button.
        </p>
      </div>
    ),
  },
};

export const WithLongContent: Story = {
  args: {
    title: 'Long Content Panel',
    children: (
      <div className="p-4 space-y-4">
        {Array.from({ length: 10 }).map((_, i) => (
          <p key={i} className="text-sm text-text">
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
            tempor incididunt ut labore et dolore magna aliqua.
          </p>
        ))}
      </div>
    ),
  },
};

export const Interactive: Story = {
  render: () => {
    const [collapsed, setCollapsed] = useState(false);
    const [visible, setVisible] = useState(true);

    if (!visible) {
      return (
        <Button onClick={() => setVisible(true)}>
          Show Panel
        </Button>
      );
    }

    return (
      <PanelChrome
        title="Interactive Panel"
        icon={Database}
        collapsed={collapsed}
        onCollapse={() => setCollapsed(!collapsed)}
        closeable={true}
        onClose={() => setVisible(false)}
      >
        <div className="p-4">
          <p className="text-sm text-text">
            Try collapsing or closing this panel using the header buttons.
          </p>
        </div>
      </PanelChrome>
    );
  },
};

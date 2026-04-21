import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { BuildCard } from '../../components/dashboard/BuildCard';

const meta: Meta<typeof BuildCard> = {
  title: 'Dashboard/Widgets/BuildCard',
  component: BuildCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof BuildCard>;

export const Default: Story = {
  render: () => {
    const [repoRoot, setRepoRoot] = useState('/Users/dev/my-project');
    return (
      <BuildCard
        repoRoot={repoRoot}
        onRepoRootChange={setRepoRoot}
        onBuild={() => console.log('Build triggered:', repoRoot)}
      />
    );
  },
};

export const Empty: Story = {
  render: () => {
    const [repoRoot, setRepoRoot] = useState('');
    return (
      <BuildCard
        repoRoot={repoRoot}
        onRepoRootChange={setRepoRoot}
        onBuild={() => {}}
      />
    );
  },
};

export const Building: Story = {
  render: () => {
    const [repoRoot, setRepoRoot] = useState('/Volumes/Code/Prep');
    return (
      <BuildCard
        repoRoot={repoRoot}
        onRepoRootChange={setRepoRoot}
        onBuild={() => {}}
        building={true}
      />
    );
  },
};

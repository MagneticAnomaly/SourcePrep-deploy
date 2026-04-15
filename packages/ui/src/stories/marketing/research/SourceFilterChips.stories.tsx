import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import {
  SourceFilterChips,
  type FilterValue,
} from '../../../components/marketing/research/SourceFilterChips';
import type { SourceType } from '../../../data/researchSources';

const meta: Meta<typeof SourceFilterChips> = {
  title: 'Website/Marketing/Research/SourceFilterChips',
  component: SourceFilterChips,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof SourceFilterChips>;

const allTypes = new Set<SourceType>(['paper', 'repo', 'blog', 'spec', 'book']);
const someTypes = new Set<SourceType>(['paper', 'repo']);

const Interactive = ({ available }: { available: Set<SourceType> }) => {
  const [active, setActive] = useState<FilterValue>('all');
  return <SourceFilterChips active={active} onChange={setActive} available={available} />;
};

export const AllTypes: Story = {
  render: () => <Interactive available={allTypes} />,
};

export const PartialAvailability: Story = {
  render: () => <Interactive available={someTypes} />,
};

export const PaperActive: Story = {
  args: { active: 'paper', onChange: () => {}, available: allTypes },
};

import type { Meta, StoryObj } from '@storybook/react';
import { SettingRow } from '../SettingRow';

const meta: Meta<typeof SettingRow> = {
  title: 'Primitives/SettingRow',
  component: SettingRow,
};
export default meta;

type Story = StoryObj<typeof SettingRow>;

export const WithToggle: Story = {
  args: {
    id: 'enable-tracing',
    label: 'Enable tracing',
    description: 'Record import edges as files change.',
    control: <input id="enable-tracing" type="checkbox" />,
  },
};

export const WithSelect: Story = {
  args: {
    id: 'worktree-location',
    label: 'Worktree location',
    description: 'Where to store git worktrees.',
    control: (
      <select id="worktree-location" className="border rounded-md px-2 py-1 text-sm">
        <option>Inside project (.claude/)</option>
        <option>External</option>
      </select>
    ),
  },
};

export const WithoutDescription: Story = {
  args: {
    id: 'branch-prefix',
    label: 'Branch prefix',
    control: (
      <input
        id="branch-prefix"
        className="border rounded-md px-2 py-1 text-sm"
        defaultValue="claude"
      />
    ),
  },
};

export const Last: Story = {
  args: {
    id: 'final-row',
    label: 'Final row',
    description: 'No bottom border.',
    control: <input id="final-row" type="checkbox" />,
    last: true,
  },
};

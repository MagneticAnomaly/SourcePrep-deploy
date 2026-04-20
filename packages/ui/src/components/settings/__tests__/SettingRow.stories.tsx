import type { Meta, StoryObj } from '@storybook/react';
import { SettingRow } from '../SettingRow';

const meta: Meta<typeof SettingRow> = {
  title: 'Settings/SettingRow',
  component: SettingRow,
};
export default meta;

type Story = StoryObj<typeof SettingRow>;

export const WithToggle: Story = {
  args: {
    label: 'Enable tracing',
    description: 'Record import edges as files change.',
    control: <input type="checkbox" />,
  },
};

export const WithSelect: Story = {
  args: {
    label: 'Worktree location',
    description: 'Where to store git worktrees.',
    control: (
      <select className="border rounded-md px-2 py-1 text-sm">
        <option>Inside project (.claude/)</option>
        <option>External</option>
      </select>
    ),
  },
};

export const WithoutDescription: Story = {
  args: {
    label: 'Branch prefix',
    control: <input className="border rounded-md px-2 py-1 text-sm" defaultValue="claude" />,
  },
};

export const Last: Story = {
  args: {
    label: 'Final row',
    description: 'No bottom border.',
    control: <input type="checkbox" />,
    last: true,
  },
};

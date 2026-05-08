import type { Meta, StoryObj } from '@storybook/react';
import { Select } from '../../components/primitives/Select';

const meta: Meta<typeof Select> = {
  title: 'Primitives/Select',
  component: Select,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'ghost'],
    },
    size: {
      control: 'select',
      options: ['default', 'sm', 'lg'],
    },
    disabled: {
      control: 'boolean',
    },
  },
};

export default meta;
type Story = StoryObj<typeof Select>;

const sampleOptions = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
];

const themeOptions = [
  { value: 'none', label: 'Default' },
  { value: 'a', label: 'A: Slate Developer' },
  { value: 'b', label: 'B: Deep Focus' },
  { value: 'c', label: 'C: Signal Green' },
  { value: 'd', label: 'D: Warm Craft' },
  { value: 'e', label: 'E: Neo-Brutalist' },
];

export const Default: Story = {
  args: {
    options: sampleOptions,
    'aria-label': 'Mode',
  },
};

export const Small: Story = {
  args: {
    options: sampleOptions,
    size: 'sm',
    'aria-label': 'Mode',
  },
};

export const Large: Story = {
  args: {
    options: sampleOptions,
    size: 'lg',
    'aria-label': 'Mode',
  },
};

export const Ghost: Story = {
  args: {
    options: sampleOptions,
    variant: 'ghost',
    'aria-label': 'Mode',
  },
};

export const Disabled: Story = {
  args: {
    options: sampleOptions,
    disabled: true,
    'aria-label': 'Mode',
  },
};

export const ThemeSelector: Story = {
  args: {
    options: themeOptions,
    size: 'sm',
    'aria-label': 'Visual Style',
  },
};

export const InlineGroup: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <Select options={sampleOptions} size="sm" aria-label="Mode" />
      <Select options={themeOptions} size="sm" aria-label="Theme" />
    </div>
  ),
};

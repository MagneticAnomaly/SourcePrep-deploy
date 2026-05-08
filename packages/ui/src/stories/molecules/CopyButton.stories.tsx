import type { Meta, StoryObj } from '@storybook/react';
import { CopyButton } from '../../components/context/CopyButton';

const meta: Meta<typeof CopyButton> = {
  title: 'Primitives/CopyButton',
  component: CopyButton,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof CopyButton>;

export const Default: Story = {
  args: {
    text: 'Sample text to copy',
    label: 'Copy',
  },
};

export const CustomLabel: Story = {
  args: {
    text: 'Sample text to copy',
    label: 'Copy to Clipboard',
  },
};

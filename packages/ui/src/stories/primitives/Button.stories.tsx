import type { Meta, StoryObj } from '@storybook/react';
import { Button } from '../../components/primitives/Button';
import { Mail, ArrowRight, Save } from 'lucide-react';

const meta: Meta<typeof Button> = {
  title: 'Primitives/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'destructive', 'outline', 'secondary', 'ghost', 'link'],
    },
    size: {
      control: 'select',
      options: ['default', 'sm', 'lg', 'icon'],
    },
    loading: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Default: Story = {
  args: {
    children: 'Button',
    variant: 'default',
  },
};

export const Secondary: Story = {
  args: {
    children: 'Secondary',
    variant: 'secondary',
  },
};

export const Destructive: Story = {
  args: {
    children: 'Delete',
    variant: 'destructive',
  },
};

export const Outline: Story = {
  args: {
    children: 'Outline',
    variant: 'outline',
  },
};

export const Ghost: Story = {
  args: {
    children: 'Ghost',
    variant: 'ghost',
  },
};

export const Link: Story = {
  args: {
    children: 'Link',
    variant: 'link',
  },
};

export const WithIcon: Story = {
  args: {
    children: 'Login with Email',
    icon: Mail,
  },
};

export const IconOnly: Story = {
  args: {
    size: 'icon',
    icon: Save,
    'aria-label': 'Save',
  },
};

export const Loading: Story = {
  args: {
    children: 'Please wait',
    loading: true,
  },
};

export const WithRightIcon: Story = {
  render: (args) => (
    <Button {...args}>
      Get Started
      <ArrowRight className="ml-2 h-4 w-4" />
    </Button>
  ),
};

import type { Meta, StoryObj } from '@storybook/react';
import { UsageGuidePanel } from '../../components/dashboard/UsageGuidePanel';

const meta: Meta<typeof UsageGuidePanel> = {
  title: 'Dashboard/Index/UsageGuidePanel',
  component: UsageGuidePanel,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof UsageGuidePanel>;

export const Default: Story = {
  args: {},
};

export const Bare: Story = {
  args: {
    bare: true,
  },
};

export const CustomDocsUrl: Story = {
  args: {
    docsUrl: 'https://docs.sourceprep.io/guides',
  },
};

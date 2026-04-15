import type { Meta, StoryObj } from '@storybook/react';
import { ResearchHero } from '../../../components/marketing/research/ResearchHero';

const meta: Meta<typeof ResearchHero> = {
  title: 'Website/Marketing/Research/ResearchHero',
  component: ResearchHero,
  parameters: { layout: 'padded' },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ResearchHero>;

export const Default: Story = {};

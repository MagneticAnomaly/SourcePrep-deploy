import type { Meta, StoryObj } from '@storybook/react';
import { FeatureBlocks } from '../../components/marketing/FeatureBlocks';
import { prepFeatures, marketingFeatures } from '../../components/marketing/FeatureBlocks';

const meta: Meta<typeof FeatureBlocks> = {
  title: 'Website/Marketing/FeatureBlocks',
  component: FeatureBlocks,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof FeatureBlocks>;

export const Cards: Story = {
  args: {
    features: prepFeatures,
    variant: 'cards',
  },
};

export const List: Story = {
  args: {
    features: marketingFeatures,
    variant: 'list',
  },
};

export const Bento: Story = {
  args: {
    features: prepFeatures.slice(0, 4), // Bento looks best with 4 items
    variant: 'bento',
  },
};

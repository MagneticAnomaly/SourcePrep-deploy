import type { Meta, StoryObj } from '@storybook/react';
import { SiteFooter } from '../../components/site/SiteFooter';

const meta: Meta<typeof SiteFooter> = {
  title: 'Website/Layout/SiteFooter',
  component: SiteFooter,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof SiteFooter>;

export const Default: Story = {
  args: {
    productName: 'RunPrep',
    socials: {
      twitter: 'https://x.com/Prep_io',
      github: 'https://github.com/MagneticAnomaly/RunPrep-MCP',
      email: 'hello@runprep.io',
    },
  },
};

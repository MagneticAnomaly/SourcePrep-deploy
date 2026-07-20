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
    productName: 'SourcePrep',
    logo: <img src="/prep-logo.png" alt="SourcePrep" style={{ width: '2.5rem', height: '2.5rem' }} className="rounded" />,
    socials: {
      twitter: 'https://x.com/Prep_io',
      github: 'https://github.com/sourceprep',
      email: 'hello@sourceprep.io',
    },
  },
};

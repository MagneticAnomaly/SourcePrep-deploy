import type { Meta, StoryObj } from '@storybook/react';
import { SiteHeader } from '../../components/site/SiteHeader';

const meta: Meta<typeof SiteHeader> = {
  title: 'Website/Layout/SiteHeader',
  component: SiteHeader,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof SiteHeader>;

const defaultLinks = [
  { label: 'Download', href: '/download' },
  { label: 'Docs', href: '/docs' },
  { label: 'Pricing', href: '/pricing' },
  { label: 'Support', href: '/support' },
];

export const Default: Story = {
  args: {
    productName: 'RunPrep',
    links: defaultLinks,
    actions: (
      <a href="#" className="px-4 py-2 bg-primary text-white rounded-md text-sm font-medium">
        Get Started
      </a>
    ),
  },
};

export const WithBadge: Story = {
  args: {
    productName: 'RunPrep',
    productBadge: 'Beta',
    links: defaultLinks,
    actions: (
      <a href="#" className="px-4 py-2 bg-primary text-white rounded-md text-sm font-medium">
        Get Started
      </a>
    ),
  },
};

export const WithSearch: Story = {
  args: {
    productName: 'RunPrep Docs',
    links: defaultLinks,
    searchPlaceholder: 'Search documentation...',
    onSearch: (q) => console.log(q),
  },
};

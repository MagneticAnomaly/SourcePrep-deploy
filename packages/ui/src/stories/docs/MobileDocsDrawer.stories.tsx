import type { Meta, StoryObj } from '@storybook/react';
import { MobileDocsDrawer } from '../../components/docs/MobileDocsDrawer';
import type { DocNode } from '../../components/docs/DocsSidebarNav';

const sampleItems: DocNode[] = [
  {
    title: 'Getting Started',
    href: '/getting-started',
    children: [
      { title: 'Introduction', href: '/getting-started' },
      { title: 'Installation', href: '/getting-started/installation' },
      { title: 'Quick Start', href: '/getting-started/quick-start' },
    ],
  },
  {
    title: 'Core Concepts',
    href: '',
    children: [
      { title: 'Knowledge', href: '/concepts/indexing' },
      { title: 'Code Graph', href: '/concepts/code-graph' },
      { title: 'Graph Enrichment', href: '/concepts/graph-enrichment', active: true },
      { title: 'Context Assembly', href: '/concepts/context' },
    ],
  },
  {
    title: 'Guides',
    href: '',
    children: [
      { title: 'Smart Search', href: '/guides/smart-search' },
      { title: 'Path Weights', href: '/guides/path-weights' },
      { title: 'Codebase Audit', href: '/guides/codebase-audit' },
    ],
  },
];

const sampleSiteLinks = [
  { label: 'Home', href: 'https://sourceprep.io' },
  { label: 'Pricing', href: 'https://sourceprep.io/pricing' },
  { label: 'Download', href: 'https://sourceprep.io/download' },
  { label: 'FAQ', href: 'https://sourceprep.io/faq' },
];

const meta: Meta<typeof MobileDocsDrawer> = {
  title: 'Docs/MobileDocsDrawer',
  component: MobileDocsDrawer,
  parameters: {
    layout: 'fullscreen',
    viewport: { defaultViewport: 'mobile1' },
  },
};

export default meta;
type Story = StoryObj<typeof MobileDocsDrawer>;

export const Default: Story = {
  args: {
    items: sampleItems,
    siteLinks: sampleSiteLinks,
    onClose: () => {},
    onSearch: (q) => console.log('search:', q),
  },
};

export const TabletViewport: Story = {
  args: {
    items: sampleItems,
    siteLinks: sampleSiteLinks,
    onClose: () => {},
  },
  parameters: { viewport: { defaultViewport: 'tablet' } },
};

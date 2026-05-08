import type { Meta, StoryObj } from '@storybook/react';
import { LicenseStatusCard } from '../../components/team/LicenseStatusCard';

const meta: Meta<typeof LicenseStatusCard> = {
  title: 'Dashboard/Team/LicenseStatusCard',
  component: LicenseStatusCard,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'License status card showing current tier, features list, seat usage (Team/Enterprise), expiration date, and upgrade/manage actions.' } },
  },
  decorators: [(Story) => <div style={{ maxWidth: 480 }}><Story /></div>],
};

export default meta;
type Story = StoryObj<typeof LicenseStatusCard>;

/** Free tier with upgrade CTA */
export const Free: Story = {
  args: {
    license: {
      tier: 'free', valid: true,
      features: ['5 projects', 'Basic search', 'Manual builds'],
    },
    onUpgrade: () => console.log('Upgrade clicked'),
  },
};

/** Pro tier */
export const Pro: Story = {
  args: {
    license: {
      tier: 'pro', valid: true,
      expires_at: '2027-04-01',
      features: ['Unlimited projects', 'Auto-rebuild', 'Deep enrichment', 'Priority support'],
    },
    onManageLicense: () => console.log('Manage license'),
  },
};

/** Team tier with seats */
export const Team: Story = {
  args: {
    license: {
      tier: 'team', valid: true,
      expires_at: '2027-04-01',
      seats_used: 7, seats_total: 10,
      features: ['Team sync', 'S3 index sharing', 'SSO', 'Admin dashboard'],
    },
    onManageLicense: () => console.log('Manage license'),
  },
};

/** Enterprise with high seat usage */
export const Enterprise: Story = {
  args: {
    license: {
      tier: 'enterprise', valid: true,
      expires_at: '2027-12-31',
      seats_used: 48, seats_total: 50,
      features: ['Unlimited seats', 'Private cloud', 'Custom models', 'Dedicated support', 'SLA'],
    },
    onManageLicense: () => console.log('Manage license'),
  },
};

/** Expired/invalid license */
export const Expired: Story = {
  args: {
    license: {
      tier: 'pro', valid: false,
      expires_at: '2025-12-31',
      features: ['Unlimited projects', 'Auto-rebuild'],
    },
    onUpgrade: () => console.log('Renew'),
    onManageLicense: () => console.log('Manage'),
  },
};

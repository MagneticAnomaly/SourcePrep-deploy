"use client";

import { FeatureBlocks } from '@prep/ui';
import { HelpCircle, Bug, CreditCard, Mail, Shield } from 'lucide-react';

const GITHUB_REPO_URL = 'https://github.com/MagneticAnomaly/SourcePrep';

const supportOptions = [
  {
    icon: <HelpCircle className="w-8 h-8" />,
    title: 'Troubleshooting',
    description: 'Common issues, fixes, and performance tips.',
    href: 'https://docs.sourceprep.io/troubleshooting',
    external: true,
  },
  {
    icon: <Bug className="w-8 h-8" />,
    title: 'Report a bug',
    description: 'File an issue with repro steps and logs.',
    href: `${GITHUB_REPO_URL}/issues/new/choose`,
    external: true,
  },
  {
    icon: <CreditCard className="w-8 h-8" />,
    title: 'Billing & licenses',
    description: 'Purchase, license delivery, and recovery.',
    href: 'https://payments.sourceprep.io',
    external: true,
  },
  {
    icon: <Mail className="w-8 h-8" />,
    title: 'Email support',
    description: 'support@sourceprep.io',
    href: 'mailto:support@sourceprep.io',
    external: true,
  },
  {
    icon: <Shield className="w-8 h-8" />,
    title: 'Security reporting',
    description: 'security@sourceprep.io',
    href: 'mailto:security@sourceprep.io',
    external: true,
  },
];

export function SupportFeatures() {
  return <FeatureBlocks features={supportOptions} variant="cards" />;
}

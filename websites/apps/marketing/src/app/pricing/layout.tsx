import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Pricing',
  description: 'SourcePrep is free and open source (Apache 2.0). Pro adds signed installers and auto-update — $29 one-time, coming soon.',
  path: '/pricing',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

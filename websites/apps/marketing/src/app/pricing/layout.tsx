import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Pricing',
  description: 'Transparent pricing for CoDRAG. Free tier available, or get a Pro perpetual license with zero cloud token markup.',
  path: '/pricing',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

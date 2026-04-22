import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'About',
  description: 'The mission behind SourcePrep: bringing determinism and structural understanding back to AI coding tools.',
  path: '/about',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

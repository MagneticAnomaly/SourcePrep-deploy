import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Community',
  description: 'Join the Prep community of developers building the next generation of AI-assisted software.',
  path: '/community',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

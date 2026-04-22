import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Support',
  description: 'Get help with SourcePrep installation, usage, and troubleshooting.',
  path: '/support',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

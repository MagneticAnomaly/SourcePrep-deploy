import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Terms of Service',
  description: 'Terms of service and licensing agreement for SourcePrep.',
  path: '/terms',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

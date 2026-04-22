import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Privacy Policy',
  description: 'SourcePrep privacy policy. We believe your code is your business.',
  path: '/privacy',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

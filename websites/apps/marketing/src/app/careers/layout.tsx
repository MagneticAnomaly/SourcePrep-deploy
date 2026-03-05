import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Careers',
  description: 'Work with us to build the ultimate local codebase context engine.',
  path: '/careers',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

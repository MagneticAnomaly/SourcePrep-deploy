import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Blog',
  description: 'Articles, tutorials, and deep-dives on local RAG, context windows, and AI-assisted engineering.',
  path: '/blog',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

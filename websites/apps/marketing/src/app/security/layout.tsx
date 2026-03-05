import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Security & Privacy',
  description: 'CoDRAG is local-first by default. Your codebase stays on your machine. Learn about our zero-telemetry architecture.',
  path: '/security',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

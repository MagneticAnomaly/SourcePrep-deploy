import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Changelog',
  description: 'Latest updates, features, and improvements to the RunPrep engine and MCP server.',
  path: '/changelog',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

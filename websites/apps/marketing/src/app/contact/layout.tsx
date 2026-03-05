import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Contact Us',
  description: 'Get in touch with the CoDRAG team for support, enterprise inquiries, or general questions.',
  path: '/contact',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

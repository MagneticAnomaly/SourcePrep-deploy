import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import Script from 'next/script';
import { Inter, JetBrains_Mono, IBM_Plex_Serif, Space_Mono } from 'next/font/google';

import '@codrag/ui/styles';
import './globals.css';

import { ClientLayout } from './ClientLayout';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });
const spaceMono = Space_Mono({ weight: ['400', '700'], subsets: ['latin'], variable: '--font-space' });
const ibmPlexSerif = IBM_Plex_Serif({ weight: ['400', '600'], subsets: ['latin'], variable: '--font-heading' });

export const metadata: Metadata = {
  metadataBase: new URL('https://docs.codrag.io'),
  title: 'CoDRAG Documentation',
  description: 'Documentation for CoDRAG CLI, dashboard, and integrations.',
  icons: {
    icon: [
      { url: '/favicon_io/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon_io/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon_io/favicon.ico', sizes: 'any' },
    ],
    apple: [
      { url: '/favicon_io/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
    other: [
      { rel: 'manifest', url: '/favicon_io/site.webmanifest' },
    ],
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-codrag-theme="m" className={`${inter.variable} ${jetbrainsMono.variable} ${spaceMono.variable} ${ibmPlexSerif.variable}`}>
      <body className="bg-background text-text selection:bg-primary/20 font-mono">
        <Script src="https://plausible.io/js/pa-3CWngGnNeUfIgUQ7wL2mV.js" strategy="afterInteractive" />
        <Script id="plausible-init" strategy="afterInteractive" dangerouslySetInnerHTML={{ __html: `window.plausible=window.plausible||function(){(plausible.q=plausible.q||[]).push(arguments)},plausible.init=plausible.init||function(i){plausible.o=i||{}};plausible.init()` }} />
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}

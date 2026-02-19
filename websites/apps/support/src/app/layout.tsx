import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import Script from 'next/script';
import { Inter, JetBrains_Mono } from 'next/font/google';

import '@codrag/ui/styles';
import './globals.css';

import { ClientLayout } from './ClientLayout';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  metadataBase: new URL('https://support.codrag.io'),
  title: 'CoDRAG Support',
  description: 'Support hub for CoDRAG: tickets, bugs, questions, and security reporting.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-codrag-theme="k" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="flex flex-col min-h-screen bg-background text-text selection:bg-primary/20 font-sans">
        <Script src="https://plausible.io/js/pa-l4-40TTsH65-qynGLddpJ.js" strategy="afterInteractive" />
        <Script id="plausible-init" strategy="afterInteractive" dangerouslySetInnerHTML={{ __html: `window.plausible=window.plausible||function(){(plausible.q=plausible.q||[]).push(arguments)},plausible.init=plausible.init||function(i){plausible.o=i||{}};plausible.init()` }} />
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}

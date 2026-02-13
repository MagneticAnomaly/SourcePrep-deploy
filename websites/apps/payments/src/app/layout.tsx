import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { Inter, JetBrains_Mono } from 'next/font/google';

import '@codrag/ui/styles';
import './globals.css';

import { ClientLayout } from './ClientLayout';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  metadataBase: new URL('https://payments.codrag.io'),
  title: 'CoDRAG Payments',
  description: 'Purchase and manage CoDRAG licenses.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-codrag-theme="k" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="flex flex-col min-h-screen bg-background text-text selection:bg-primary/20 font-sans">
        {/* 
          TODO: Analytics (Plausible/Umami)
          <script defer data-domain="payments.codrag.io" src="https://plausible.io/js/script.js"></script>
        */}
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}

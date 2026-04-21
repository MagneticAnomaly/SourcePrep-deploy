import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import Script from 'next/script';
import { Inter, JetBrains_Mono, IBM_Plex_Serif, Playfair_Display, Space_Mono, IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';

import '@prep/ui/styles';
import './globals.css';

import { ClientLayout } from './ClientLayout';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });
const playfair = Playfair_Display({ subsets: ['latin'], variable: '--font-serif' });
const spaceMono = Space_Mono({ weight: ['400', '700'], subsets: ['latin'], variable: '--font-space' });
const ibmPlexSans = IBM_Plex_Sans({ weight: ['400', '500', '600', '700'], subsets: ['latin'], variable: '--font-ibm-sans' });
const ibmPlexMono = IBM_Plex_Mono({ weight: ['400', '500', '600'], subsets: ['latin'], variable: '--font-ibm-mono' });
const ibmPlexSerif = IBM_Plex_Serif({ weight: ['400', '500', '600'], subsets: ['latin'], variable: '--font-heading' });


const productSchema = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "RunPrep",
  "operatingSystem": "macOS, Windows, Linux",
  "applicationCategory": "DeveloperApplication",
  "description": "Epistemic codebase intelligence engine designed for autonomous agents and AI-assisted development. It creates a structural code graph using Rust to map imports, call chains, and symbol hierarchies for sophisticated context.",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  }
};
export const metadata: Metadata = {
  metadataBase: new URL('https://runprep.io'),
  title: {
    default: 'RunPrep - Epistemic Code Context',
    template: '%s | RunPrep'
  },
  description: 'Deep structural codebase tracing and epistemic context for autonomous agents and intelligent workflows.',
  openGraph: {
    title: 'RunPrep - Epistemic Code Context',
    description: 'Deep structural codebase tracing and epistemic context for autonomous agents and intelligent workflows.',
    url: 'https://runprep.io',
    siteName: 'RunPrep',
    images: [
      {
        url: '/images/og-image.png',
        width: 1245,
        height: 779,
        alt: 'RunPrep Logo',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'RunPrep - Epistemic Code Context',
    description: 'Deep structural codebase tracing and epistemic context for autonomous agents and intelligent workflows.',
    images: ['/images/og-image.png'],
  },
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
    <html lang="en" data-prep-theme="m" className={`${inter.variable} ${jetbrainsMono.variable} ${playfair.variable} ${spaceMono.variable} ${ibmPlexSans.variable} ${ibmPlexMono.variable} ${ibmPlexSerif.variable}`}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(productSchema) }}
        />
      </head>
      <body className="flex flex-col min-h-screen bg-background text-text selection:bg-primary/20 font-mono">
        <Script src="https://plausible.io/js/pa-EyiWunLuXsVDCxYAfsQ6-.js" strategy="afterInteractive" />
        <Script id="plausible-init" strategy="afterInteractive" dangerouslySetInnerHTML={{ __html: `window.plausible=window.plausible||function(){(plausible.q=plausible.q||[]).push(arguments)},plausible.init=plausible.init||function(i){plausible.o=i||{}};plausible.init()` }} />
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}

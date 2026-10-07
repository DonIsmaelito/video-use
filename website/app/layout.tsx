import type { Metadata } from 'next';
import { McpAnnouncement } from '@/components/mcp-announcement';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.SITE_URL || 'https://video-use.insforge.site',
  ),
  title: 'video-use — Prompt something worth watching',
  description:
    'An open-source video toolkit. Explore real edits, motion design, and explainers. Copy a prompt, bring a reference, and make it yours.',
  icons: { icon: '/favicon.svg' },
  openGraph: {
    title: 'video-use — Prompt something worth watching',
    description:
      'Edits, motion, stories, and video. Browse real examples, copy a prompt, and make it yours.',
    type: 'website',
    images: [
      {
        url: '/og.png',
        width: 1730,
        height: 909,
        alt: 'video-use — prompt & video. Prompt something worth watching.',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'video-use — Prompt something worth watching',
    description:
      'Edits, motion, stories, and video. Browse real examples, copy a prompt, and make it yours.',
    images: ['/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link
          rel="preload"
          href="/fonts/space-grotesk-latin.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <link
          rel="preload"
          href="/fonts/inter-regular.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <link
          rel="preconnect"
          href="https://pub-ec8bfc71ab97450e915c455459d2d57d.r2.dev"
        />
      </head>
      <body>
        <McpAnnouncement />
        {children}
      </body>
    </html>
  );
}

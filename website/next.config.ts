import type { NextConfig } from 'next';

const immutable = 'public, max-age=31536000, immutable';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [
      { source: '/fonts/:path*', headers: [{ key: 'Cache-Control', value: immutable }] },
      { source: '/media/:path*', headers: [{ key: 'Cache-Control', value: immutable }] },
      { source: '/brand/:path*', headers: [{ key: 'Cache-Control', value: immutable }] },
      {
        source: '/(favicon.svg|og.png)',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=86400, stale-while-revalidate=604800' }],
      },
    ];
  },
};

export default nextConfig;

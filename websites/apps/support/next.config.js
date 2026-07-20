/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@prep/ui'],
  // Security headers applied to every route (license-neutral, pre-ship
  // hardening — Session E / E-3). A page Content-Security-Policy is
  // intentionally omitted here: Next.js injects inline scripts, so a strict
  // CSP needs nonces + careful testing. Add it only after verifying the admin
  // UI still renders. The headers below are safe by construction.
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          // Force HTTPS for two years, cover subdomains, opt into browser
          // preload lists once the cert is stable and the site is live.
          { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
          // The admin dashboard exposes reporter PII — it must not be framed
          // by a third party (clickjacking).
          { key: 'X-Frame-Options', value: 'DENY' },
          // Stop MIME sniffing on responses.
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          // Send only the origin to cross-origin targets; full URL stays same-origin.
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          // Lock down device capabilities the support site never uses.
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
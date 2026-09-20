const production = process.env.NODE_ENV === 'production';
const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  { key: 'Content-Security-Policy', value: [
    "default-src 'self'", "base-uri 'self'", "object-src 'none'", "frame-ancestors 'none'",
    `script-src 'self' 'unsafe-inline'${production ? '' : " 'unsafe-eval'"}`,
    "style-src 'self' 'unsafe-inline'", "img-src 'self' data: blob:", "font-src 'self' data:",
    `connect-src 'self'${production ? '' : ' http://localhost:* http://127.0.0.1:* ws://localhost:*'}`,
    "form-action 'self'"
  ].join('; ') },
];
const nextConfig = {
  compress: true, poweredByHeader: false, reactStrictMode: true,
  output: 'standalone',
  images: { formats: ['image/avif', 'image/webp'] },
  async headers() { return [
    { source: '/(.*)', headers: securityHeaders },
    { source: '/api/:path*', headers: [{ key: 'Cache-Control', value: 'no-store' }] },
    { source: '/sw.js', headers: [{ key: 'Cache-Control', value: 'no-cache, no-store' }] },
  ]; },
  async rewrites() {
    const gateway = process.env.API_GATEWAY_URL || 'http://127.0.0.1:8000';
    return [{ source: '/v1/:path*', destination: `${gateway}/v1/:path*` }];
  },
};
export default nextConfig;

import path from "path";
const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-XSS-Protection', value: '1; mode=block' },
];
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  async headers() {
    return [{ source: '/(.*)', headers: securityHeaders }];
  },
  async rewrites() {
    const backend = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: '/api/dashboard/:path*', destination: `${backend}/api/dashboard/:path*` },
      { source: '/api/agents', destination: `${backend}/api/agents` },
      { source: '/api/knowledge/:path*', destination: `${backend}/api/knowledge/:path*` },
      { source: '/api/workflow/:path*', destination: `${backend}/api/workflow/:path*` },
      { source: '/api/governance/:path*', destination: `${backend}/api/governance/:path*` },
      { source: '/api/integrations/:path*', destination: `${backend}/api/integrations/:path*` },
      { source: '/api/admin/:path*', destination: `${backend}/api/admin/:path*` },
    ];
  },
};
export default nextConfig;

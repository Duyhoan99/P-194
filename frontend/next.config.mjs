/** @type {import('next').NextConfig} */
const apiProxyTarget = (process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000').replace(/\/$/, '');

const nextConfig = {
  // Allow connections from Docker/VM host interfaces for dev resources
  allowedDevOrigins: ['172.28.208.1', 'localhost', '127.0.0.1'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiProxyTarget}/api/:path*`,
      },
      {
        source: '/health',
        destination: `${apiProxyTarget}/health`,
      },
    ];
  },
};

export default nextConfig;


/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow connections from Docker/VM host interfaces for dev resources
  allowedDevOrigins: ['172.28.208.1', 'localhost', '127.0.0.1'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
      {
        source: '/health',
        destination: 'http://localhost:8000/health',
      },
    ];
  },
};

export default nextConfig;


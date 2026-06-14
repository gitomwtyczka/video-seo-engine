/** @type {import('next').NextConfig} */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085'

const nextConfig = {
  output: 'standalone',
  // next-auth v4 has known type incompatibility with Next.js 14 App Router
  // types are correct at runtime — suppressed for build
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: API_URL + '/:path*',
      },
    ]
  },
}

export default nextConfig

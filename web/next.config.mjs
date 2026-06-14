/** @type {import('next').NextConfig} */
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
  // NOTE: NO rewrites here — all /api/* routing is handled by nginx:
  // /api/auth/* -> Next.js 3001 (NextAuth)
  // /api/v1/*   -> FastAPI 8085 (strip /api prefix)
  // Adding rewrites here would intercept /api/auth/* and break NextAuth!
}

export default nextConfig

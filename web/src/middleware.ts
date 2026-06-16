import { withAuth } from 'next-auth/middleware'
import { NextResponse } from 'next/server'

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token
    const pathname = req.nextUrl.pathname

    // /admin routes require is_admin flag or agency plan
    if (pathname.startsWith('/admin')) {
      const isAdmin = token?.is_admin === true
      const plan = token?.plan as string | undefined
      const isAgency = plan === 'agency'

      if (!isAdmin && !isAgency) {
        return NextResponse.redirect(new URL('/dashboard', req.url))
      }
    }

    return NextResponse.next()
  },
  {
    pages: {
      signIn: '/login',
    },
    callbacks: {
      authorized: ({ token }) => !!token,
    },
  }
)

export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*', '/admin/:path*', '/historia/:path*', '/ustawienia/:path*'],
}

import NextAuth from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'
import GoogleProvider from 'next-auth/providers/google'

// Server-side calls use internal Docker URL to avoid going through public nginx
// Client-side calls use the public API URL
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085'

const providers: any[] = []

// Only include Google provider if credentials are configured
if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    })
  )
}

providers.push(
  CredentialsProvider({
    name: 'Email',
    credentials: {
      email: { label: 'Email', type: 'email' },
      password: { label: 'Has\u0142o', type: 'password' },
    },
    async authorize(credentials) {
      if (!credentials?.email || !credentials?.password) return null
      try {
        const res = await fetch(`${BACKEND_URL}/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        })
        if (!res.ok) return null
        const data = await res.json()
        return {
          id: data.user_id || credentials.email,
          email: credentials.email,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
        }
      } catch (err) {
        console.error('[NextAuth] authorize error:', err)
        return null
      }
    },
  })
)

export const authOptions = {
  providers,
  callbacks: {
    async jwt({ token, user, account }: any) {
      if (user) {
        token.accessToken = user.accessToken
        token.refreshToken = user.refreshToken
        token.email = user.email
      }
      if (account?.provider === 'google') {
        token.provider = 'google'
      }
      return token
    },
    async session({ session, token }: any) {
      session.accessToken = token.accessToken
      session.user = session.user || {}
      session.user.email = token.email
      return session
    },
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  secret: process.env.NEXTAUTH_SECRET,
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }

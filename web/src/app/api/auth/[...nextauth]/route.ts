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

/**
 * Fetch user profile from FastAPI backend to get plan + is_admin.
 * Called in jwt callback after login and on token refresh.
 * Uses internal BACKEND_URL (Docker network) for server-side fetching.
 */
async function fetchUserProfile(accessToken: string): Promise<{ plan_id: string; is_admin: boolean } | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/v1/users/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return null
    const data = await res.json()
    return {
      plan_id: data.plan?.id ?? 'free',
      is_admin: data.is_admin ?? false,
    }
  } catch (err) {
    console.error('[NextAuth] fetchUserProfile error:', err)
    return null
  }
}

export const authOptions = {
  providers,
  callbacks: {
    async jwt({ token, user, account }: any) {
      // On initial sign-in: store tokens from authorize()
      if (user) {
        token.accessToken = user.accessToken
        token.refreshToken = user.refreshToken
        token.email = user.email
        // Fetch plan + is_admin immediately after login
        if (user.accessToken) {
          const profile = await fetchUserProfile(user.accessToken)
          if (profile) {
            token.plan = profile.plan_id
            token.is_admin = profile.is_admin
          }
        }
      }
      if (account?.provider === 'google') {
        token.provider = 'google'
        // For Google OAuth, plan is fetched from backend on first login
        // accessToken here is Google token, not our JWT — plan fetched separately
      }
      // Refresh plan on every request if we have our own accessToken
      // but only refresh every 5 minutes to avoid excessive API calls
      const now = Math.floor(Date.now() / 1000)
      const lastPlanFetch = (token.planFetchedAt as number) ?? 0
      if (token.accessToken && !user && (now - lastPlanFetch > 300)) {
        const profile = await fetchUserProfile(token.accessToken as string)
        if (profile) {
          token.plan = profile.plan_id
          token.is_admin = profile.is_admin
          token.planFetchedAt = now
        }
      }
      return token
    },
    async session({ session, token }: any) {
      session.accessToken = token.accessToken
      session.user = session.user || {}
      session.user.email = token.email
      // Expose plan and is_admin to client — used by dashboard + middleware
      session.user.plan = token.plan ?? 'free'
      session.user.is_admin = token.is_admin ?? false
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

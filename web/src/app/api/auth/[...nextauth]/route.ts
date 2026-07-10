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
      password: { label: 'Hasło', type: 'password' },
    },
    async authorize(credentials) {
      if (!credentials?.email || !credentials?.password) return null
      try {
        const res = await fetch(`${BACKEND_URL}/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            username: credentials.email,
            password: credentials.password,
          }),
        })
        if (!res.ok) {
          console.error('[NextAuth] Backend returned', res.status)
          return null
        }
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

/**
 * CO: Wymienia Google id_token na nasz backend JWT (access_token + refresh_token).
 *
 * PO CO: NextAuth GoogleProvider dostarcza account.id_token w jwt callback,
 * ale NextAuth NIE ma naszego JWT — bez token-exchange token.accessToken jest null
 * i plan refresh nigdy nie działa dla Google OAuth (warunek if token.accessToken).
 * Ten krok naprawia bug plan=free przy pierwszym logowaniu przez Google.
 *
 * JAK: Wysyła id_token do POST /v1/auth/google/token-exchange (backend weryfikuje
 * przez Google tokeninfo, upsertuje usera, zwraca nasz JWT pair).
 */
async function exchangeGoogleToken(
  idToken: string
): Promise<{ accessToken: string; refreshToken: string } | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/v1/auth/google/token-exchange`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken }),
    })
    if (!res.ok) {
      console.error('[NextAuth] google token-exchange failed:', res.status, await res.text())
      return null
    }
    const data = await res.json()
    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
    }
  } catch (err) {
    console.error('[NextAuth] exchangeGoogleToken error:', err)
    return null
  }
}

export const authOptions = {
  providers,
  callbacks: {
    async jwt({ token, user, account }: any) {
      // --- Credentials login ---
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
            token.planFetchedAt = Math.floor(Date.now() / 1000)
          }
        }
      }

      // --- Google OAuth first sign-in ---
      // account object is only present on first sign-in (subsequent calls: account=null)
      if (account?.provider === 'google') {
        token.provider = 'google'
        token.email = token.email || account.email

        // Exchange Google id_token for our backend JWT so we can:
        // 1. Store our accessToken (needed for plan refresh logic below)
        // 2. Fetch plan + is_admin immediately (no 5-min wait)
        const googleIdToken = account.id_token
        if (googleIdToken) {
          const exchanged = await exchangeGoogleToken(googleIdToken)
          if (exchanged) {
            token.accessToken = exchanged.accessToken
            token.refreshToken = exchanged.refreshToken
            // Fetch plan immediately using our fresh backend JWT
            const profile = await fetchUserProfile(exchanged.accessToken)
            if (profile) {
              token.plan = profile.plan_id
              token.is_admin = profile.is_admin
              token.planFetchedAt = Math.floor(Date.now() / 1000)
            }
          } else {
            // Fallback: token-exchange failed (backend down / misconfigured)
            // Force plan refresh on next token call (within 1 min vs default 5 min)
            token.planFetchedAt = 0
          }
        } else {
          // No id_token from Google — force early refresh
          token.planFetchedAt = 0
        }
      }

      // --- Periodic plan refresh (every 5 minutes) ---
      // Applies to all providers once token.accessToken is populated
      const now = Math.floor(Date.now() / 1000)
      const lastPlanFetch = (token.planFetchedAt as number) ?? 0
      if (token.accessToken && !user && !account && (now - lastPlanFetch > 300)) {
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

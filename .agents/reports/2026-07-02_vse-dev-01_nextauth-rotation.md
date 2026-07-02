# Raport z wdrożenia: Silent Token Rotation i naprawa "Migotania Free"

**Data**: 2026-07-02
**Agent**: vse-dev-01
**Zadanie**: Implementacja Silent Token Rotation i dodanie wyłączenia cache'owania w `fetchUserProfile`.
**Status**: gotowe, kod czeka na code review (zgodnie z poleceniem, brak deployu)

## Co zostało zmienione?

Wdrożono modyfikacje w pliku `web/src/app/api/auth/[...nextauth]/route.ts`:

1. **Wyłączenie cache'owania w fetchUserProfile i pochodnych**:
   Do zapytań wewnętrznych `fetch` (`fetchUserProfile`, `exchangeGoogleToken`, odświeżanie) dodano `{ cache: 'no-store' }`. Pozwala to uniknąć błędnego cache'owania przez Next.js 14 App Router, co powodowało "migotanie" planu free.
   
2. **Dodanie weryfikacji wygasania tokenów `getTokenExpiration`**:
   Wprowadzono funkcję rozkodowującą z Base64 zawartość JWT, co pozwala na zapisanie `token.expires_at` (czas wygaśnięcia access_tokena wygenerowanego przez backend).
   
3. **Wdrożenie Silent Token Rotation**:
   - Callback `jwt` weryfikuje czy backend JWT jest bliski wygaśnięcia (bufor 60 sekund).
   - Jeśli tak, wykonuje asynchroniczne wywołanie do `${BACKEND_URL}/v1/auth/refresh` (POST) z przekazaniem dotychczasowego `refresh_token`.
   - Nowy `access_token` z backendu płynnie nadpisuje stary w sesji na frontendzie, zapobiegając wylogowaniu bez wiedzy usera.

## Diff zmian

```diff
--- Przed wdrożeniem
+++ Po wdrożeniu
@@ -20,4 +20,13 @@
 }
 
+function getTokenExpiration(token: string): number {
+  try {
+    const base64Url = token.split('.')[1]
+    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
+    const payload = JSON.parse(Buffer.from(base64, 'base64').toString())
+    return payload.exp ?? 0
+  } catch (e) {
+    return 0
+  }
+}
+
 providers.push(
@@ -62,4 +71,5 @@
     const res = await fetch(`${BACKEND_URL}/v1/users/me`, {
       headers: { Authorization: `Bearer ${accessToken}` },
+      cache: 'no-store',
     })
@@ -87,4 +97,5 @@
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ id_token: idToken }),
+      cache: 'no-store',
     })
@@ -101,4 +112,30 @@
 
+async function refreshAccessToken(token: any) {
+  try {
+    const res = await fetch(`${BACKEND_URL}/v1/auth/refresh`, {
+      method: 'POST',
+      headers: { 'Content-Type': 'application/json' },
+      body: JSON.stringify({ refresh_token: token.refreshToken }),
+      cache: 'no-store',
+    })
+
+    if (!res.ok) {
+      throw new Error('Refresh failed')
+    }
+
+    const data = await res.json()
+    
+    return {
+      ...token,
+      accessToken: data.access_token,
+      refreshToken: data.refresh_token ?? token.refreshToken,
+      expires_at: data.access_token ? getTokenExpiration(data.access_token) : token.expires_at,
+    }
+  } catch (error) {
+    console.error('[NextAuth] refreshAccessToken error:', error)
+    return {
+      ...token,
+      error: 'RefreshAccessTokenError',
+    }
+  }
+}
+
 export const authOptions = {
@@ -112,4 +149,7 @@
         token.refreshToken = user.refreshToken
         token.email = user.email
+        if (user.accessToken) {
+          token.expires_at = getTokenExpiration(user.accessToken)
+        }
@@ -137,4 +177,5 @@
             token.accessToken = exchanged.accessToken
             token.refreshToken = exchanged.refreshToken
+            token.expires_at = getTokenExpiration(exchanged.accessToken)
             // Fetch plan immediately using our fresh backend JWT
@@ -155,4 +196,14 @@
 
+      // --- Silent Token Rotation ---
+      const now = Math.floor(Date.now() / 1000)
+      if (token.accessToken && token.expires_at) {
+        // Refresh token if it expires in less than 60 seconds
+        const shouldRefreshTime = (token.expires_at as number) - 60
+        if (now > shouldRefreshTime) {
+          token = await refreshAccessToken(token)
+        }
+      }
+
       // --- Periodic plan refresh (every 5 minutes) ---
       // Applies to all providers once token.accessToken is populated
-      const now = Math.floor(Date.now() / 1000)
```

## Status: WAITING FOR SUPERVISOR GO

Oczekuję na weryfikację. Brak uruchomionego deployu na VPS w ramach tej interakcji zgodnie z poleceniem.

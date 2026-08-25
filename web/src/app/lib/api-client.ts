/**
 * CO: Centralny klient HTTP z JWT interceptorem.
 * PO CO: Eliminuje badge 401 przy ?job_id= — automatyczny refresh tokena NextAuth.
 *        Zastępuje rozproszony raw fetch we wszystkich hookach dashboardu.
 * JAK: fetchWithAuth() pobiera token z getSession(), na 401 robi refresh + retry,
 *      jeśli nadal 401 — signOut().
 *
 * D1 (2026-08-25, shadow-strateg): Sprint 5C — JWT interceptor.
 */
import { getSession, signOut } from 'next-auth/react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const session = await getSession()
  const token = (session as { accessToken?: string } | null)?.accessToken

  const baseHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
  const merged: Record<string, string> = {
    ...baseHeaders,
    ...(options.headers as Record<string, string> | undefined ?? {}),
  }

  const res = await fetch(url, { ...options, headers: merged })

  if (res.status === 401) {
    // Try refreshing session once
    const refreshed = await getSession()
    const newToken = (refreshed as { accessToken?: string } | null)?.accessToken
    if (newToken && newToken !== token) {
      const retryHeaders = { ...merged, Authorization: `Bearer ${newToken}` }
      const retry = await fetch(url, { ...options, headers: retryHeaders })
      if (retry.status !== 401) return retry
    }
    await signOut()
    throw new Error('Session expired — signed out')
  }

  return res
}

export async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetchWithAuth(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export async function apiPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  const res = await fetchWithAuth(`${API_URL}${path}`, {
    method: 'POST',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function apiDelete(path: string): Promise<boolean> {
  const res = await fetchWithAuth(`${API_URL}${path}`, { method: 'DELETE' })
  return res.ok || res.status === 204
}

export { fetchWithAuth as apiClient }

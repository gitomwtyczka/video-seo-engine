'use client'
/**
 * CO: Wrapper strony /dashboard z Suspense dla useSearchParams
 * PO CO: Next.js 14 App Router wymaga Suspense boundary wokół
 *        komponentów używających useSearchParams(). Bez tego build fails.
 * JAK: Re-eksportuje oryginalny DashboardPage opakowany w Suspense.
 *      Importuje useJobLoader i przekazuje dane do DashboardPage.
 */
import { Suspense } from 'react'
import DashboardInner from './dashboard-inner'

export default function DashboardPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500" />
      </div>
    }>
      <DashboardInner />
    </Suspense>
  )
}

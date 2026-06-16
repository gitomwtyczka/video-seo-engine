'use client'
/**
 * CO: Hook useJobLoader — ładuje dane job'u z historii na podstawie ?job_id w URL
 * PO CO: Umożliwia stronie /historia linkowanie do /dashboard?job_id=X
 *        który załaduje wyniki z DB zamiast generować od nowa.
 * JAK: useSearchParams() → jeśli job_id → GET /v1/jobs/{id} → zwróć schema_data
 */
import { useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'

interface JobData {
  id: string
  video_url: string
  video_id: string | null
  status: string
  schema_data: Record<string, unknown> | null
}

export function useJobLoader() {
  const searchParams = useSearchParams()
  const jobId = searchParams.get('job_id')
  const [jobData, setJobData] = useState<JobData | null>(null)
  const [jobLoading, setJobLoading] = useState(false)
  const [jobError, setJobError] = useState('')

  useEffect(() => {
    if (!jobId) return

    const loadJob = async () => {
      setJobLoading(true)
      setJobError('')
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
        const res = await fetch(`${apiUrl}/v1/jobs/${jobId}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        if (!data.schema_data) {
          throw new Error('Ten job nie ma zapisanych wyników SEO. Wygeneruj ponownie.')
        }
        setJobData(data)
      } catch (e: unknown) {
        setJobError(e instanceof Error ? e.message : 'Błąd ładowania danych')
      } finally {
        setJobLoading(false)
      }
    }

    loadJob()
  }, [jobId])

  return { jobId, jobData, jobLoading, jobError }
}

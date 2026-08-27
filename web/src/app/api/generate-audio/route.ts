import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData()
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085'
    const authHeader = req.headers.get('authorization')
    
    // Proxy request to backend
    const res = await fetch(`${apiBase}/v1/audio/generate`, {
      method: 'POST',
      body: formData,
      headers: {
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
    })

    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal Server Error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

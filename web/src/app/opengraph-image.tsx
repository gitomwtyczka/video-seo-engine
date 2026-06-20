import { ImageResponse } from 'next/og'

export const runtime = 'edge'

export const alt = 'VSE — Video SEO Engine'
export const size = {
  width: 1200,
  height: 630,
}
export const contentType = 'image/png'

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)',
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'Inter, sans-serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginBottom: 32 }}>
          <svg
            width="80"
            height="80"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M6 4L18 12L6 20V4Z" fill="url(#og-grad)" />
            <rect x="14" y="14" width="3" height="6" rx="0.5" fill="url(#og-grad)" opacity="0.7" />
            <rect x="18" y="10" width="3" height="10" rx="0.5" fill="url(#og-grad)" opacity="0.9" />
            <defs>
              <linearGradient id="og-grad" x1="0" y1="0" x2="24" y2="24">
                <stop offset="0%" stopColor="#3B82F6" />
                <stop offset="100%" stopColor="#8B5CF6" />
              </linearGradient>
            </defs>
          </svg>
          <span
            style={{
              fontSize: 72,
              fontWeight: 800,
              background: 'linear-gradient(135deg, #3B82F6, #8B5CF6)',
              backgroundClip: 'text',
              color: 'transparent',
              letterSpacing: '-2px',
            }}
          >
            VSE
          </span>
        </div>
        <span
          style={{
            fontSize: 36,
            color: '#CBD5E1',
            fontWeight: 400,
            letterSpacing: '1px',
          }}
        >
          Video SEO Engine
        </span>
        <span
          style={{
            fontSize: 20,
            color: '#64748B',
            marginTop: 16,
          }}
        >
          Automatyczna optymalizacja SEO filmów YouTube
        </span>
      </div>
    ),
    { ...size }
  )
}

import { ImageResponse } from 'next/og'

export const runtime = 'edge'

export const size = {
  width: 180,
  height: 180,
}
export const contentType = 'image/png'

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 24,
          background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)',
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 32,
        }}
      >
        <svg
          width="120"
          height="120"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M6 4L18 12L6 20V4Z" fill="url(#grad)" />
          <rect x="14" y="14" width="3" height="6" rx="0.5" fill="url(#grad)" opacity="0.7" />
          <rect x="18" y="10" width="3" height="10" rx="0.5" fill="url(#grad)" opacity="0.9" />
          <defs>
            <linearGradient id="grad" x1="0" y1="0" x2="24" y2="24">
              <stop offset="0%" stopColor="#3B82F6" />
              <stop offset="100%" stopColor="#8B5CF6" />
            </linearGradient>
          </defs>
        </svg>
      </div>
    ),
    { ...size }
  )
}

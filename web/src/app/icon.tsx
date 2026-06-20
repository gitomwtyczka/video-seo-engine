import { ImageResponse } from 'next/og'

// Route segment config
export const runtime = 'edge'

// Image metadata
export const size = {
  width: 32,
  height: 32,
}
export const contentType = 'image/png'

// Image generation
export default function Icon() {
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
          borderRadius: 4,
        }}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Play triangle */}
          <path
            d="M6 4L18 12L6 20V4Z"
            fill="url(#grad)"
            stroke="none"
          />
          {/* Growth bar 1 */}
          <rect x="14" y="14" width="3" height="6" rx="0.5" fill="url(#grad)" opacity="0.7" />
          {/* Growth bar 2 */}
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
    {
      ...size,
    }
  )
}

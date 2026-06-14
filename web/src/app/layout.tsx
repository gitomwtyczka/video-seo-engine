import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: 'VSE — Video SEO Engine | Najlepsze Video SEO',
  description: 'Automatyzuj optymalizację SEO swoich filmów YouTube. Schema VideoObject, rozdziały AI, FAQ — gotowe w sekundy.',
  keywords: ['video seo', 'youtube seo', 'schema.org', 'video schema', 'seo wordpress'],
  openGraph: {
    title: 'VSE — Video SEO Engine',
    description: 'Automatyczna optymalizacja SEO filmów YouTube',
    url: 'https://vse.impresjapr.pl',
    siteName: 'VSE',
    locale: 'pl_PL',
    type: 'website',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" className={inter.variable}>
      <body className="bg-dark-950 text-white antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

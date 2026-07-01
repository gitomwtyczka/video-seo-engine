import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import Link from 'next/link'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXTAUTH_URL || 'https://vse.impresjapr.pl'),
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
      <body className="bg-dark-950 text-white antialiased flex flex-col min-h-screen">
        <Providers>
          <div className="flex-1">{children}</div>
          <footer className="border-t border-white/5 py-4 px-6 text-center">
            <p className="text-gray-600 text-xs">
              &copy; {new Date().getFullYear()} IMPRESJA PR Sp. z o.o. &bull;{' '}
              <Link href="/regulamin" className="hover:text-gray-400 transition-colors">Regulamin</Link>
              {' '}&bull;{' '}
              <Link href="/polityka-prywatnosci" className="hover:text-gray-400 transition-colors">Polityka Prywatności</Link>
            </p>
          </footer>
        </Providers>
      </body>
    </html>
  )
}

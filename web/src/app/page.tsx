import Link from 'next/link'
import { Video, Zap, Shield, BarChart3, ArrowRight, CheckCircle } from 'lucide-react'

const features = [
  {
    icon: Zap,
    title: 'Schema VideoObject w sekundy',
    desc: 'AI analizuje transkrypt YouTube i generuje pełny JSON-LD: VideoObject, Clip, FAQ.'
  },
  {
    icon: BarChart3,
    title: 'Wyniki potwierdzone benchmarkiem',
    desc: 'Prawy.pl: 8/10 w audycie Google vs TVP Info 3/10. Twoja przewaga nad konkurrencją.'
  },
  {
    icon: Shield,
    title: 'Google 2026 — zawsze aktualny',
    desc: 'Automatyczne dostosowanie do wymagn Google. Działamy zgodnie z najnowszymi wytycznymi.'
  },
  {
    icon: Video,
    title: 'One-click inject do WordPress',
    desc: 'Schema trafia bezpośrednio do Twojego artykułu przez REST API. Zero edycji ręcznej.'
  },
]

const plans = [
  {
    name: 'Free',
    price: '0',
    quota: '5 filmów / mies.',
    features: ['Schema VideoObject + Clip + FAQ', 'Wtyczka WordPress v3.0 w cenie', 'Cross-Language → język panelu', '1 portal WP'],
    cta: 'Zacznij za darmo',
    href: '/register',
    highlighted: false,
  },
  {
    name: 'Starter',
    price: '49',
    quota: '30 filmów / mies.',
    features: ['Wszystko z Free', 'WordPress Auto-Publish (3 portale)', 'Cross-Language: wideo → SEO w języku panelu', 'Opcjonalny Add-on: Pakiet Wielojęzyczny (+29 zł/mies.)', 'VSE Local Runner (.zip)'],
    cta: 'Wybierz Starter',
    href: '/register?plan=starter',
    highlighted: false,
  },
  {
    name: 'Pro',
    price: '149',
    quota: '110 filmów / mies.',
    features: ['Wszystko ze Starter', '10 portali WP', '🌐 Pakiet Wielojęzyczny (8 języków) W CENIE', 'Tłumaczenie poszczególnych zakładek 1 kliknięciem', 'Pakiet analiz Premium AI', 'API Access', 'Priority support'],
    cta: 'Wybierz Pro',
    href: '/register?plan=pro',
    highlighted: true,
  },
  {
    name: 'Agencja',
    price: '499',
    quota: '250 filmów / mies.',
    features: ['Wszystko z Pro', '50 portali WP', '🌐 Pełny Multi-Language (8 języków) bez limitu adaptacji', 'Moduł ShortMachine (AI Shorts 9:16 + NLE)', 'White-label & SLA 99.9%'],
    cta: 'Wybierz Agency',
    href: '/register?plan=agency',
    highlighted: false,
  },
]

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 hover:opacity-90 transition-opacity">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center">
              <Video className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">VSE</span>
            <span className="text-dark-400 text-sm ml-1">Video SEO Engine</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-dark-300 hover:text-white transition-smooth text-sm">
              Zaloguj
            </Link>
            <Link
              href="/register"
              className="px-4 py-2 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium transition-smooth glow-sm"
            >
              Zacznij za darmo
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-24 px-6 overflow-hidden">
        <div className="absolute inset-0 bg-hero-glow" />
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-brand-500/10 rounded-full blur-3xl" />

        <div className="relative max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass text-sm text-brand-300 mb-8 border border-brand-500/20">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Benchmark: 8/10 vs konkurencja 2–3/10
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 leading-tight">
            Video SEO na
            <span className="text-gradient"> najwyższym</span>
            <br />poziomie
          </h1>

          <p className="text-xl text-dark-300 max-w-2xl mx-auto mb-10 leading-relaxed">
            Wklej URL YouTube, otrzymaj Schema VideoObject, rozdziały AI i FAQ.
            Wstrzyknij do WordPress jednym kliknięciem. Wyprzedź konkurencję w Google.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/register"
              className="px-8 py-4 rounded-xl bg-brand-500 hover:bg-brand-400 text-white font-semibold text-lg transition-smooth glow-brand flex items-center gap-2"
            >
              Zacznij za darmo <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="/docs"
              className="px-8 py-4 rounded-xl glass hover:bg-white/5 text-white font-medium text-lg transition-smooth"
            >
              Zobacz API docs
            </Link>
          </div>

          <p className="mt-6 text-dark-400 text-sm">Bez karty kredytowej • 5 filmów za darmo • Setup w 60 sekund</p>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            Wszystko czego potrzebujesz do
            <span className="text-gradient"> video SEO</span>
          </h2>
          <p className="text-dark-400 text-center mb-16 max-w-2xl mx-auto">
            Jeden pipeline, pełna automatyzacja — od YouTube po WordPress.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {features.map((f) => (
              <div key={f.title} className="glass rounded-2xl p-8 hover:border-brand-500/30 transition-smooth group">
                <div className="w-12 h-12 rounded-xl bg-brand-500/10 flex items-center justify-center mb-4 group-hover:bg-brand-500/20 transition-smooth">
                  <f.icon className="w-6 h-6 text-brand-400" />
                </div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-dark-300 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>

          {/* Dedicated WordPress Plugin Lead-Magnet Banner */}
          <div className="mt-12 glass rounded-2xl border border-brand-500/30 p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-2 max-w-2xl">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-3 py-0.5 rounded-full text-xs font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30 uppercase tracking-wider">
                  🔌 Oficjalna Wtyczka WordPress v3.0
                </span>
                <span className="text-xs text-green-400 font-semibold">
                  ✓ Gutenberg + RankMath / Yoast / SEOPress + Auto-Parowanie
                </span>
              </div>
              <h3 className="text-xl font-bold text-white">
                VSE Video SEO v3.0 dla WordPress — 1-klikowa publikacja i Schema JSON-LD
              </h3>
              <p className="text-sm text-dark-300 leading-relaxed">
                Pobierz darmową wtyczkę <code className="text-brand-300">vse-video-seo.zip</code>, wklej klucz API <code className="text-brand-300">vse_live_...</code> aby automatycznie sparować portal bez Application Passwords i wstrzykuj czyste znaczniki <strong className="text-white">VideoObject + Clip (Key Moments) + FAQPage</strong> do sekcji <code className="text-brand-300">&lt;head&gt;</code> (5 filmów / mies. za darmo).
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <a
                href="/v1/plugin/download"
                className="px-6 py-3 rounded-xl font-semibold text-sm bg-brand-500 hover:bg-brand-400 text-white transition-smooth glow-sm whitespace-nowrap"
              >
                ⬇️ Pobierz wtyczkę (.zip)
              </a>
              <Link
                href="/register?utm_source=landing&utm_medium=wp_plugin_banner"
                className="px-5 py-3 rounded-xl font-medium text-sm glass hover:bg-white/10 text-white transition-smooth whitespace-nowrap"
              >
                Odbierz darmowy klucz API →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-6 bg-dark-950/50">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            Przejrzyste <span className="text-gradient">ceny</span>
          </h2>
          <p className="text-dark-400 text-center mb-16">Zacznij za darmo, rozwijaj się w swoim tempie.</p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`relative glass rounded-2xl p-8 flex flex-col transition-smooth ${
                  plan.highlighted
                    ? 'border-brand-500/50 glow-brand scale-105'
                    : 'hover:border-white/15'
                }`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-brand-500 text-white text-xs font-semibold">
                    Najpopularniejszy
                  </div>
                )}
                <div className="mb-6">
                  <h3 className="text-lg font-bold mb-1">{plan.name}</h3>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold">{plan.price}</span>
                    <span className="text-dark-400">PLN/mies.</span>
                  </div>
                  <p className="text-dark-400 text-sm mt-1">{plan.quota}</p>
                </div>
                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-center gap-2 text-sm text-dark-200">
                      <CheckCircle className="w-4 h-4 text-brand-400 shrink-0" />
                      {feat}
                    </li>
                  ))}
                </ul>
                <Link
                  href={plan.href || "/register"}
                  className={`w-full py-3 rounded-xl text-center font-medium transition-smooth ${
                    plan.highlighted
                      ? 'bg-brand-500 hover:bg-brand-400 text-white'
                      : 'glass hover:bg-white/5 text-white'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>

          {/* Dedicated Add-on: Pakiet Wielojęzyczny */}
          <div className="mt-12 glass rounded-2xl border border-brand-500/30 p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-2 max-w-2xl">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-3 py-0.5 rounded-full text-xs font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30 uppercase tracking-wider">
                  Add-on dla planu Starter
                </span>
                <span className="text-xs text-green-400 font-semibold">
                  ✨ W planach Pro i Agency w cenie!
                </span>
              </div>
              <h3 className="text-xl font-bold text-white">
                🌐 Add-on: Pakiet Wielojęzyczny — +29 PLN / mies.
              </h3>
              <p className="text-sm text-dark-300 leading-relaxed">
                Generuj materiały SEO, artykuły, streszczenia i posty Social Media w <strong className="text-white">8 językach</strong> (🇵🇱 PL, 🇬🇧 EN, 🇩🇪 DE, 🇪🇸 ES, 🇫🇷 FR, 🇮🇹 IT, 🇺🇦 UK, 🇵🇹 PT) oraz tłumacz poszczególne zakładki 1 kliknięciem bez zużywania limitu wideo.
              </p>
            </div>
            <Link
              href="/cennik"
              className="px-6 py-3 rounded-xl font-semibold text-sm bg-brand-500 hover:bg-brand-400 text-white transition-smooth glow-sm whitespace-nowrap"
            >
              Sprawdź w Cenniku →
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2 hover:opacity-90 transition-opacity">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-brand-500 to-purple-600" />
            <span className="font-semibold">VSE</span>
            <span className="text-dark-400 text-sm">— ImpresjaAI</span>
          </Link>
          <p className="text-dark-400 text-sm">© 2026 ImpresjaAI. Wszelkie prawa zastrzeżone.</p>
        </div>
      </footer>
    </main>
  )
}

'use client'
import Link from 'next/link';

export default function ShortMachinePagePL() {
  return (
    <div className="min-h-screen text-gray-100 font-sans" style={{ background: 'linear-gradient(135deg, #070d1f 0%, #1a0533 50%, #070d1f 100%)' }}>
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-1/4 w-96 h-96 bg-purple-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
        <div className="absolute bottom-40 right-1/4 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-pulse" style={{animationDelay:'2s'}} />
      </div>

      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4" style={{background:'rgba(7,13,31,0.8)',backdropFilter:'blur(12px)',borderBottom:'1px solid rgba(255,255,255,0.05)'}}>
        <div className="font-black text-xl" style={{background:'linear-gradient(90deg,#a855f7,#06b6d4)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>ShortMachine</div>
        <div className="flex gap-3">
          <Link href="/shortmachine" className="text-sm text-gray-400 hover:text-white px-3 py-1">PL</Link>
          <Link href="/shortmachine/en" className="text-sm text-gray-400 hover:text-white px-3 py-1">EN</Link>
          <Link href="/shortmachine/es" className="text-sm text-gray-400 hover:text-white px-3 py-1">ES</Link>
          <Link href="/dashboard" className="px-4 py-2 rounded-lg text-sm font-bold text-white" style={{background:'linear-gradient(135deg,#7c3aed,#06b6d4)'}}>Panel</Link>
        </div>
      </nav>

      <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-4 pt-20">
        <div className="mb-8 relative">
          <div className="absolute inset-0 bg-purple-500 rounded-full blur-3xl opacity-30 scale-150" />
          <svg width="120" height="120" viewBox="0 0 120 120" className="relative z-10 mx-auto">
            <rect x="10" y="20" width="100" height="80" rx="8" fill="none" stroke="url(#grad1)" strokeWidth="3"/>
            <rect x="10" y="20" width="20" height="15" rx="2" fill="url(#grad1)" opacity="0.6"/>
            <rect x="10" y="45" width="20" height="15" rx="2" fill="url(#grad1)" opacity="0.6"/>
            <rect x="10" y="70" width="20" height="15" rx="2" fill="url(#grad1)" opacity="0.6"/>
            <rect x="90" y="20" width="20" height="15" rx="2" fill="url(#grad1)" opacity="0.6"/>
            <rect x="90" y="45" width="20" height="15" rx="2" fill="url(#grad1)" opacity="0.6"/>
            <rect x="90" y="70" width="20" height="15" rx="2" fill="url(#grad1)" opacity="0.6"/>
            <circle cx="50" cy="68" r="8" fill="none" stroke="url(#grad2)" strokeWidth="2.5"/>
            <circle cx="70" cy="68" r="8" fill="none" stroke="url(#grad2)" strokeWidth="2.5"/>
            <line x1="56" y1="63" x2="78" y2="45" stroke="url(#grad2)" strokeWidth="2.5" strokeLinecap="round"/>
            <line x1="64" y1="63" x2="42" y2="45" stroke="url(#grad2)" strokeWidth="2.5" strokeLinecap="round"/>
            <defs>
              <linearGradient id="grad1" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#a855f7"/>
                <stop offset="100%" stopColor="#06b6d4"/>
              </linearGradient>
              <linearGradient id="grad2" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#06b6d4"/>
                <stop offset="100%" stopColor="#a855f7"/>
              </linearGradient>
            </defs>
          </svg>
        </div>

        <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
          <span className="text-white">Twoje </span>
          <span style={{background:'linear-gradient(90deg,#a855f7,#06b6d4)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>YouTube Shorts.</span>
          <br/>
          <span className="text-white">Bez renderowania. </span>
          <span style={{background:'linear-gradient(90deg,#06b6d4,#a855f7)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>Gratis.</span>
        </h1>

        <p className="text-xl text-gray-300 max-w-2xl mx-auto mb-10 leading-relaxed">
          Wklej link YouTube. Za 60 sekund dostajesz pakiet SRT z zaznaczonymi momentami do cięcia w Premiere Pro lub DaVinci Resolve. AI wybiera haki, emocje i pointy za Ciebie.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12">
          <Link href="/dashboard" className="px-8 py-4 rounded-xl font-bold text-lg text-white transition-all hover:scale-105" style={{background:'linear-gradient(135deg,#7c3aed,#06b6d4)',boxShadow:'0 0 30px rgba(124,58,237,0.5)'}}>Zacznij za darmo →</Link>
          <a href="#jak-dziala" className="px-8 py-4 rounded-xl font-bold text-lg text-gray-300 border border-gray-600 hover:border-purple-500 transition-all">Zobacz jak działa</a>
        </div>

        <div className="flex gap-8 justify-center text-center">
          <div><div className="text-2xl font-bold text-white">60s</div><div className="text-xs text-gray-400">czas generowania</div></div>
          <div className="w-px bg-gray-700" />
          <div><div className="text-2xl font-bold text-white">4</div><div className="text-xs text-gray-400">pliki w pakiecie</div></div>
          <div className="w-px bg-gray-700" />
          <div><div className="text-2xl font-bold text-white">$0</div><div className="text-xs text-gray-400">na start</div></div>
        </div>
      </section>

      <section id="jak-dziala" className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="text-3xl font-bold mb-12">Jak to działa</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">🔗</span>
              <h3 className="text-xl font-bold mb-3 text-center">1. Wklej link YouTube</h3>
              <p className="text-gray-400 text-center">AI pobiera transkrypt i analizuje treść. Identyfikuje momenty z najwyższym potencjałem na viral hook, emocjonalną puentet i profesjonalne insight.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">📦</span>
              <h3 className="text-xl font-bold mb-3 text-center">2. Pobierz pakiet SRT</h3>
              <p className="text-gray-400 text-center">4 pliki gotowe w sekundę. Pełna transkrypcja, napisy w obszarach shortów i markery cięć dla Premiere.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">✂️</span>
              <h3 className="text-xl font-bold mb-3 text-center">3. Tnij w Premiere w 5 sekund</h3>
              <p className="text-gray-400 text-center">Przeciągnij shorts_markers.srt na ścieżkę Captions. Na osi czasu pojawiają się kolorowe bloki z tytułami shortów. Tnij żyletką bez szukania momentów.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-3xl font-bold mb-12">Co dostajesz</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">🎞️</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">pelny_film.srt</h3>
              <p className="text-gray-300 text-center">Pełna transkrypcja wideo z timestampami. Można wprost załadować jako YouTube Closed Captions.</p>
              <p className="text-xs text-violet-400 mt-3 text-center">→ Wgraj jako CC na YouTube — więcej wyświetlen od algorytmu</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">💬</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">napisy_shortow.srt</h3>
              <p className="text-gray-300 text-center">Napisy tylko w obszarach wybranych przez AI. Do importu jako ścieżka napisów w Premiere lub DaVinci.</p>
              <p className="text-xs text-violet-400 mt-3 text-center">→ Import do Premiere: ścieżka Captions gotowa</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">🎯</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">shorts_markers.srt</h3>
              <p className="text-gray-300 text-center">Kluczowy plik: duże bloki [SHORT 1: Tytuł] na osi czasu. Drag & drop na Premiere = wizualne markery cięć natychmiast.</p>
              <p className="text-xs text-violet-400 mt-3 text-center">→ Drag & drop na timeline = kolorowe bloki cięć w 5 sekund</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">📑</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">chapters.txt</h3>
              <p className="text-gray-300 text-center">Gotowy blok YouTube Chapters do wklejenia w opis wideo. YouTube tworzy klikalne rozdziały na pasku odtwarzacza.</p>
              <p className="text-xs text-violet-400 mt-3 text-center">→ Klik rozdziału w telefonie → Remix → Edit into Short</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-3xl font-bold mb-12">Cennik</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col">
              <h3 className="text-2xl font-bold mb-2">🆓 FREE</h3>
              <div className="text-3xl font-extrabold mb-6">$0<span className="text-lg text-gray-500 font-normal">/mc</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ 2 filmy / miesiąc</li>
                <li>✅ Unlimited shortów z każdego filmu</li>
                <li>✅ Gotowe w 60 sekund</li>
                <li>✅ Bez karty kredytowej</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-white/10 hover:bg-white/20 rounded-lg font-semibold transition border border-white/20">
                Wybierz
              </Link>
            </div>
            
            <div className="bg-white/10 backdrop-blur-sm border-2 border-purple-500 rounded-2xl p-8 flex flex-col relative transform md:-translate-y-4" style={{boxShadow: '0 0 40px rgba(124,58,237,0.3)'}}>
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-purple-500 to-cyan-500 text-white px-4 py-1 text-sm font-bold rounded-full shadow-lg">Polecany</div>
              <h3 className="text-2xl font-bold mb-2">⚡ ADVANCED</h3>
              <div className="text-3xl font-extrabold mb-6" style={{background:'linear-gradient(90deg,#a855f7,#06b6d4)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>$9<span className="text-lg text-gray-400 font-normal">/mc</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ 10 filmów / miesiąc</li>
                <li>✅ Unlimited shortów z każdego filmu</li>
                <li>✅ Filmy do 45 minut</li>
                <li>✅ Historia i zapis analiz</li>
                <li>✅ Integracja z kanałem YT</li>
                <li>✅ Priorytetowe wsparcie</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-gradient-to-r from-violet-600 to-cyan-500 hover:from-violet-500 hover:to-cyan-400 rounded-lg font-semibold transition text-white shadow-lg">
                Kup ADVANCED
              </Link>
            </div>
            
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col opacity-80">
              <h3 className="text-2xl font-bold mb-2">🏢 ENTERPRISE</h3>
              <div className="text-3xl font-extrabold mb-6">Skontaktuj się</div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ Wszystko z ADVANCED</li>
                <li>✅ Nielimitowane filmy / mc</li>
                <li>✅ Filmy powyżej 45 minut</li>
                <li>✅ API access</li>
                <li>✅ Automatyczne renderowanie</li>
                <li>✅ Dedykowany support</li>
              </ul>
              <a href="mailto:kontakt@impresjapr.pl" className="block text-center py-3 bg-white/10 hover:bg-white/20 rounded-lg font-semibold transition border border-white/20">
                Zapytaj o wycenę
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="text-3xl font-bold mb-12">FAQ</h2>
          <div className="space-y-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">Czy muszę instalować cokolwiek?</h4>
              <p className="text-gray-400">Nie. ShortMachine działa w 100% w przeglądarce. Potrzebujesz tylko Premiere Pro lub DaVinci Resolve do montażu.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">Jak AI wybiera momenty do shortów?</h4>
              <p className="text-gray-400">Nasz model analizuje transkrypt pod kątem trzech typów: Emotional (silne emocje, kontrowersja), Professional (ekspertyza, insight) i Custom (Twój własny query). Każdy kandydat dostaje ocenę Hook-Body-Punchline.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">Czy mogę użyć z dowolnym wideo YouTube?</h4>
              <p className="text-gray-400">Tak, o ile wideo ma dostępne napisy (CC). Większość publicznych wideo je ma.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">Co daje SRT PRO vs FREE?</h4>
              <p className="text-gray-400">FREE: 3 shorty na film. PRO: nielimitowane shorty, historia wideo, integracja z kanałem YouTube (automatyczne tytuły i opisy po publikacji).</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 relative z-10 text-center px-6">
        <h2 className="text-4xl font-bold mb-8">Gotowy przyspieszyć montaż?</h2>
        <Link href="/dashboard" className="inline-block px-10 py-4 font-bold rounded-xl text-lg text-white transition-all hover:scale-105" style={{background:'linear-gradient(135deg,#7c3aed,#06b6d4)',boxShadow:'0 0 30px rgba(124,58,237,0.5)'}}>
          Przejdź do panelu
        </Link>
      </section>
    </div>
  );
}

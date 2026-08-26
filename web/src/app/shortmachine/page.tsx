import Link from 'next/link';

export default function ShortMachinePagePL() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Hero */}
      <section className="relative px-6 py-24 text-center">
        <div className="absolute inset-0 bg-gradient-to-b from-gray-900 to-gray-950 z-0"></div>
        <div className="relative z-10 max-w-4xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-r from-violet-600 to-blue-600">
            Twoje shorty z YouTube. Bez renderowania. Za darmo.
          </h1>
          <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
            Wklej link YouTube. Za 60 sekund dostajesz pakiet SRT z zaznaczonymi momentami do cięcia w Premiere Pro lub DaVinci Resolve. AI wybiera haki, emocje i pointy za Ciebie.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Link href="/dashboard" className="px-8 py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-lg transition">
              Zacznij za darmo
            </Link>
            <Link href="/shortmachine/en" className="px-8 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition">
              Zobacz po angielsku
            </Link>
          </div>
        </div>
      </section>

      {/* Jak to działa */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Jak to działa</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">➡</div>
              <h3 className="text-xl font-bold mb-3">1. Wklej link YouTube</h3>
              <p className="text-gray-400">AI pobiera transkrypt i analizuje treść. Identyfikuje momenty z najwyższym potencjałem na viral hook, emocjonalną puentet i profesjonalne insight.</p>
            </div>
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">↓</div>
              <h3 className="text-xl font-bold mb-3">2. Pobierz pakiet SRT</h3>
              <p className="text-gray-400">3 pliki SRT gotowe w sekundę. Pełna transkrypcja, napisy w obszarach shortów i markery cięć dla Premiere.</p>
            </div>
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">✂</div>
              <h3 className="text-xl font-bold mb-3">3. Tnij w Premiere w 5 sekund</h3>
              <p className="text-gray-400">Przeciągnij shorts_markers.srt na ścieżkę Captions. Na osi czasu pojawiają się kolorowe bloki z tytułami shortów. Tnij żyletką bez szukania momentów.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Co dostajesz */}
      <section className="py-20 bg-gray-950">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Co dostajesz</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">pelny_film.srt</h3>
              <p className="text-gray-300">Pełna transkrypcja wideo z timestampami. Można wprost załadować jako YouTube Closed Captions.</p>
              <p className="text-xs text-violet-400 mt-3">→ Wgraj jako CC na YouTube — więcej wyświetlen od algorytmu</p>
            </div>
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">napisy_shortow.srt</h3>
              <p className="text-gray-300">Napisy tylko w obszarach wybranych przez AI. Do importu jako ścieżka napisów w Premiere lub DaVinci.</p>
              <p className="text-xs text-violet-400 mt-3">→ Import do Premiere: ścieżka Captions gotowa</p>
            </div>
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">shorts_markers.srt</h3>
              <p className="text-gray-300">Kluczowy plik: duże bloki [SHORT 1: Tytuł] na osi czasu. Drag & drop na Premiere = wizualne markery cięć natychmiast.</p>
              <p className="text-xs text-violet-400 mt-3">→ Drag & drop na timeline = kolorowe bloki cięć w 5 sekund</p>
            </div>
          </div>
        </div>
      </section>

      {/* Cennik */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Cennik</h2>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700 flex flex-col">
              <h3 className="text-2xl font-bold mb-2">FREE</h3>
              <div className="text-3xl font-extrabold mb-6">$0<span className="text-lg text-gray-500 font-normal">/mc</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• 3 filmy/miesiąc, unlimited shortów</li>
                <li>• Gotowe w 60 sekund</li>
                <li>• Bez karty kredytowej</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition">
                Wybierz
              </Link>
            </div>
            
            <div className="bg-gray-900 p-8 rounded-xl border-2 border-violet-500 ring-4 ring-violet-500/20 flex flex-col relative transform md:-translate-y-4">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-violet-500 text-white px-3 py-1 text-sm font-bold rounded-full">Polecany</div>
              <h3 className="text-2xl font-bold mb-2">ADVANCED</h3>
              <div className="text-3xl font-extrabold mb-6">$9<span className="text-lg text-gray-400 font-normal">/mc</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• Unlimited filmów/miesiąc</li>
                <li>• AI wybiera najlepsze momenty</li>
                <li>• Historia i zapis analiz</li>
                <li>• Integracja z kanałem YT</li>
                <li>• Priorytetowe wsparcie</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-violet-600 hover:bg-violet-700 rounded-lg font-semibold transition text-white">
                Kup PRO
              </Link>
            </div>
            
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700 flex flex-col">
              <h3 className="text-2xl font-bold mb-2">ENTERPRISE</h3>
              <div className="text-3xl font-extrabold mb-6">Skontaktuj się</div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• Wszystko z ADVANCED</li>
                <li>• Automatyczne renderowanie wideo</li>
                <li>• Local Runner (offline)</li>
                <li>• API access</li>
              </ul>
              <a href="mailto:kontakt@impresjapr.pl" className="block text-center py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition">
                Zapytaj o wycenę
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-20 bg-gray-950">
        <div className="max-w-3xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">FAQ</h2>
          <div className="space-y-6">
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">Czy muszę instalować cokolwiek?</h4>
              <p className="text-gray-400">Nie. ShortMachine działa w 100% w przeglądarce. Potrzebujesz tylko Premiere Pro lub DaVinci Resolve do montażu.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">Jak AI wybiera momenty do shortów?</h4>
              <p className="text-gray-400">Nasz model analizuje transkrypt pod kątem trzech typów: Emotional (silne emocje, kontrowersja), Professional (ekspertyza, insight) i Custom (Twój własny query). Każdy kandydat dostaje ocenę Hook-Body-Punchline.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">Czy mogę użyć z dowolnym wideo YouTube?</h4>
              <p className="text-gray-400">Tak, o ile wideo ma dostępne napisy (CC). Większość publicznych wideo je ma.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">Co daje SRT PRO vs FREE?</h4>
              <p className="text-gray-400">FREE: 3 shorty na film. PRO: nielimitowane shorty, historia wideo, integracja z kanałem YouTube (automatyczne tytuły i opisy po publikacji).</p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="py-24 bg-gradient-to-b from-gray-900 to-gray-950 text-center px-6">
        <h2 className="text-4xl font-bold mb-8">Gotowy przyspieszyć montaż?</h2>
        <Link href="/dashboard" className="inline-block px-10 py-4 bg-violet-600 hover:bg-violet-700 text-white font-bold rounded-xl text-lg shadow-lg shadow-violet-600/20 transition">
          Przejdź do panelu
        </Link>
      </section>
    </div>
  );
}

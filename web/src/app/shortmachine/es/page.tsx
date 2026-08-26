'use client'
import Link from 'next/link';

export default function ShortMachinePageES() {
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
          <span className="text-white">Tus </span>
          <span style={{background:'linear-gradient(90deg,#a855f7,#06b6d4)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>YouTube Shorts.</span>
          <br/>
          <span className="text-white">Sin renderizar. </span>
          <span style={{background:'linear-gradient(90deg,#06b6d4,#a855f7)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>Gratis.</span>
        </h1>

        <p className="text-xl text-gray-300 max-w-2xl mx-auto mb-10 leading-relaxed">
          Pega el link de YouTube. En 60 segundos recibes un paquete SRT con los momentos marcados para cortar en Premiere Pro o DaVinci Resolve. La IA elige los ganchos, emociones y remates por ti.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12">
          <Link href="/dashboard" className="px-8 py-4 rounded-xl font-bold text-lg text-white transition-all hover:scale-105" style={{background:'linear-gradient(135deg,#7c3aed,#06b6d4)',boxShadow:'0 0 30px rgba(124,58,237,0.5)'}}>Empieza gratis →</Link>
          <a href="#jak-dziala" className="px-8 py-4 rounded-xl font-bold text-lg text-gray-300 border border-gray-600 hover:border-purple-500 transition-all">Cómo funciona</a>
        </div>

        <div className="flex gap-8 justify-center text-center">
          <div><div className="text-2xl font-bold text-white">60s</div><div className="text-xs text-gray-400">tiempo de generación</div></div>
          <div className="w-px bg-gray-700" />
          <div><div className="text-2xl font-bold text-white">4</div><div className="text-xs text-gray-400">archivos en paquete</div></div>
          <div className="w-px bg-gray-700" />
          <div><div className="text-2xl font-bold text-white">$0</div><div className="text-xs text-gray-400">para empezar</div></div>
        </div>
      </section>

      <section id="jak-dziala" className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="text-3xl font-bold mb-12">Cómo funciona</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">🔗</span>
              <h3 className="text-xl font-bold mb-3 text-center">1. Pega el link de YouTube</h3>
              <p className="text-gray-400 text-center">La IA descarga la transcripción y analiza el contenido. Identifica momentos con mayor potencial viral: gancho emocional, punto de giro profesional y remate memorable.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">📦</span>
              <h3 className="text-xl font-bold mb-3 text-center">2. Descarga el paquete SRT</h3>
              <p className="text-gray-400 text-center">4 archivos listos en segundos. Transcripción completa, subtítulos en áreas de shorts y marcadores de corte para Premiere.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">✂️</span>
              <h3 className="text-xl font-bold mb-3 text-center">3. Corta en Premiere en 5 segundos</h3>
              <p className="text-gray-400 text-center">Arrastra shorts_markers.srt a la pista de Captions. Aparecen bloques de colores con títulos de shorts en tu timeline. Corta con la cuchilla sin buscar momentos.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-3xl font-bold mb-12">Lo que obtienes</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">🎞️</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">pelny_film.srt</h3>
              <p className="text-gray-300 mb-2 text-center">Transcripción completa del vídeo con marcas de tiempo. Cárgala directamente como Closed Captions en YouTube.</p>
              <p className="text-sm text-violet-300 font-medium text-center">→ Súbela como CC en YouTube — más alcance del algoritmo</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">💬</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">napisy_shortow.srt</h3>
              <p className="text-gray-300 mb-2 text-center">Subtítulos solo en las áreas seleccionadas por la IA. Para importar como pista de subtítulos en Premiere o DaVinci.</p>
              <p className="text-sm text-violet-300 font-medium text-center">→ Import a Premiere: pista de Captions lista</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">🎯</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">shorts_markers.srt</h3>
              <p className="text-gray-300 mb-2 text-center">El archivo clave: grandes bloques [SHORT 1: Título] en el timeline. Drag & drop en Premiere = marcadores visuales de corte inmediatos.</p>
              <p className="text-sm text-violet-300 font-medium text-center">→ Drag & drop en timeline = bloques de color en 5 segundos</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">📑</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">chapters.txt</h3>
              <p className="text-gray-300 text-center">Bloque de capítulos de YouTube listo para pegar en la descripción. YouTube crea capítulos clicables en la barra del reproductor.</p>
              <p className="text-xs text-violet-400 mt-3 text-center">→ Toca el capítulo en el móvil → Remix → Edit into Short</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-3xl font-bold mb-12">Precios</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col">
              <h3 className="text-2xl font-bold mb-2">🆓 FREE</h3>
              <div className="text-3xl font-extrabold mb-6">$0<span className="text-lg text-gray-500 font-normal">/mes</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ 2 vídeos / mes</li>
                <li>✅ Shorts ilimitados por vídeo</li>
                <li>✅ Listo en 60 segundos</li>
                <li>✅ Sin tarjeta de crédito</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-white/10 hover:bg-white/20 rounded-lg font-semibold transition border border-white/20">
                Elegir
              </Link>
            </div>
            
            <div className="bg-white/10 backdrop-blur-sm border-2 border-purple-500 rounded-2xl p-8 flex flex-col relative transform md:-translate-y-4" style={{boxShadow: '0 0 40px rgba(124,58,237,0.3)'}}>
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-purple-500 to-cyan-500 text-white px-4 py-1 text-sm font-bold rounded-full shadow-lg">Recomendado</div>
              <h3 className="text-2xl font-bold mb-2">⚡ ADVANCED</h3>
              <div className="text-3xl font-extrabold mb-6" style={{background:'linear-gradient(90deg,#a855f7,#06b6d4)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>$9<span className="text-lg text-gray-400 font-normal">/mes</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ 10 vídeos / mes</li>
                <li>✅ Shorts ilimitados por vídeo</li>
                <li>✅ Vídeos de hasta 45 minutos</li>
                <li>✅ Historial y análisis guardados</li>
                <li>✅ Integración con canal de YouTube</li>
                <li>✅ Soporte prioritario</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-gradient-to-r from-violet-600 to-cyan-500 hover:from-violet-500 hover:to-cyan-400 rounded-lg font-semibold transition text-white shadow-lg">
                Obtener ADVANCED
              </Link>
            </div>
            
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col opacity-80">
              <h3 className="text-2xl font-bold mb-2">🏢 ENTERPRISE</h3>
              <div className="text-3xl font-extrabold mb-6">Contáctanos</div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ Todo lo de ADVANCED</li>
                <li>✅ Vídeos ilimitados / mes</li>
                <li>✅ Vídeos de más de 45 minutos</li>
                <li>✅ Acceso a API</li>
                <li>✅ Renderizado automático</li>
                <li>✅ Soporte dedicado</li>
              </ul>
              <a href="mailto:kontakt@impresjapr.pl" className="block text-center py-3 bg-white/10 hover:bg-white/20 rounded-lg font-semibold transition text-white border border-white/20">
                Pedir presupuesto
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
              <h4 className="font-bold text-lg mb-2">¿Necesito instalar algo?</h4>
              <p className="text-gray-400">No. ShortMachine funciona 100% en el navegador. Solo necesitas Premiere Pro o DaVinci Resolve para editar.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">¿Cómo elige la IA los momentos?</h4>
              <p className="text-gray-400">Nuestro modelo analiza la transcripción en busca de tres tipos: Emocional (emociones fuertes, controversia), Profesional (experiencia, insight) y Personalizado (tu propia búsqueda). Cada candidato recibe una puntuación Gancho-Cuerpo-Remate.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">¿Funciona con cualquier vídeo de YouTube?</h4>
              <p className="text-gray-400">Sí, siempre que el vídeo tenga subtítulos disponibles (CC). La mayoría de los vídeos públicos los tienen.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">¿Qué ventajas tiene ADVANCED sobre FREE?</h4>
              <p className="text-gray-400">FREE: 3 vídeos al mes. ADVANCED: vídeos ilimitados, historial, integración con canal de YouTube (títulos y descripciones automáticos tras la publicación).</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 relative z-10 text-center px-6">
        <h2 className="text-4xl font-bold mb-8">¿Listo para acelerar el montaje?</h2>
        <Link href="/dashboard" className="inline-block px-10 py-4 font-bold rounded-xl text-lg text-white transition-all hover:scale-105" style={{background:'linear-gradient(135deg,#7c3aed,#06b6d4)',boxShadow:'0 0 30px rgba(124,58,237,0.5)'}}>
          Ir al panel
        </Link>
      </section>
    </div>
  );
}

import Link from 'next/link';

export default function ShortMachinePageES() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Hero */}
      <section className="relative px-6 py-24 text-center">
        <div className="absolute inset-0 bg-gradient-to-b from-gray-900 to-gray-950 z-0"></div>
        <div className="relative z-10 max-w-4xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-r from-violet-600 to-blue-600">
            Tus YouTube Shorts. Sin renderizar. Gratis.
          </h1>
          <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
            Pega el link de YouTube. En 60 segundos recibes un paquete SRT con los momentos marcados para cortar en Premiere Pro o DaVinci Resolve. La IA elige los ganchos, emociones y remates por ti.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Link href="/dashboard" className="px-8 py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-lg transition">
              Empieza gratis →
            </Link>
            <Link href="/shortmachine" className="px-8 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition">
              Ver en polaco
            </Link>
            <Link href="/shortmachine/en" className="px-8 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition">
              See in English
            </Link>
          </div>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Cómo funciona</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">➡</div>
              <h3 className="text-xl font-bold mb-3">1. Pega el link de YouTube</h3>
              <p className="text-gray-400">La IA descarga la transcripción y analiza el contenido. Identifica momentos con mayor potencial viral: gancho emocional, punto de giro profesional y remate memorable.</p>
            </div>
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">↓</div>
              <h3 className="text-xl font-bold mb-3">2. Descarga el paquete SRT</h3>
              <p className="text-gray-400">3 archivos SRT listos en segundos. Transcripción completa, subtítulos en áreas de shorts y marcadores de corte para Premiere.</p>
            </div>
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">✂</div>
              <h3 className="text-xl font-bold mb-3">3. Corta en Premiere en 5 segundos</h3>
              <p className="text-gray-400">Arrastra shorts_markers.srt a la pista de Captions. Aparecen bloques de colores con títulos de shorts en tu timeline. Corta con la cuchilla sin buscar momentos.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Lo que obtienes */}
      <section className="py-20 bg-gray-950">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Lo que obtienes</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">pelny_film.srt</h3>
              <p className="text-gray-300 mb-2">Transcripción completa del vídeo con marcas de tiempo. Cárgala directamente como Closed Captions en YouTube.</p>
              <p className="text-sm text-violet-300 font-medium">→ Súbela como CC en YouTube — más alcance del algoritmo</p>
            </div>
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">napisy_shortow.srt</h3>
              <p className="text-gray-300 mb-2">Subtítulos solo en las áreas seleccionadas por la IA. Para importar como pista de subtítulos en Premiere o DaVinci.</p>
              <p className="text-sm text-violet-300 font-medium">→ Import a Premiere: pista de Captions lista</p>
            </div>
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">shorts_markers.srt</h3>
              <p className="text-gray-300 mb-2">El archivo clave: grandes bloques [SHORT 1: Título] en el timeline. Drag & drop en Premiere = marcadores visuales de corte inmediatos.</p>
              <p className="text-sm text-violet-300 font-medium">→ Drag & drop en timeline = bloques de color en 5 segundos</p>
            </div>
          </div>
        </div>
      </section>

      {/* Precios */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Precios</h2>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700 flex flex-col">
              <h3 className="text-2xl font-bold mb-2">FREE</h3>
              <div className="text-3xl font-extrabold mb-6">$0<span className="text-lg text-gray-500 font-normal">/mes</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• 2 vídeos / mes</li>
                <li>• Shorts ilimitados por vídeo</li>
                <li>• Listo en 60 segundos</li>
                <li>• Sin tarjeta de crédito</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition">
                Elegir
              </Link>
            </div>
            
            <div className="bg-gray-900 p-8 rounded-xl border-2 border-violet-500 ring-4 ring-violet-500/20 flex flex-col relative transform md:-translate-y-4">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-violet-500 text-white px-3 py-1 text-sm font-bold rounded-full">Recomendado</div>
              <h3 className="text-2xl font-bold mb-2">ADVANCED</h3>
              <div className="text-3xl font-extrabold mb-6">$9<span className="text-lg text-gray-400 font-normal">/mes</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• 10 vídeos / mes</li>
                <li>• Shorts ilimitados por vídeo</li>
                <li>• Vídeos de hasta 45 minutos</li>
                <li>• Historial y análisis guardados</li>
                <li>• Integración con canal de YouTube</li>
                <li>• Soporte prioritario</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-violet-600 hover:bg-violet-700 rounded-lg font-semibold transition text-white">
                Obtener ADVANCED
              </Link>
            </div>
            
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700 flex flex-col opacity-75">
              <h3 className="text-2xl font-bold mb-2">ENTERPRISE</h3>
              <div className="text-3xl font-extrabold mb-6">Contáctanos</div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• Todo lo de ADVANCED</li>
                <li>• Vídeos ilimitados / mes</li>
                <li>• Vídeos de más de 45 minutos</li>
                <li>• Acceso a API</li>
                <li>• Renderizado automático</li>
                <li>• Soporte dedicado</li>
              </ul>
              <a href="mailto:kontakt@impresjapr.pl" className="block text-center py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition text-white">
                Pedir presupuesto
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
              <h4 className="font-bold text-lg mb-2">¿Necesito instalar algo?</h4>
              <p className="text-gray-400">No. ShortMachine funciona 100% en el navegador. Solo necesitas Premiere Pro o DaVinci Resolve para editar.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">¿Cómo elige la IA los momentos?</h4>
              <p className="text-gray-400">Nuestro modelo analiza la transcripción en busca de tres tipos: Emocional (emociones fuertes, controversia), Profesional (experiencia, insight) y Personalizado (tu propia búsqueda). Cada candidato recibe una puntuación Gancho-Cuerpo-Remate.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">¿Funciona con cualquier vídeo de YouTube?</h4>
              <p className="text-gray-400">Sí, siempre que el vídeo tenga subtítulos disponibles (CC). La mayoría de los vídeos públicos los tienen.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">¿Qué ventajas tiene ADVANCED sobre FREE?</h4>
              <p className="text-gray-400">FREE: 3 vídeos al mes. ADVANCED: vídeos ilimitados, historial, integración con canal de YouTube (títulos y descripciones automáticos tras la publicación).</p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="py-24 bg-gradient-to-b from-gray-900 to-gray-950 text-center px-6">
        <h2 className="text-4xl font-bold mb-8">¿Listo para acelerar el montaje?</h2>
        <Link href="/dashboard" className="inline-block px-10 py-4 bg-violet-600 hover:bg-violet-700 text-white font-bold rounded-xl text-lg shadow-lg shadow-violet-600/20 transition">
          Ir al panel
        </Link>
      </section>
    </div>
  );
}

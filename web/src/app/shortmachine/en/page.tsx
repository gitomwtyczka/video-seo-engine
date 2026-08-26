import Link from 'next/link';

export default function ShortMachinePageEN() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Hero */}
      <section className="relative px-6 py-24 text-center">
        <div className="absolute inset-0 bg-gradient-to-b from-gray-900 to-gray-950 z-0"></div>
        <div className="relative z-10 max-w-4xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-r from-violet-600 to-blue-600">
            YouTube Shorts. No rendering. Free.
          </h1>
          <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
            ShortMachine uses AI to analyze your video transcript, identify the highest-potential moments, and generates an SRT package ready for Premiere Pro or DaVinci Resolve. Zero server-side rendering costs.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Link href="/dashboard" className="px-8 py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-lg transition">
              Start for free →
            </Link>
            <Link href="/shortmachine" className="px-8 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition">
              View in Polish
            </Link>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">How it works</h2>
          <div className="grid md:grid-cols-4 gap-8">
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">➡</div>
              <h3 className="text-xl font-bold mb-3">1. Paste YouTube link</h3>
              <p className="text-gray-400">AI downloads the transcript and analyzes the content. It identifies moments with the highest viral hook potential, emotional punchline, and professional insight.</p>
            </div>
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">↓</div>
              <h3 className="text-xl font-bold mb-3">2. Download SRT package</h3>
              <p className="text-gray-400">4 files ready in seconds. Full transcript, subtitles in short areas, and cut markers for Premiere.</p>
            </div>
            <div className="bg-gray-800 p-8 rounded-xl">
              <div className="text-4xl mb-4">✂</div>
              <h3 className="text-xl font-bold mb-3">3. Cut in Premiere in 5 seconds</h3>
              <p className="text-gray-400">Drag shorts_markers.srt to the Captions track. Colored blocks with short titles appear on your timeline. Cut with the razor tool — no more hunting for moments.</p>
            </div>
          </div>
        </div>
      </section>

      {/* What you get */}
      <section className="py-20 bg-gray-950">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">What you get</h2>
          <div className="grid md:grid-cols-4 gap-8">
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">pelny_film.srt</h3>
              <p className="text-gray-300">Full video transcript with timestamps. Load directly as YouTube Closed Captions.</p>
            </div>
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">napisy_shortow.srt</h3>
              <p className="text-gray-300">Subtitles only in AI-selected areas. Import as a caption track in Premiere or DaVinci.</p>
            </div>
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">shorts_markers.srt</h3>
              <p className="text-gray-300">The key file: large [SHORT 1: Title] blocks on the timeline. Drag & drop to Premiere = instant visual cut markers.</p>
            </div>
            <div className="border border-gray-800 p-8 rounded-xl bg-gray-900/50">
              <h3 className="text-lg font-mono text-violet-400 mb-2">chapters.txt</h3>
              <p className="text-gray-300">Ready-to-paste YouTube Chapters block for your video description. YouTube creates clickable chapters on the scrubber bar.</p>
              <p className="text-xs text-violet-400 mt-3">→ Tap chapter on mobile → Remix → Edit into Short</p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Pricing</h2>
          <div className="grid md:grid-cols-4 gap-8 max-w-5xl mx-auto">
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700 flex flex-col">
              <h3 className="text-2xl font-bold mb-2">FREE</h3>
              <div className="text-3xl font-extrabold mb-6">$0<span className="text-lg text-gray-500 font-normal">/mo</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• 2 videos / month</li>
                <li>• Unlimited shorts per video</li>
                <li>• Ready in 60 seconds</li>
                <li>• No credit card required</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition">
                Select
              </Link>
            </div>
            
            <div className="bg-gray-900 p-8 rounded-xl border-2 border-violet-500 ring-4 ring-violet-500/20 flex flex-col relative transform md:-translate-y-4">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-violet-500 text-white px-3 py-1 text-sm font-bold rounded-full">Recommended</div>
              <h3 className="text-2xl font-bold mb-2">ADVANCED</h3>
              <div className="text-3xl font-extrabold mb-6">$9<span className="text-lg text-gray-400 font-normal">/mo</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• 10 videos / month</li>
                <li>• Unlimited shorts per video</li>
                <li>• Videos up to 45 minutes</li>
                <li>• History and saved analyses</li>
                <li>• YouTube channel integration</li>
                <li>• Priority support</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-violet-600 hover:bg-violet-700 rounded-lg font-semibold transition text-white">
                Get ADVANCED
              </Link>
            </div>
            
            <div className="bg-gray-800 p-8 rounded-xl border border-gray-700 flex flex-col opacity-75">
              <h3 className="text-2xl font-bold mb-2">ENTERPRISE</h3>
              <div className="text-3xl font-extrabold mb-6">Contact us</div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3">
                <li>• Everything in ADVANCED</li>
                <li>• Unlimited videos / month</li>
                <li>• Videos over 45 minutes</li>
                <li>• API access</li>
                <li>• Automatic video rendering</li>
                <li>• Dedicated support</li>
              </ul>
              <a href="mailto:kontakt@impresjapr.pl" className="block text-center py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold transition">
                Request a quote
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
              <h4 className="font-bold text-lg mb-2">Do I need to install anything?</h4>
              <p className="text-gray-400">No. ShortMachine runs 100% in the browser. You only need Premiere Pro or DaVinci Resolve for editing.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">How does AI pick the moments?</h4>
              <p className="text-gray-400">Our model analyzes the transcript for three types: Emotional (strong emotion, controversy), Professional (expertise, insight) and Custom (your own query). Each candidate gets a Hook-Body-Punchline score.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">Does it work with any YouTube video?</h4>
              <p className="text-gray-400">Yes, as long as the video has available subtitles (CC). Most public videos do.</p>
            </div>
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
              <h4 className="font-bold text-lg mb-2">What does SRT PRO add over FREE?</h4>
              <p className="text-gray-400">FREE: 3 shorts per video. PRO: unlimited shorts, video history, YouTube channel integration (auto titles and descriptions after publishing).</p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="py-24 bg-gradient-to-b from-gray-900 to-gray-950 text-center px-6">
        <h2 className="text-4xl font-bold mb-8">Ready to speed up your editing?</h2>
        <Link href="/dashboard" className="inline-block px-10 py-4 bg-violet-600 hover:bg-violet-700 text-white font-bold rounded-xl text-lg shadow-lg shadow-violet-600/20 transition">
          Start for free →
        </Link>
      </section>
    </div>
  );
}

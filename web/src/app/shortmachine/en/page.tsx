'use client'
import Link from 'next/link';

export default function ShortMachinePageEN() {
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
          <span className="text-white">Your </span>
          <span style={{background:'linear-gradient(90deg,#a855f7,#06b6d4)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>YouTube Shorts.</span>
          <br/>
          <span className="text-white">No rendering. </span>
          <span style={{background:'linear-gradient(90deg,#06b6d4,#a855f7)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>Free.</span>
        </h1>

        <p className="text-xl text-gray-300 max-w-2xl mx-auto mb-10 leading-relaxed">
          ShortMachine uses AI to analyze your video transcript, identify the highest-potential moments, and generates an SRT package ready for Premiere Pro or DaVinci Resolve. Zero server-side rendering costs.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12">
          <Link href="/dashboard" className="px-8 py-4 rounded-xl font-bold text-lg text-white transition-all hover:scale-105" style={{background:'linear-gradient(135deg,#7c3aed,#06b6d4)',boxShadow:'0 0 30px rgba(124,58,237,0.5)'}}>Start for free →</Link>
          <a href="#jak-dziala" className="px-8 py-4 rounded-xl font-bold text-lg text-gray-300 border border-gray-600 hover:border-purple-500 transition-all">See how it works</a>
        </div>

        <div className="flex gap-8 justify-center text-center">
          <div><div className="text-2xl font-bold text-white">60s</div><div className="text-xs text-gray-400">generation time</div></div>
          <div className="w-px bg-gray-700" />
          <div><div className="text-2xl font-bold text-white">4</div><div className="text-xs text-gray-400">files in package</div></div>
          <div className="w-px bg-gray-700" />
          <div><div className="text-2xl font-bold text-white">$0</div><div className="text-xs text-gray-400">to start</div></div>
        </div>
      </section>

      <section id="jak-dziala" className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="text-3xl font-bold mb-12">How it works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">🔗</span>
              <h3 className="text-xl font-bold mb-3 text-center">1. Paste YouTube link</h3>
              <p className="text-gray-400 text-center">AI downloads the transcript and analyzes the content. It identifies moments with the highest viral hook potential, emotional punchline, and professional insight.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">📦</span>
              <h3 className="text-xl font-bold mb-3 text-center">2. Download SRT package</h3>
              <p className="text-gray-400 text-center">4 files ready in seconds. Full transcript, subtitles in short areas, and cut markers for Premiere.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
              <div className="h-1 rounded-full mb-6" style={{background:'linear-gradient(90deg,#7c3aed,#06b6d4)'}} />
              <span className="text-5xl mb-4 block text-center">✂️</span>
              <h3 className="text-xl font-bold mb-3 text-center">3. Cut in Premiere in 5 seconds</h3>
              <p className="text-gray-400 text-center">Drag shorts_markers.srt to the Captions track. Colored blocks with short titles appear on your timeline. Cut with the razor tool — no more hunting for moments.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-3xl font-bold mb-12">What you get</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">🎞️</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">pelny_film.srt</h3>
              <p className="text-gray-300 text-center">Full video transcript with timestamps. Load directly as YouTube Closed Captions.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">💬</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">napisy_shortow.srt</h3>
              <p className="text-gray-300 text-center">Subtitles only in AI-selected areas. Import as a caption track in Premiere or DaVinci.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">🎯</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">shorts_markers.srt</h3>
              <p className="text-gray-300 text-center">The key file: large [SHORT 1: Title] blocks on the timeline. Drag & drop to Premiere = instant visual cut markers.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 hover:shadow-[0_0_20px_rgba(124,58,237,0.2)] transition-shadow">
              <span className="text-4xl mb-4 block text-center">📑</span>
              <h3 className="text-lg font-mono text-violet-400 mb-2 text-center">chapters.txt</h3>
              <p className="text-gray-300 text-center">Ready-to-paste YouTube Chapters block for your video description. YouTube creates clickable chapters on the scrubber bar.</p>
              <p className="text-xs text-violet-400 mt-3 text-center">→ Tap chapter on mobile → Remix → Edit into Short</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 relative z-10 text-center">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-3xl font-bold mb-12">Pricing</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col">
              <h3 className="text-2xl font-bold mb-2">🆓 FREE</h3>
              <div className="text-3xl font-extrabold mb-6">$0<span className="text-lg text-gray-500 font-normal">/mo</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ 2 videos / month</li>
                <li>✅ Unlimited shorts per video</li>
                <li>✅ Ready in 60 seconds</li>
                <li>✅ No credit card required</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-white/10 hover:bg-white/20 rounded-lg font-semibold transition border border-white/20">
                Select
              </Link>
            </div>
            
            <div className="bg-white/10 backdrop-blur-sm border-2 border-purple-500 rounded-2xl p-8 flex flex-col relative transform md:-translate-y-4" style={{boxShadow: '0 0 40px rgba(124,58,237,0.3)'}}>
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-purple-500 to-cyan-500 text-white px-4 py-1 text-sm font-bold rounded-full shadow-lg">Recommended</div>
              <h3 className="text-2xl font-bold mb-2">⚡ ADVANCED</h3>
              <div className="text-3xl font-extrabold mb-6" style={{background:'linear-gradient(90deg,#a855f7,#06b6d4)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>$9<span className="text-lg text-gray-400 font-normal">/mo</span></div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ 10 videos / month</li>
                <li>✅ Unlimited shorts per video</li>
                <li>✅ Videos up to 45 minutes</li>
                <li>✅ History and saved analyses</li>
                <li>✅ YouTube channel integration</li>
                <li>✅ Priority support</li>
              </ul>
              <Link href="/dashboard" className="block text-center py-3 bg-gradient-to-r from-violet-600 to-cyan-500 hover:from-violet-500 hover:to-cyan-400 rounded-lg font-semibold transition text-white shadow-lg">
                Get ADVANCED
              </Link>
            </div>
            
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 flex flex-col opacity-80">
              <h3 className="text-2xl font-bold mb-2">🏢 ENTERPRISE</h3>
              <div className="text-3xl font-extrabold mb-6">Contact us</div>
              <ul className="text-gray-300 mb-8 flex-grow space-y-3 text-left">
                <li>✅ Everything in ADVANCED</li>
                <li>✅ Unlimited videos / month</li>
                <li>✅ Videos over 45 minutes</li>
                <li>✅ API access</li>
                <li>✅ Automatic video rendering</li>
                <li>✅ Dedicated support</li>
              </ul>
              <a href="mailto:kontakt@impresjapr.pl" className="block text-center py-3 bg-white/10 hover:bg-white/20 rounded-lg font-semibold transition border border-white/20">
                Request a quote
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
              <h4 className="font-bold text-lg mb-2">Do I need to install anything?</h4>
              <p className="text-gray-400">No. ShortMachine runs 100% in the browser. You only need Premiere Pro or DaVinci Resolve for editing.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">How does AI pick the moments?</h4>
              <p className="text-gray-400">Our model analyzes the transcript for three types: Emotional (strong emotion, controversy), Professional (expertise, insight) and Custom (your own query). Each candidate gets a Hook-Body-Punchline score.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">Does it work with any YouTube video?</h4>
              <p className="text-gray-400">Yes, as long as the video has available subtitles (CC). Most public videos do.</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-left">
              <h4 className="font-bold text-lg mb-2">What does SRT PRO add over FREE?</h4>
              <p className="text-gray-400">FREE: 3 shorts per video. PRO: unlimited shorts, video history, YouTube channel integration (auto titles and descriptions after publishing).</p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 relative z-10 text-center px-6">
        <h2 className="text-4xl font-bold mb-8">Ready to speed up your editing?</h2>
        <Link href="/dashboard" className="inline-block px-10 py-4 font-bold rounded-xl text-lg text-white transition-all hover:scale-105" style={{background:'linear-gradient(135deg,#7c3aed,#06b6d4)',boxShadow:'0 0 30px rgba(124,58,237,0.5)'}}>
          Start for free →
        </Link>
      </section>
    </div>
  );
}

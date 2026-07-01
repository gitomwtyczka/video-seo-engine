export default function PolitykaPrywatnosciPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 py-20 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <span className="inline-block px-4 py-1 rounded-full text-xs font-semibold bg-violet-900/40 text-violet-300 border border-violet-700/40 mb-4 uppercase tracking-widest">
            Dokument prawny
          </span>
          <h1 className="text-3xl md:text-4xl font-extrabold text-white mb-3">
            Polityka Prywatności
          </h1>
          <p className="text-gray-400 text-sm">
            Video SEO Engine &mdash; zgodna z RODO (art. 13) &mdash; obowiązuje od 1 lipca 2026 r.
          </p>
        </div>

        <div className="glass rounded-2xl p-8 md:p-12 space-y-8 text-gray-300 leading-relaxed">

          {/* 1. Administrator */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">1. Administrator danych osobowych</h2>
            <p className="text-sm">
              Administratorem Państwa danych osobowych jest:
            </p>
            <div className="mt-3 p-4 bg-white/5 rounded-xl text-sm space-y-1 border border-white/10">
              <p className="text-white font-semibold">IMPRESJA PR SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ</p>
              <p>al. Jana Pawła II 27, 00-867 Warszawa</p>
              <p>KRS: 0000981410 &bull; NIP: 5273010810 &bull; REGON: 522593390</p>
              <p>Prezes Zarządu: Tomasz Brzozowski</p>
              <p>E-mail: <a href="mailto:spolka@impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">spolka@impresjapr.pl</a></p>
            </div>
          </section>

          {/* 2. Kontakt */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">2. Kontakt w sprawach ochrony danych</h2>
            <p className="text-sm">
              We wszelkich sprawach dotyczących przetwarzania danych osobowych prosimy o kontakt pod adresem e-mail: <a href="mailto:spolka@impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">spolka@impresjapr.pl</a>.
            </p>
          </section>

          {/* 3. Cele i podstawy */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">3. Cele i podstawy prawne przetwarzania danych</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left py-2 pr-4 text-white font-semibold">Cel</th>
                    <th className="text-left py-2 text-white font-semibold">Podstawa prawna (RODO)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  <tr>
                    <td className="py-2.5 pr-4">Realizacja usług VSE (rejestracja konta, generowanie SEO, publikacja WordPress)</td>
                    <td className="py-2.5">Art. 6 ust. 1 lit. b &mdash; wykonanie umowy</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4">Rozliczenia i obsługa płatności przez Stripe</td>
                    <td className="py-2.5">Art. 6 ust. 1 lit. b &mdash; wykonanie umowy</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4">Weryfikacja adresu e-mail</td>
                    <td className="py-2.5">Art. 6 ust. 1 lit. b &mdash; wykonanie umowy</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4">Komunikacja z użytkownikiem (wsparcie techniczne, informacje systemowe)</td>
                    <td className="py-2.5">Art. 6 ust. 1 lit. f &mdash; uzasadniony interes administratora</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4">Wypełnianie obowiązków podatkowych i rachunkowych</td>
                    <td className="py-2.5">Art. 6 ust. 1 lit. c &mdash; obowiązek prawny</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* 4. Kategorie danych */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">4. Kategorie przetwarzanych danych</h2>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li><span className="text-white font-medium">Dane identyfikacyjne:</span> adres e-mail, imię i nazwisko (opcjonalnie).</li>
              <li><span className="text-white font-medium">Dane płatnicze:</span> informacje o subskrypcji i historii transakcji przetwarzane przez Stripe Inc. Administrator nie przechowuje numerów kart płatniczych.</li>
              <li><span className="text-white font-medium">Dane użytkowania:</span> logi aktywności, historia generowania SEO, daty logowania.</li>
              <li><span className="text-white font-medium">Adresy URL YouTube:</span> adresy URL filmów przekazywane przez Użytkownika w celu generowania treści SEO. Adresy te są przesyłane do API Anthropic (AI) wyłącznie w celu realizacji usługi &mdash; szczegóły w sekcji 5.</li>
              <li><span className="text-white font-medium">Dane sesji:</span> tokeny sesji NextAuth niezbędne do uwierzytelnienia.</li>
            </ul>
          </section>

          {/* 5. Odbiorcy */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">5. Odbiorcy danych i transfery do krajów trzecich</h2>
            <p className="text-sm mb-4">
              Dane mogą być przekazywane następującym kategoriom podmiotów. Transfery do USA odbywają się na podstawie Standardowych Klauzul Umownych (SCCs) zatwierdzonych przez Komisję Europejską.
            </p>
            <div className="space-y-3">
              <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-sm">
                <p className="text-white font-semibold mb-1">Stripe Inc. &mdash; USA (SCCs)</p>
                <p>Operator płatności. Przetwarza dane niezbędne do realizacji transakcji i zarządzania subskrypcją. <a href="https://stripe.com/privacy" className="text-violet-400 hover:text-violet-300 underline" target="_blank" rel="noopener noreferrer">Polityka prywatności Stripe</a></p>
              </div>
              <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-sm">
                <p className="text-white font-semibold mb-1">Anthropic PBC &mdash; USA (SCCs)</p>
                <p>Dostawca modeli AI (Claude API). <span className="text-amber-300">Adresy URL filmów YouTube podane przez Użytkownika są przesyłane do API Anthropic w celu generowania treści SEO</span> (schema, rozdziały, FAQ). Anthropic nie jest uprawniony do wykorzystywania tych danych do trenowania modeli. <a href="https://www.anthropic.com/privacy" className="text-violet-400 hover:text-violet-300 underline" target="_blank" rel="noopener noreferrer">Polityka prywatności Anthropic</a></p>
              </div>
              <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-sm">
                <p className="text-white font-semibold mb-1">Google LLC &mdash; USA (SCCs)</p>
                <p>Dostawca usługi OAuth (Google Sign-In) oraz dostawca czcionek (Google Fonts). Przetwarza dane logowania w przypadku wyboru uwierzytelniania Google. <a href="https://policies.google.com/privacy" className="text-violet-400 hover:text-violet-300 underline" target="_blank" rel="noopener noreferrer">Polityka prywatności Google</a></p>
              </div>
              <div className="p-4 bg-white/5 rounded-xl border border-white/10 text-sm">
                <p className="text-white font-semibold mb-1">Oracle Corporation &mdash; USA (SCCs)</p>
                <p>Dostawca infrastruktury serwerowej (Oracle Cloud Infrastructure). Serwery zlokalizowane w UE. Dane przechowywane są na serwerze w Polsce/UE. <a href="https://www.oracle.com/legal/privacy/" className="text-violet-400 hover:text-violet-300 underline" target="_blank" rel="noopener noreferrer">Polityka prywatności Oracle</a></p>
              </div>
            </div>
          </section>

          {/* 6. Okres przechowywania */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">6. Okres przechowywania danych</h2>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Dane Konta &mdash; przez czas trwania umowy (aktywne Konto) oraz 30 dni po jej rozwiązaniu.</li>
              <li>Dane rozliczeniowe (faktury, transakcje) &mdash; przez 5 lat od końca roku rozliczeniowego (obowiązki podatkowe wynikające z polskiego prawa).</li>
              <li>Logi systemowe &mdash; maksymalnie 90 dni.</li>
            </ul>
          </section>

          {/* 7. Prawa */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">7. Prawa osoby, której dane dotyczą</h2>
            <p className="text-sm mb-3">Przysługują Państwu następujące prawa na podstawie RODO:</p>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li><span className="text-white font-medium">Prawo dostępu</span> (art. 15 RODO) &mdash; prawo do uzyskania informacji o przetwarzanych danych.</li>
              <li><span className="text-white font-medium">Prawo do sprostowania</span> (art. 16 RODO) &mdash; prawo do poprawiania błędnych lub uzupełniania niekompletnych danych.</li>
              <li><span className="text-white font-medium">Prawo do usunięcia</span> (&bdquo;prawo do bycia zapomnianym&rdquo;, art. 17 RODO).</li>
              <li><span className="text-white font-medium">Prawo do ograniczenia przetwarzania</span> (art. 18 RODO).</li>
              <li><span className="text-white font-medium">Prawo do przenoszenia danych</span> (art. 20 RODO).</li>
              <li><span className="text-white font-medium">Prawo do sprzeciwu</span> (art. 21 RODO) &mdash; w zakresie przetwarzania opartego na uzasadnionym interesie.</li>
            </ul>
            <p className="text-sm mt-3">
              Wnioski w zakresie realizacji praw należy kierować na adres: <a href="mailto:spolka@impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">spolka@impresjapr.pl</a>. Administrator odpowie w terminie 30 dni.
            </p>
          </section>

          {/* 8. Cookies */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">8. Pliki cookies i technologie śledzące</h2>
            <p className="text-sm mb-3">VSE używa wyłącznie niezbędnych plików cookies:</p>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li><span className="text-white font-medium">next-auth.session-token</span> &mdash; cookie sesji NextAuth, niezbędne do utrzymania stanu zalogowania. Wygasa po zamknięciu przeglądarki lub po 30 dniach.</li>
              <li><span className="text-white font-medium">next-auth.csrf-token</span> &mdash; token CSRF zabezpieczający formularze. Niezbędny do działania aplikacji.</li>
            </ul>
            <p className="text-sm mt-3">Serwis nie używa cookies śledzących, reklamowych ani analitycznych.</p>
          </section>

          {/* 9. Skarga */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">9. Prawo do skargi</h2>
            <p className="text-sm">
              Mają Państwo prawo do wniesienia skargi do organu nadzorczego &mdash; <span className="text-white font-medium">Prezesa Urzędu Ochrony Danych Osobowych (UODO)</span>, ul. Stawki 2, 00-193 Warszawa, tel. 606-950-000, <a href="https://www.uodo.gov.pl" className="text-violet-400 hover:text-violet-300 underline" target="_blank" rel="noopener noreferrer">www.uodo.gov.pl</a>.
            </p>
          </section>

          {/* 10. Data */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">10. Data wejścia w życie i zmiany Polityki</h2>
            <p className="text-sm">
              Niniejsza Polityka Prywatności wchodzi w życie z dniem <span className="text-white font-medium">1 lipca 2026 r.</span> O każdej istotnej zmianie Polityki Prywatności Użytkownicy zostaną poinformowani drogą elektroniczną na adres e-mail powiązany z Kontem.
            </p>
          </section>

          {/* Footer */}
          <div className="border-t border-white/10 pt-6 text-sm text-gray-500">
            <p>Administrator: IMPRESJA PR SP. Z O.O. &bull; al. Jana Pawła II 27, 00-867 Warszawa &bull; <a href="mailto:spolka@impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">spolka@impresjapr.pl</a></p>
          </div>

        </div>

        {/* Back link */}
        <div className="text-center mt-8">
          <a href="/" className="text-gray-500 hover:text-gray-300 text-sm transition-colors">&larr; Wróć do strony głównej</a>
        </div>
      </div>
    </main>
  )
}

export default function RegulaminPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 py-20 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <span className="inline-block px-4 py-1 rounded-full text-xs font-semibold bg-violet-900/40 text-violet-300 border border-violet-700/40 mb-4 uppercase tracking-widest">
            Dokument prawny
          </span>
          <h1 className="text-3xl md:text-4xl font-extrabold text-white mb-3">
            Regulamin Usług
          </h1>
          <p className="text-gray-400 text-sm">
            Video SEO Engine &mdash; obowiązuje od 1 lipca 2026 r.
          </p>
        </div>

        <div className="glass rounded-2xl p-8 md:p-12 space-y-8 text-gray-300 leading-relaxed">

          {/* §1 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;1. Definicje</h2>
            <ul className="space-y-2 text-sm">
              <li><span className="text-violet-300 font-semibold">Usługodawca</span> &mdash; IMPRESJA PR SP. Z O.O., al. Jana Pawła II 27, 00-867 Warszawa, KRS: 0000981410, NIP: 5273010810, REGON: 522593390.</li>
              <li><span className="text-violet-300 font-semibold">Użytkownik</span> &mdash; osoba fizyczna lub prawna, która zawarła umowę z Usługodawcą poprzez rejestrację w systemie VSE.</li>
              <li><span className="text-violet-300 font-semibold">VSE / Serwis</span> &mdash; platforma Video SEO Engine dostępna pod adresem <a href="https://vse.impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">https://vse.impresjapr.pl</a>.</li>
              <li><span className="text-violet-300 font-semibold">Konto</span> &mdash; indywidualne konto Użytkownika w systemie VSE, chronione hasłem.</li>
              <li><span className="text-violet-300 font-semibold">Plan</span> &mdash; poziom subskrypcji określający zakres dostępu do funkcji (Free, Starter, Pro, Agency).</li>
              <li><span className="text-violet-300 font-semibold">Subskrypcja</span> &mdash; odpłatna usługa dostępu do VSE, odnawiana miesięcznie.</li>
              <li><span className="text-violet-300 font-semibold">Treść Generowana</span> &mdash; dane wyjściowe AI (schema SEO, rozdziały, FAQ) wygenerowane przez VSE na żądanie Użytkownika.</li>
            </ul>
          </section>

          {/* §2 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;2. Zakres usług</h2>
            <p className="text-sm mb-3">VSE świadczy następujące usługi drogą elektroniczną:</p>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Automatyczne generowanie schematów SEO (VideoObject, ClipObject, FAQPage) dla filmów YouTube na podstawie podanego przez Użytkownika adresu URL.</li>
              <li>Generowanie rozdziałów wideo (chapters) i sekcji FAQ przy użyciu modeli AI.</li>
              <li>Publikacja Treści Generowanej na platformach WordPress wskazanych przez Użytkownika (plan Starter i wyższe).</li>
              <li>Historia generowania — dostęp do wcześniej wygenerowanych treści.</li>
              <li>Monitor kanału YouTube — automatyczne wykrywanie nowych filmów (plan Pro i wyższe).</li>
              <li>Dostęp do REST API VSE w celach integracyjnych.</li>
            </ul>
            <p className="text-sm mt-3">Usługodawca zastrzega sobie prawo do zmiany zakresu usług z zachowaniem 30-dniowego okresu wypowiedzenia.</p>
          </section>

          {/* §3 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;3. Plany i płatności</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse mb-4">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left py-2 pr-4 text-white font-semibold">Plan</th>
                    <th className="text-left py-2 pr-4 text-white font-semibold">Cena brutto</th>
                    <th className="text-left py-2 text-white font-semibold">Zakres</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  <tr>
                    <td className="py-2 pr-4 text-violet-300">Free</td>
                    <td className="py-2 pr-4">Bezpłatny</td>
                    <td className="py-2">5 filmów/mies., bez WordPress</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 text-violet-300">Starter</td>
                    <td className="py-2 pr-4">49 zł / mies.</td>
                    <td className="py-2">50 filmów/mies., 3 portale WordPress</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 text-violet-300">Pro</td>
                    <td className="py-2 pr-4">149 zł / mies.</td>
                    <td className="py-2">300 filmów/mies., 10 portali, auto-publish</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 text-violet-300">Agency</td>
                    <td className="py-2 pr-4">499 zł / mies.</td>
                    <td className="py-2">Nielimitowane filmy, 999 portali</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <ul className="space-y-2 text-sm">
              <li>Operatorem płatności jest <span className="text-white font-medium">Stripe Inc.</span> (354 Oyster Point Blvd, South San Francisco, CA 94080, USA). Dane karty płatniczej są przechowywane wyłącznie przez Stripe — Usługodawca nie ma do nich dostępu.</li>
              <li>Podane ceny zawierają podatek VAT 23%.</li>
              <li>Subskrypcja odnawiana jest automatycznie w dniu rocznicy aktywacji planu.</li>
              <li>Usługodawca wystawi fakturę VAT na żądanie Użytkownika przesłane na adres <a href="mailto:spolka@impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">spolka@impresjapr.pl</a>.</li>
            </ul>
          </section>

          {/* §4 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;4. Polityka zwrotów</h2>
            <p className="text-sm mb-3">
              Zgodnie z art. 38 pkt 13 ustawy z dnia 30 maja 2014 r. o prawach konsumenta (Dz.U. 2014 poz. 827 ze zm.), prawo odstąpienia od umowy zawartej na odległość nie przysługuje w odniesieniu do umów o dostarczanie treści cyfrowych, które nie są zapisane na nośniku materialnym, jeżeli spełnianie świadczenia rozpoczęło się za wyraźną zgodą konsumenta.
            </p>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Rejestrując konto i aktywując plan płatny, Użytkownik wyraża zgodę na natychmiastowe rozpoczęcie świadczenia usługi i przyjmuje do wiadomości utratę prawa odstąpienia od umowy.</li>
              <li>Wyjątkowo, w przypadku potwierdzonych błędów technicznych po stronie Usługodawcy, uniemożliwiających korzystanie z usługi przez ponad 72 godziny w danym okresie rozliczeniowym, Użytkownikowi przysługuje proporcjonalny zwrot środków lub przedłużenie okresu subskrypcji.</li>
              <li>Wnioski o zwrot należy kierować na adres <a href="mailto:spolka@impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">spolka@impresjapr.pl</a>.</li>
            </ul>
          </section>

          {/* §5 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;5. Ograniczenia odpowiedzialności</h2>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Usługodawca nie gwarantuje konkretnych wyników SEO. Treść Generowana ma charakter informacyjny i techniczny &mdash; efektywność działań SEO zależy od wielu czynników zewnętrznych.</li>
              <li>Usługodawca nie ponosi odpowiedzialności za przerwy w dostępie wynikające z awarii infrastruktury zewnętrznej (Google, Anthropic, Oracle, Stripe).</li>
              <li>Odpowiedzialność Usługodawcy ograniczona jest do wartości opłat wniesionych przez Użytkownika w ciągu ostatnich 3 miesięcy.</li>
              <li>Użytkownik ponosi wyłączną odpowiedzialność za treści wideo, których URL przekazuje do systemu VSE, oraz za sposób wykorzystania Treści Generowanej.</li>
            </ul>
          </section>

          {/* §6 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;6. Własność intelektualna</h2>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Treść Generowana przez VSE na podstawie materiałów Użytkownika stanowi własność Użytkownika. Usługodawca nie rości sobie praw do Treści Generowanej.</li>
              <li>Kod źródłowy, interfejs użytkownika, logotypy i znaki towarowe VSE są własnością Usługodawcy i są chronione prawem autorskim.</li>
              <li>Użytkownik udziela Usługodawcy niewyłącznej, nieodpłatnej licencji na przetwarzanie przekazanych URL YouTube wyłącznie w celu świadczenia usługi.</li>
            </ul>
          </section>

          {/* §7 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;7. Rozwiązanie umowy</h2>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Użytkownik może anulować subskrypcję w dowolnym momencie poprzez Stripe Customer Portal dostępny w ustawieniach Konta (zakładka &ldquo;Subskrypcja&rdquo;).</li>
              <li>Po anulowaniu dostęp do funkcji płatnych obowiązuje do końca opłaconego okresu rozliczeniowego.</li>
              <li>Usługodawca może wypowiedzieć umowę ze skutkiem natychmiastowym w przypadku naruszenia Regulaminu przez Użytkownika.</li>
              <li>Po rozwiązaniu umowy Usługodawca usunie dane Konta w terminie 30 dni, chyba że przepisy prawa nakazują dłuższe przechowywanie.</li>
            </ul>
          </section>

          {/* §8 */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">&sect;8. Postanowienia końcowe</h2>
            <ul className="list-disc list-inside space-y-2 text-sm">
              <li>Prawem właściwym dla niniejszego Regulaminu jest prawo polskie, w szczególności Kodeks cywilny, ustawa o świadczeniu usług drogą elektroniczną oraz ustawa o prawach konsumenta.</li>
              <li>Spory wynikające z Regulaminu rozpatrują sądy powszechne właściwe dla siedziby Usługodawcy (Warszawa).</li>
              <li>Konsument ma prawo skorzystać z pozasądowych sposobów rozpatrywania sporów (Platforma ODR: <a href="https://ec.europa.eu/consumers/odr" className="text-violet-400 hover:text-violet-300 underline" target="_blank" rel="noopener noreferrer">ec.europa.eu/consumers/odr</a>).</li>
              <li>Regulamin wchodzi w życie z dniem <span className="text-white font-medium">1 lipca 2026 r.</span></li>
              <li>Usługodawca zastrzega sobie prawo do zmiany Regulaminu z 14-dniowym wyprzedzeniem, informując Użytkowników drogą elektroniczną.</li>
            </ul>
          </section>

          {/* Contact */}
          <div className="border-t border-white/10 pt-6 text-sm text-gray-500">
            <p>Kontakt: <a href="mailto:spolka@impresjapr.pl" className="text-violet-400 hover:text-violet-300 underline">spolka@impresjapr.pl</a> &bull; IMPRESJA PR SP. Z O.O. &bull; al. Jana Pawła II 27, 00-867 Warszawa</p>
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

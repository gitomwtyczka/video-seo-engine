# DISPATCH — vse-dev-03

**Data:** 2026-06-15  
**Od:** Supervisor 01  
**Dla:** `vse-dev-03` (Worker — Frontend)  
**Repo:** `gitomwtyczka/video-seo-engine` (branch: `main`)  
**Priorytet:** 🔴 WYSOKI — to core UX produktu

---

## ⛔ ZAKRES NARZĘDZI TEJ SESJI

Ta sesja: TYLKO GitHub MCP + publiczne endpointy.  
**Nie używaj:** file bridge, stellar-relay, Wetty, SSH, bash na VPS.  
Weryfikacja: `curl https://vse.impresjapr.pl/...` lub Swagger `/docs`.  
Deploy: zgłoś Supervisorowi po sesji.

---

## KONTEKST — CO I PO CO

**CO:** Przebudowa dashboardu z surowego JSON-output na dwie pełnoprawne ścieżki UX.

**PO CO:** Teraz dashboard pokazuje surowy JSON po wygenerowaniu SEO — użytkownik nie wie
 co z tym zrobić. Produktem jest SaaS freemium, więc:
- Klient **free** musi dostać gotowe snippety HTML do skopiowania
- Klient **pro/agency** musi dostać przycisk "Opublikuj" który robi to automatycznie

**Stan po sesji vse-dev-02 (2026-06-15):**
- `/v1/generate` działa ✅, zwraca pełny `schema_data` JSON
- Dashboard nie crashuje ✅
- Ale output to surowy JSON w polu tekstowym ❌

**OBOWIĄZKOWO przeczytaj przed pracą:**
- `AGENTS.md` w root repo — sekcja "WIZJA PRODUKTU" + "STANDARD DOKUMENTACJI"
- `.agents/handoff/2026-06-14_vse-dev-01_handoff.md` — 9 GOTCHA deploy
- `.agents/reports/2026-06-15_vse-dev-02_P3-P1-P4.md` — co zmieniono w poprzedniej sesji

---

## ZADANIE — Dashboard UI: 2 ścieżki

### Architektura widoku

```
URL YouTube wklejony przez usera
         ↓
  [Przycisk „Generuj SEO”]
         ↓
  POST /api/v1/generate
         ↓
   schema_data (JSON)
         ↓
  ┌────────────────────────────────────────────┐
  │  SEKCJA WYNIKÓW (obie ścieżki)                  │
  │  ► Tytuł artykułu         [Kopiuj]              │
  │  ► Meta description        [Kopiuj]              │
  │  ► Schema JSON-LD          [Kopiuj]              │
  │  ► FAQ (HTML)              [Kopiuj]              │
  │  ► Chapters (lista)        [Kopiuj]              │
  └────────────────────────────────────────────┘
         ↓
  [widoczne TYLKO dla plan pro/agency]
  ┌────────────────────────────────────────────┐
  │  SEKCJA PUBLIKACJI (pro/agency)                  │
  │  Portal: [dropdown z WP sites]                   │
  │  Status: ● Draft  ○ Publikuj                     │
  │  [Przycisk „Opublikuj na portalu”]               │
  └────────────────────────────────────────────┘
```

---

### Ścieżka A — Sekcja wyników (Free + Pro)

**Plik docelowy:** `web/src/app/dashboard/page.tsx`

Z `schema_data` które wraca z `/v1/generate` wyświetl w blokach:

**1. Tytuł artykułu**
```
Pole: schema_data.post_title
Widok: <h2> + input readonly + [Kopiuj]
```

**2. Meta description**
```
Pole: schema_data.meta_description
Widok: <textarea readonly> + [Kopiuj]
```

**3. Schema JSON-LD**  
*To jest główna wartość — gotowy tag do wklejenia w header strony*
```
Pole: schema_data (całość) sformatowana jako:
<script type="application/ld+json">
{...całe schema_data jako JSON...}
</script>
Widok: <pre><code> z syntaxem + [Kopiuj cały blok]
```

**4. Rozdziały (chapters)**
```
Pole: schema_data.chapters (tablica)
Widok: lista z timestampami i tytułami:
  00:00 — Wprowadzenie
  01:23 — Główny wątek
  ...
+ [Kopiuj jako tekst]
```

**5. FAQ**
```
Pole: schema_data.faq (tablica {question, answer})
Widok: sformatowany HTML jako blok do skopiowania:
  <h3>Często zadawane pytania</h3>
  <details><summary>Pytanie?</summary>Odpowiedź.</details>
  ...
+ [Kopiuj HTML]
```

**Implementacja przycisku Kopiuj:**
```typescript
const copyToClipboard = async (text: string, id: string) => {
  await navigator.clipboard.writeText(text);
  setCopied(id);  // feedback: przycisk zmienia się na "✓ Skopiowano"
  setTimeout(() => setCopied(null), 2000);
};
```

---

### Ścieżka B — Sekcja publikacji (Pro/Agency only)

**CO:** Sekcja widoczna tylko gdy `session.user.plan` to `pro` lub `agency`.
**PO CO:** Automatyczna publikacja — klient nie musi wchodzić do WordPressa.

**Jak sprawdzić plan usera:**
```typescript
// NextAuth session zawiera dane usera z bazy
const { data: session } = useSession();
const isPro = ['pro', 'agency'].includes(session?.user?.plan ?? '');

// Renderuj warunkowo:
{isPro && <PublishSection schemaData={result} />}
```

**Jeśli `session.user.plan` nie zawiera planu** — pobierz z `GET /api/v1/users/me`
(endpoint powinien istnieć w `api/routers/users.py`).

**Komponent PublishSection:**
```typescript
// Stan
const [wpSite, setWpSite] = useState('https://prawy.pl'); // docelowo dropdown
const [postStatus, setPostStatus] = useState<'draft' | 'publish'>('draft');
const [publishing, setPublishing] = useState(false);
const [publishResult, setPublishResult] = useState<any>(null);

// Wywołanie inject
const handlePublish = async () => {
  setPublishing(true);
  try {
    const res = await fetch('/api/v1/inject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        schema_data: schemaData,
        wp_url: wpSite,
        // wp_user i wp_app_password — docelowo z profilu usera
        // MVP: hardcoded lub formularz
        post_status: postStatus,
      })
    });
    const data = await res.json();
    setPublishResult(data);
  } catch (e: any) {
    setPublishResult({ error: e.message });
  } finally {
    setPublishing(false);
  }
};
```

**Uwaga MVP:** W tej sesji WP credentials (url/user/password) mogą być wpisywane
w formularzu ręcznie. Profile management (zapisane portale) to Faza 3.

**Widok sekcji:**
```
┌────────────────────────────────────────┐
│  🚀 Opublikuj na portalu              │
│  WordPress URL: [____________]        │
│  Użytkownik WP: [____________]        │
│  App Password:  [____________]        │
│                                       │
│  Status:  ● Szkic  ○ Publikuj od razu  │
│                                       │
│  [Opublikuj] lub [Tworzenie...] spin  │
└────────────────────────────────────────┘
```

---

## SPRAWDŹ PRZED PISANIEM KODU

```bash
# Jak wygląda aktualne schema_data z generate (publiczny endpoint)
curl -X POST https://vse.impresjapr.pl/api/v1/generate \
  -H 'Content-Type: application/json' \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "llm_provider": "claude", "lang": "pl"}'

# Co ma endpoint inject
curl https://vse.impresjapr.pl/docs  # Swagger — sprawdz schema InjectRequest
```

**Sprawdz pola schema_data** zanim zaczniesz budować komponentu — nazwy pól mogą się
nięco różnić od nazw w tym dispatchu. Swagger i live API są źródłem prawdy.

---

## DEPLOY WORKFLOW

[Deploy po sesji — zgłoś Supervisorowi]

Kod commituj przez GitHub MCP (`create_or_update_file` / `push_files`).
Supervisor zleci oddzielną sesję deploy na VPS.

---

## STANDARD DOKUMENTACJI (obowiązkowy)

Każdy komponent który tworzysz musi mieć komentarz:
```typescript
/**
 * CO: [nazwa] — [co robi]
 * PO CO: [jaki problem użytkownika rozwiązuje]
 * JAK: [jak działa technicznie, z czego korzysta]
 */
```

---

## RAPORTOWANIE

Dual write po sesji:
```
video-seo-engine: .agents/reports/2026-06-15_vse-dev-03_dashboard-ui.md
sonic-void:       .agents/reports/inbox/2026-06-15_vse-dev-03_dashboard-ui.md
```

---

*Dispatch: Supervisor 01 | 2026-06-15 | video-seo-engine*
*Zaktualizowano: 2026-06-15 [sup-worker-01] — usunięto sekcje bash VPS, dodano blokadę narzędzi*

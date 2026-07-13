# DISPATCH — Roadmapa VSE z ludzkimi opisami
**Supervisor:** Supervisor-01  
**Data:** 2026-07-14  
**Dla:** Strateg / Redaktor projektu (ty)

---

## ZADANIE

Przygotuj roadmapę projektu **Video SEO Engine** w formie dokumentu, który:
- Rozumie człowiek bez znajomości kodu
- Mówi co JUŻ działa, co jest w planach i dlaczego
- Nadaje się do wklejenia np. do Notion, strony o projekcie lub jako README dla partnera biznesowego

---

## STRUKTURA DOKUMENTU

### 1. Co to jest Video SEO Engine (2-3 zdania)
Opis dla laika. Co robi, komu służy, jaki problem rozwiązuje.

### 2. Jak to działa (schemat przepływu, po ludzku)
Na wzorze:
```
Wklejasz link YouTube
  ↓
  Silnik pobiera transkrypt i metadane
  ↓
  AI analizuje całą rozmowę
  ↓
  Dostajesz gotowy artykuł, chaptery, FAQ, schema.org
  ↓
  Jeden klik — artykuł ląduje na Twoim WordPressie
```
Rozpisz każdy krok 1-2 zdaniami co się dzieje.

### 3. Co już działa ✔️
Lista funkcji GOTOWYCH i działających produkcyjnie.

Baza do wykorzystania (rozpisz po ludzku, nie technicznie):
- Generacja SEO z transkryptu (artykuł, tytuły, meta, chaptery, FAQ, cytaty)
- Publikacja jednym klikiem na WordPress
- Obsługa wielu portalów równocześnie (agencja)
- Trzy tryby artykułu: pełna analiza / strona oglądania / Google Discover
- YouTube OAuth — automatyczna aktualizacja opisu i chapterów na YouTube
- Panel administracyjny z historią generacji
- Upload własnego pliku VTT (dla materiałów bez automatycznych napisów)
- Obsługa materiałów do ~90 minut
- Linki zewnętrzne do źródeł (E-E-A-T, authority)
- Fallback SEO bez transkryptu (livestreamy, podcasty bez napisów)

### 4. Co jest w planie 🔹

Podziel na trzy horyzonty:

**Najbliższe (1-4 tygodnie):**
- VTT dla długich materiałów i transmisji wielogodzinnych
  (Teraz limit ~90 min. Dla livestreamów 3-8h potrzeba chunkowania —
   AI będzie analizować materiał partiami i składać wynik w całość)

**Średnioterminowe (1-3 miesiące):**
- Lokalne pobieranie transkryptów (VPS jest blokowany przez YouTube —
  potrzebny mechanizm proxy lub lokalny klient który uploaduje VTT)
- Refactor komponentów dashboardu (dashboard-inner.tsx — 7865 linii —
  podzielony na mniejsze moduły dla łatwiejszego rozwoju)
- Dodatkowe portale i integracje WordPress

**Długoterminowe (3-6 miesięcy):**
- Benchmark SEO — porównanie z konkurencją (wyniki w testach: 8/10 vs 2-3/10)
- API dla zewnętrznych integracji
- Obsługa innych platform (Vimeo, Wistia, pliki MP3 podcastów)

### 5. Technologia (krótko, dla ciekawskich)
Nie techniczny opis stacku — raczej: "silnik AI oparty na Claude/Gemini", "publikuje przez WordPress REST API", "działa na serwerze w chmurze Oracle".

---

## FORMAT WYNIKOWY

- Język: **polski**
- Format: Markdown (.md) — działa w Notion, GitHub, edytorach
- Objętość: 1-2 strony A4 (600-1200 słów)
- Bez żargonu technicznego — zrozumiałe dla redaktora, nie programisty
- Można dodać emoji dla czytelności sekcji

---

## GDZIE ZAPISAĆ

GitHub MCP:
```
owner: gitomwtyczka
repo: video-seo-engine
branch: main
path: docs/ROADMAP.md
message: "docs: roadmapa projektu VSE z opisami [strateg]"
```

SHA do sprawdzenia przed zapisem (plik może nie istnieć — sprawdź get_file_contents najpierw).

---

*Dispatch sformułowany przez: Supervisor-01 | video-seo-engine | 2026-07-14*

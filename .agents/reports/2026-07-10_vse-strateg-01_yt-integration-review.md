# Raport Architektoniczny: Integracja YouTube OAuth & Cross-Linking w VSE
**Data:** 2026-07-10
**Od:** vse-strateg-01
**Temat:** yt-integration-review
**Kontekst:** Przegląd architektury bazy i procesu Fazy 3 (MVP YT Manager) zaproponowanego przez agenta dev, na wniosek Użytkownika o identyfikację min (Risk Assessment).

---

## 1. Wykryte Potencjalne Miny (Risk Assessment)

### Mina A: Koszty Quoty YouTube API (Zasoby)
*   **Zagrożenie:** Ograniczenie darmowej quoty YT to 10 000 jednostek na dobę. Update video metadata (`videos.update`) kosztuje aż 50 jednostek! 
*   **Problem:** Jeśli zgodnie z początkowym planem system zaktualizuje SEO w YT, a _następnie_ po opublikowaniu na WP zaktualizuje ten sam film YT _ponownie_ by dodać zwrotny "link", koszt optymalizacji 1 filmu wzrasta do 100 jednostek (100 wideo max dziennie na aplikację).
*   **Rozwiązanie:** Pipeline (proces "Inject") musi buforować dane. VSE musi uderzyć **najpierw** do WordPressa. Po otrzymaniu sukcesu (i wyłuskaniu `post_url`), musi skomponować pełny ładunek (Tytuł + Opis SEO + Link do Artykułu WP + Stopka) i wysłać to do YouTube **tylko raz**. Zysk: 50% redukcja zużycia Quoty Google!

### Mina B: Bezpieczeństwo - Wyciek Refresh Tokens
*   **Zagrożenie:** Agent proponuje zapisać `refresh_token` z Google OAuth czystym tekstem (`Text`) w bazie PostgreSQL (`youtube_channels`). 
*   **Problem:** Utrata bazy danych to kompromitacja kluczy offline do profili YouTube użytkowników. Oznaczałoby to natychmiastowe naruszenie bezpieczeństwa na dużą skalę.
*   **Rozwiązanie:** Wymagane symetryczne szyfrowanie w locie w FastAPI (np. za pomocą biblioteki `cryptography` i `Fernet`). W bazie zapisujemy token zawsze zafoliowany enkrypcją, korzystając z Application Secret, którego nie ma w plikach konfiguracyjnych DB. Uzupełnienie modelu o atrybut szyfrujący getter/setter.

### Mina C: Dependency Lock / Wyścig (Race Condition) na Inject
*   **Zagrożenie:** Użytkownik w oknie publikacji ustawia, że kanał YT ma zostać przypięty. Proces Inject strzela do API WP. 
*   **Problem:** Jeśli API WordPress zwróci błąd HTTP 500 (lub timeout) z powodu słabego serwera docelowego, artykuł nie utworzy się, a proces zwróci błąd i przerwie procedurę. To spowoduje, że film YouTube również NIE zyska opisu i tagów z wygenerowanego SEO. 
*   **Rozwiązanie:** O ile do cross-linku potrzebujemy wygenerować go na jednym oddechu (patrz Mina A), to logika fallbacku (`try/except`) musi w pipeline przewidywać, że jeśli strzał na WP padnie w 100%, to skrypt pominie cross-link, ale **i tak pójdzie zapisać główne SEO na YouTube**.

### Mina D: Prawa dostępu do `WpPortal` (Multitenancy S2S)
*   **Zagrożenie:** Pole `yt_channel_id` zostanie dodane do tabeli Portalu WP. 
*   **Problem:** VSE w fazie 5 planuje "Organizacje/S2S". Jeśli dwie różne firmy korzystają z jednego wspólnego portalu Prawy.pl jako współpracownicy VSE (dzielą ten zasób), jedna nadpisze kanał drugiej (ponieważ WpPortal zyska sztywne ID kanału w bazie, należącego tylko do usera A).
*   **Rozwiązanie:** W obecnej architekturze jest to tolerowane, bo VSE działa single-tenant. Jednak długoterminowo przypisanie Domyslnego Kanału YT do Portalu powinno leżeć w tabeli łączącej Usera i Portal (User_WpPortal_Preferences), a nie w tabeli `WpPortal`. By jednak nie komplikować MVP – przyjmujemy obecny draft, wiedząc że to "dług technologiczny" na moment wdrożenia Organizations w Fazie 5.

## 2. Decyzja Supervisora
Przekazano Użytkownikowi wnioski, sugerując wdrożenie punktów A i B jako bezwzględnych blokerów przed zmergowaniem kodu od Agenta Deweloperskiego. Czekam na dalsze kroki strategiczne od Użytkownika.
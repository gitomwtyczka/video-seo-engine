# DISPATCH: VSE-DEV-20260701 — Regulamin + Polityka Prywatnosci

**Zlecenie od:** Supervisor 02 (sonic-void)
**Data:** 2026-07-01
**Priorytet:** Wysoki — wymaganie prawne przed komercjalizacja (pobieranie platnosci w UE)
**Estymacja:** 1-2 dni

## Dane firmy (zrodlo: KRS, zweryfikowane)

- Pelna nazwa: IMPRESJA PR SPOLKA Z OGRANICZONA ODPOWIEDZIALNOSCIA
- Forma prawna: Sp. z o.o.
- KRS: 0000981410
- NIP: 5273010810
- REGON: 522593390
- Adres: al. Jana Pawla II 27, 00-867 Warszawa
- Email kontaktowy: spolka@impresjapr.pl
- Prezes Zarzadu: Tomasz Brzozowski
- Produkt: Video SEO Engine (VSE) dostepny pod https://vse.impresjapr.pl

## Co zaimplementowac

### 1. Dwa nowe dokumenty jako strony Next.js

- `web/src/app/regulamin/page.tsx` — Regulamin Uslug VSE
- `web/src/app/polityka-prywatnosci/page.tsx` — Polityka Prywatnosci VSE

Obie strony: bez auth guard (publicznie dostepne), dark theme jak reszta aplikacji, statyczna tresc.

### 2. Tresc dokumentow — wytyczne

#### Regulamin (Terms of Service)

Nalezy zawieral min.:
- Definicje (Uslugodawca, Uzytkownik, Konto, Plan, Subskrypcja)
- Zakres uslug (generowanie schema SEO, publikacja na WordPress, historia)
- Plany i platnosci (Free/Starter/Pro/Agency, ceny PLN + VAT, odnowienie miesieczne)
- Stripe jako operator platnosci
- Polityka zwrotow (SaaS — brak zwrotow po dostarczeniu uslug cyfrowych, mozliwy wyjatki)
- Ograniczenia odpowiedzialnosci
- Prawo wlasnosci intelektualnej (tresc generowana przez AI)
- Rozwiazanie umowy (anulowanie subskrypcji)
- Prawo wlasciwe: prawo polskie, sady wlasciwe: Warszawa
- Data wejscia w zycie: 2026-07-01

#### Polityka Prywatnosci (RODO/GDPR)

Musi zawierac (wymogi RODO Art. 13):
- Administrator danych: IMPRESJA PR SP. Z O.O., al. Jana Pawla II 27, 00-867 Warszawa, NIP: 5273010810
- Kontakt: spolka@impresjapr.pl
- Cele przetwarzania: realizacja uslug, rozliczenia (Stripe), komunikacja, email weryfikacja
- Podstawy prawne: art. 6 ust. 1 lit. b RODO (umowa), lit. c (obowiazek prawny), lit. f (uzasadniony interes)
- Kategorie danych: email, imie/nazwisko (opcjonalnie), dane platnosci (Stripe), logi uzytkowania
- Odbiorcy danych: Stripe Inc. (platnosci), Anthropic/Google (AI processing), Vercel/Oracle (hosting)
- Okres przechowywania: przez czas trwania umowy + 5 lat (obowiazki podatkowe)
- Prawa uzytkownika: dostep, sprostowanie, usuniecie, przenosnosc, sprzeciw
- Cookies: sesja, NextAuth, Google Analytics (jesli uzywane)
- Prawo do skargi do UODO
- Data: 2026-07-01

### 3. Linki w stopce/nawigacji

Dodaj linki do obu dokumentow w:
- Stopce aplikacji (jesli istnieje)
- Stronie cennika `/cennik` — przy przycisku zakupu
- Stronie rejestracji `/register` — checkbox "Akceptuje regulamin"

### 4. Checkbox przy rejestracji (opcjonalnie jesli latwe)

Na `/register` dodaj:
```
[ ] Akceptuje Regulamin i Polityke Prywatnosci VSE
```
Z linkami do obu dokumentow. Wymagany do submit formularza.

## ZNANE PULAPKI
1. Tresc prawna — generuj w jezyku polskim (prawo polskie)
2. Stripe jako procesor platnosci wymaga wzmianki w PP
3. AI processing (Anthropic Claude) — dane wideo (URL YouTube) sa przekazywane do API Anthropic — musisz to ujawnic w PP
4. SSH user: ubuntu (NIE root) przy deployu
5. Nie uzywaj ask_permission na SSH
6. GitHub MCP: po commicie weryfikacja newlines

## Deployment

1. Commit przez GitHub MCP
2. SSH: ubuntu@147.224.162.100, git pull && docker compose restart vse-web
3. Weryfikacja: docker logs vse-web --tail 10, sprawdz /regulamin i /polityka-prywatnosci

## Raport koncowy
- Commit SHA dla obu plikow
- Potwierdzenie ze strony sa dostepne publicznie
- Czy checkbox rejestracji zostal dodany

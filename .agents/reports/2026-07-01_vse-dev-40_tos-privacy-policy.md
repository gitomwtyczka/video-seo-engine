# Raport: DISPATCH-VSE-DEV-20260701-TOS-PRIVACY-POLICY

**Callsign:** vse-dev-40  
**Data:** 2026-07-01  
**Status:** ✅ ZAMKNIĘTE

---

## Wykonane zadania

### 1. Strona Regulaminu
- **Ścieżka:** `web/src/app/regulamin/page.tsx`
- **Commit SHA:** `7770748a176ae8400b4858e9268c92f8443cb802`
- **URL:** https://vse.impresjapr.pl/regulamin
- **Status HTTP:** 200 ✅
- **Treść:** 8 paragrafów (§1 Definicje, §2 Zakres usług, §3 Plany i płatności, §4 Polityka zwrotów, §5 Ograniczenia odpowiedzialności, §6 Własność intelektualna, §7 Rozwiązanie umowy, §8 Postanowienia końcowe)
- **Data wejścia w życie:** 2026-07-01
- **Operator płatności:** Stripe Inc. — wzmianka w §3

### 2. Strona Polityki Prywatności (RODO Art. 13)
- **Ścieżka:** `web/src/app/polityka-prywatnosci/page.tsx`
- **Commit SHA:** `c08952e1ec95d2f707659e97b9c258559f959167`
- **URL:** https://vse.impresjapr.pl/polityka-prywatnosci
- **Status HTTP:** 200 ✅
- **Odbiorcy danych:** Stripe Inc. (USA, SCCs), Anthropic PBC (USA, SCCs), Google LLC (USA, SCCs), Oracle Corporation (USA, SCCs)
- **Ujawnienie AI:** ✅ Adresy URL YouTube przekazywane do API Anthropic — jasno opisane w sekcji 5
- **Podstawy prawne:** art. 6 ust. 1 lit. b (umowa), c (obowiązek prawny), f (uzasadniony interes)
- **Prawa UODO:** ✅ wzmianka o możliwości skargi do Prezesa UODO

### 3. Globalny Footer (layout.tsx)
- **Commit SHA:** `629defee8b65cecdd2b6ed7b413ff589a32ebba2`
- **Zmiana:** Dodano globalny `<footer>` do `web/src/app/layout.tsx`
- **Linki:** Regulamin | Polityka Prywatności — widoczne na każdej stronie
- **Firma:** "IMPRESJA PR Sp. z o.o."

### 4. Checkbox rejestracji (register/page.tsx)
- **Commit SHA:** `996c9c35a483ac5d0fd6a9a2d46fb585250c65be`
- **Zmiana:** Dodano checkbox `tosAccepted` do formularza rejestracji
- **Zachowanie:** Przycisk submit `disabled` gdy checkbox niezaznaczony
- **Linki:** `/regulamin` i `/polityka-prywatnosci` (poprawione z `/terms` i `/privacy`)
- **Checkbox:** ✅ wymagany do założenia konta

---

## Deploy

- **Pre-deploy backup:** ✅ wykonany
- **Build:** ✅ `Next.js 14.2.29` — Compiled successfully
- **Static pages:** `/regulamin` i `/polityka-prywatnosci` — skompilowane statycznie
- **Container:** `vse-web` — Recreated & Started ✅

---

## Weryfikacja

| URL | HTTP Status |
|-----|-------------|
| https://vse.impresjapr.pl/regulamin | 200 ✅ |
| https://vse.impresjapr.pl/polityka-prywatnosci | 200 ✅ |

---

## Commity (chronologicznie)

1. `7770748` — feat: add regulamin page [vse-dev-40]
2. `c08952e` — feat: add polityka-prywatnosci page [vse-dev-40]
3. `629defe` — feat: add global footer with links [vse-dev-40]
4. `996c9c3` — feat: add TOS/PP checkbox to register form [vse-dev-40]

---

*vse-dev-40 | video-seo-engine | 2026-07-01 20:40*

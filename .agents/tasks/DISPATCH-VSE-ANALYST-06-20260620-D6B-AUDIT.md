# DISPATCH: VSE-ANALYST-06 — Niezależny audyt D6b + bug Swagger

**Data:** 2026-06-20  
**Priorytet:** 🟡 WAŻNY  
**Zlecający:** Supervisor 01  
**Przypisany do:** vse-analyst-06  
**Repo:** video-seo-engine (branch: main)  
**VPS:** ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100

---

## Kontekst

D6b (architektura kanał/witryna/typy publikacji) to duża zmiana: 13 commitów, 3 nowe pliki, 8 zmodyfikowanych. Worker (vse-dev-21) przeprowadził testy i raportuje 30/31 ✅. 

**Twoje zadanie:** niezależna weryfikacja. Nie ufaj blindly raportowi workera — powtórz testy sam, dodaj własne.

---

## Scope audytu

### 1. Weryfikacja testów workera (30/31)

Pobierz raport testów workera z:
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/reports/inbox/  (szukaj 2026-06-20_vse-dev-21_*test*)
```

Dla każdego testu z raportu:
- Czy test faktycznie testuje to co opisuje?
- Czy wynik jest powtarzalny?
- Czy nie ma false-positive (test przechodzi ale nie sprawdza właściwego warunku)?

### 2. Niezależne testy D6b na VPS

Przeprowadź WŁASNE testy na żywym VPS:

**a) Ładowanie konfiguracji:**
```bash
# Czy channel loader działa?
curl -s https://vse.impresjapr.pl/health | python3 -m json.tool

# Czy profil prawy.yaml ma source_channels?
ssh ... "cd /home/ubuntu/video-seo-engine && python3 -c \"from core.profile import load_profile; p=load_profile('prawy'); print(p.get('source_channels'))\""

# Czy channel prawy-tv.yaml ładuje się?
ssh ... "cd /home/ubuntu/video-seo-engine && python3 -c \"from core.channel import load_channel; c=load_channel('prawy-tv'); print(c)\""
```

**b) Wsteczna kompatybilność:**
- Czy istniejące endpointy API nadal działają bez podania nowych parametrów?
- Czy /generate bez publication_type defaultuje poprawnie?
- Czy stare dane w registry nie powodują crashy?

**c) Nowe funkcjonalności:**
- Czy publication_type=watching_page zmienia zachowanie generatora?
- Czy config_utils.py poprawnie resolvuje ${ZMIENNE} z .env?
- Czy yt_admin.py z channel param nie crashuje?

### 3. Bug Swagger (/openapi.json)

Pre-existing bug: nginx routuje /openapi.json do Next.js zamiast do FastAPI.

**Zbadaj:**
- Jaki jest obecny routing w nginx config? (sprawdź na VPS: `/home/ubuntu/video-seo-engine/nginx/` lub analogiczna lokalizacja)
- Dlaczego poprzednia próba naprawy nie zadziałała?
- Zaproponuj konkretny fix (ale NIE implementuj — to decyzja Supervisora)

---

## Zasady

- ⛔ NIE modyfikuj kodu — jesteś audytorem
- ✅ Uruchamiaj testy read-only (curl, python -c, docker logs)
- ✅ Raportuj każdy znaleziony problem z severity (krytyczny/ważny/niski)
- VPS: `ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100`
- Pliki repo: GitHub MCP

---

## Deliverables

1. **Raport audytu** z tabelą: test | wynik workera | wynik audytora | zgodność
2. **Lista ryzyk** — co może się wysypać w produkcji
3. **Swagger bug** — root cause + propozycja fixu
4. **Dual-write:** raport do `video-seo-engine/.agents/reports/` + `sonic-void/.agents/reports/inbox/`

---

*Supervisor 01 | sonic-void | 20.06.2026*

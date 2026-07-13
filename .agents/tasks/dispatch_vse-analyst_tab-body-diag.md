# DISPATCH — vse-analyst | Diagnostyka: brak zakładki + brak body w podglądzie

**Data:** 2026-07-13  
**Od:** Supervisor 01  
**Do:** vse-analyst (read-only, zero zmian)  
**Priorytet:** BLOKUJĄCY

---

## ⚡ KROK 0

```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: sonic-void
  branch: master
  path: .agents/protocols/dispatch-system-block.md
```
Heartbeat do `video-seo-engine/.agents/heartbeat.json`.

---

## KONTEKST

Po serii dispatchów stan na VPS jest niepłynny. Zgłoszone problemy:
1. Zakładka "Opis YouTube" w panelu wyników nie pojawia się
2. W oknie wysyłki (YouTubePublishModal) brak treści M1 (body intro), widoczna tylko stopka
3. Opis wysyłany na YouTube nie uwzględnia edycji z podglądu

---

## 🔍 ZADANIE — tylko czytanie

### Q1: Czy zakładka "Opis YouTube" jest w `dashboard-inner.tsx`?

Sprawdź w `web/src/app/dashboard/dashboard-inner.tsx`:
- Czy `TabKey` zawiera `'youtube'`?
- Czy tablica `tabs` w `TabBar` zawiera `{ key: 'youtube', label: 'Opis YouTube' }`?
- Czy istnieje blok renderowania dla `activeTab === 'youtube'` (lub `active === 'youtube'`)?
- Czy `ytDescription` i `setYtDescription` są zadeklarowane w `DashboardInner`?
- Czy `useEffect` wypełniający `ytDescription` z `result.raw` istnieje?

**Oczekiwana odpowiedź:** TAK/NIE dla każdego punktu + linia kodu

---

### Q2: Co zawiera `schemaData` po wygenerowaniu?

Sprawdź w `api/routers/generate.py` lub `api/services/generator.py`:
- Jakie pola YT zawiera response z `/v1/generate`? Szukaj: `youtube_description_body`, `youtube_mid_cta`, `youtube_credits`, `youtube_hashtags`
- Czy te pola są zwracane w `schema_data` odpowiedzi?

**Oczekiwana odpowiedź:** lista pól YT zwracanych przez backend

---

### Q3: Co robi `buildPreview` w `YouTubePublishModal.tsx`?

Sprawdź aktualny kod `web/src/app/dashboard/YouTubePublishModal.tsx`:
- Jakich pól używa `buildPreview` do zbudowania podglądu?
- Czy czyta `schemaData.youtube_description_body`?
- Czy wynik `buildPreview` jest wyświetlany w textarea?

**Oczekiwana odpowiedź:** lista pól + czy textarea pokazuje wynik

---

### Q4: Czy frontend wysyła `override_description` do backendu?

Sprawdź w `YouTubePublishModal.tsx` funkcję `publish()`:
- Czy w body POST do `/v1/youtube/publish-description` jest pole `override_description`?
- Jeśli tak — skąd pochodzi jego wartość (`previewText`? `overrideDescription` prop?)?

**Oczekiwana odpowiedź:** TAK/NIE + skąd wartość

---

## 📨 RAPORT

```
video-seo-engine/.agents/reports/2026-07-13_vse-analyst_tab-body-diag.md
sonic-void/.agents/reports/inbox/2026-07-13_vse-analyst_tab-body-diag.md
```

```markdown
# Diagnostyka: zakładka + body

## Q1: Zakładka w dashboard-inner.tsx
[TAK/NIE per punkt + linie]

## Q2: Pola YT w response /v1/generate
[lista pól]

## Q3: buildPreview w YouTubePublishModal
[pola + czy textarea pokazuje wynik]

## Q4: override_description w payload
[TAK/NIE + źródło]

## Root cause per problem
- Brak zakładki: [...]
- Brak body w podglądzie: [...]
- YT się nie aktualizuje: [...]

## Minimalne zmiany do naprawy
[lista plików + co konkretnie]
```

---

*Supervisor 01 | sonic-void | 2026-07-13*

# Raport: [vse-dev-01] Krok 3B — Naprawa YouTube (emoji + video_id debug)
**Model:** Gemini 3.1 Pro High
**Data:** 2026-07-12
**Cel:** Diagnostyka i naprawa problemów z polskimi znakami, logowanie yt-debug.

## Wykonane Kroki

### 0. Diagnostyka (Krok 0A - 0D)
- **Logi API:** Brak logów z próby publikacji (`vse-api`).
- **Tokeny DB:** Wykryto brak kolumny `refresh_token`, użyto poprawnej `refresh_token_encrypted`. Zweryfikowano `has_token = t` dla 3 kanałów.
- **Tabela jobs:** Zaktualizowano zapytanie na tabelę `transcript_jobs` z wykorzystaniem `schema_data`. Zweryfikowano ostatnie zadania: `video_id` oraz `youtube_description_hook` były **NULL**. To wyjaśnia problemy z publikacją.
- **Emoji:** Poprawnie zidentyfikowano 3 błędnie zakodowane emoji w pliku `dashboard-inner.tsx`.

### 1. Naprawa Emoji
- Skrypt zastępujący emoji został uruchomiony na VPS, działając w oparciu o dokładne dopasowanie bajtów (wyeliminowało to problem z błędem kodowania i `errors='replace'`).
- Znaleziono i poprawiono 3 miejsca w pliku `dashboard-inner.tsx` (`\U0001f680`, `\u23f1\ufe0f`, `\u2705`).
- Zmiany zostały zcommitowane przez GitHub API. (SHA commita: `a5542904bce741f694724b382a2b0441b1329f25`).

### 2. Akcja Zależna od Scenariusza
- W związku z diagnozą, problem to mix Scenariusza B (`vid`=NULL) i D (brak requestów na backend w wyniku faila na frontendzie).
- Zastosowano poprawkę do pliku `YouTubePublishModal.tsx` aby wdrożyć polecony debugujący log: `console.log('[YT-DEBUG] videoId:', videoId, 'desc.length:', description.length);`. (SHA commita: `49a94b392674737cb5c7987db16cc166843d4348`).
- Sprawdzono `.env.production` — nie istnieje (routing odbywa się przez relatywny prefix proxy w konfiguracji nginx).

### 3. YT Hook null
- W bazie danych pole `yt_hook` wynosi NULL w ostatnich wpisach z `transcript_jobs`.
- **Notatka / Handoff:** `generator.py` nie zwraca `youtube_description_hook` w swoim wyjściu (`schema_data`) — zakładka YouTube jest pusta. **Wymaga osobnego dispatcha.**

### 4. Deploy
- Wykonano rutynowy backup: `backup_pre_deploy.sh` bez błędów.
- Po restarcie stanu lokalnego git (`git restore`) wdrożono i przebudowano aplikację `vse-web`.

# Dispatch: Fix ReferenceError ytLoading + debug system audit
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Priorytet:** KRYTYCZNY — dashboard crashuje

---

## ⚠️ ZNANE PUŁAPKI
1. Plik ma ~77KB — `replace_file_content` może uciąć kod. Weryfikuj rozmiarem pliku po zapisie.
2. Nie dodawaj early return przed hookami (Rules of Hooks).
3. SHA sprawdzaj przez `get_file_contents` tuż przed `create_or_update_file`.

---

## BŁĄD DO NAPRAWY

```
ReferenceError: ytLoading is not defined
```

Dashboard crashuje po kliknięciu "Wyślij do portalu". Zmienna `ytLoading` jest używana w JSX ale nie jest widoczna w scope.

## KROK 1 — Diagnoza przez SSH

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "grep -n 'ytLoading\|ytChannels\|selectedYtChannel\|YtChannel\|toggleYtChannel' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```

Zwraca linie z deklaracjami i użyciami. Sprawdzić:
- Czy `const [ytLoading, setYtLoading] = useState(false)` jest WEWNĄTRZ funkcji `InjectModal` (nie poza nią)
- Czy `ytChannels`, `selectedYtChannelIds`, `toggleYtChannel` są w tym samym scope
- Czy użycie w JSX (`{ytLoading && ...}`) jest po deklaracjach

## KROK 2 — Naprawa

Jeśli deklaracje są poza `InjectModal` albo w złej kolejności:

Prawidłowe miejsce deklaracji — wewnątrz `function InjectModal({...}) {`, tuż po bloku inicjalizacji istniejącego stanu, PRZED pierwszym `useEffect`:

```typescript
  // YouTube channels
  const [ytChannels, setYtChannels] = useState<YtChannel[]>([])
  const [selectedYtChannelIds, setSelectedYtChannelIds] = useState<string[]>([])
  const [ytLoading, setYtLoading] = useState(false)

  useEffect(() => {
    if (!accessToken) return
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    setYtLoading(true)
    fetch(`${apiUrl}/v1/youtube/channels`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setYtChannels(Array.isArray(data) ? data : []))
      .catch(() => setYtChannels([]))
      .finally(() => setYtLoading(false))
  }, [accessToken])

  const toggleYtChannel = (channelId: string) => {
    setSelectedYtChannelIds((prev) =>
      prev.includes(channelId)
        ? prev.filter((id) => id !== channelId)
        : [...prev, channelId]
    )
  }
```

Popraw plik — wgraj przez `create_or_update_file` z aktualnym SHA.

## KROK 3 — Audit systemu debugowania VSE

Sprawdź czy istnieje system debugowania w repo:

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "find /home/ubuntu/video-seo-engine -name '*debug*' -o -name '*error*boundary*' -o -name '*ErrorBoundary*' 2>/dev/null | grep -v node_modules | grep -v .git"
```

Jeśli jest `ErrorBoundary` lub podobny komponent — sprawdź czy obsługuje nowe typy błędów i raportuj mi w raporcie co znalazłeś (bez modyfikowania — decyzję o zmianie podejmie Supervisor).

## KROK 4 — Deploy i weryfikacja

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web 2>&1 | tail -5"
```

Po 30s:
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs --tail 10 vse-web 2>&1"
```

Oczekiwany wynik: `✓ Compiled successfully`, `✓ Ready in Xms`.

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_ytloading-fix.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_ytloading-fix.md`

Raport musi zawierać:
- Wynik grep (gdzie były deklaracje przed fix)
- Commit SHA
- Wynik `docker logs` (Compiled successfully?)
- Co znalazłeś w systemie debugowania

---
*[Supervisor-03 | sonic-void 11.07.2026]*
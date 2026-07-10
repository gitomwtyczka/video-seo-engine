# React #310 Fix — use-portals.ts

**Agent:** vse-worker  
**Data:** 2026-07-10  
**Status:** ✅ DONE

## Wykonane zmiany

### Root cause
`setLoading(false)` wywoływane synchronicznie gdy `token = undefined` — powodowało React #310 (update state w trakcie renderu innego komponentu).

### Fix
W `web/src/app/dashboard/use-portals.ts` zamieniono:
```typescript
// PRZED
if (!token) { setLoading(false); return }

// PO
if (!token) {
  // Defer setState to avoid React #310 — updating state during another component's render
  Promise.resolve().then(() => setLoading(false))
  return
}
```

## Commit

- **Commit SHA:** `35920a79c51c96bb03c9c7e52fa526ac690d0680`
- **File SHA (after):** `5a16a8765e09447d3752cc8d5a3437c0f9e34c6e`
- **Branch:** main
- **Repo:** gitomwtyczka/video-seo-engine

## Deploy

- **Git pull:** ✅ Fast-forward `419fc84..35920a7`
- **Docker build vse-web:** ✅ `✓ Compiled successfully` (15/15 stron)
- **Container start:** ✅ `vse-web Up`, `✓ Ready in 102ms`
- **Logi błędów:** ❌ brak — logi czyste

## Stan końcowy

| Check | Status |
|---|---|
| GitHub commit | ✅ |
| Plik zweryfikowany (get_file_contents) | ✅ |
| Build bez błędów | ✅ |
| Kontener running | ✅ |
| Logi bez errors | ✅ |

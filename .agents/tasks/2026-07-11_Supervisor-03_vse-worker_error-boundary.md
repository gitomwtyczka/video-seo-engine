# Dispatch: Dodaj ErrorBoundary do VSE Dashboard
**Od:** Supervisor-03  
**Do:** vse-worker (Flash)  
**Data:** 2026-07-11  
**Priorytet:** NORMALNY — poprawa debugowania, nie blokuje żadnej funkcji

---

## ⚠️ ZNANE PUŁAPKI
1. Plik `dashboard-inner.tsx` ma ok. 77KB — weryfikuj rozmiar po zapisie.
2. SHA pobierz przez `get_file_contents` tuż przed `create_or_update_file`.
3. **NIE ROBIMY DEPLOYU** — patrz sekcja STOP niżej.

---

## 🛑 STOP — BEZ DEPLOYU

Ten dispatch wykonuje **wyłącznie commity do GitHub**. Nie uruchamiaj SSH rebuild/docker compose.
Deploy wykona Supervisor osobnym poleceniem po zakończeniu równoległego dispatcha `yt-settings`.

---

## CEL

Audit wykazał brak `ErrorBoundary` w VSE — każdy `ReferenceError` lub nieobsłużony wyjątek React powoduje biały ekran bez informacji o błędzie. Dodaj `ErrorBoundary` który:
- Wyświetla czytelny komunikat zamiast białego ekranu
- Pokazuje nazwę błędu (np. `ReferenceError: accessToken is not defined`)
- Ma przycisk "Odśwież stronę"

---

## IMPLEMENTACJA

### Plik do STWORZENIA: `web/src/app/dashboard/error-boundary.tsx`

```tsx
'use client'

import { Component, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('[VSE ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-gray-900 border border-red-500/30 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">⚠️</span>
              <h2 className="text-lg font-semibold text-red-400">Błąd aplikacji</h2>
            </div>
            <p className="text-sm text-gray-400">
              Wystąpił nieoczekiwany błąd. Spróbuj odświeżyć stronę.
            </p>
            {this.state.error && (
              <pre className="text-xs text-red-300 bg-gray-800 rounded-lg p-3 overflow-auto max-h-32">
                {this.state.error.name}: {this.state.error.message}
              </pre>
            )}
            <button
              onClick={() => window.location.reload()}
              className="w-full py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Odśwież stronę
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
```

### Plik do MODYFIKACJI: `web/src/app/dashboard/dashboard-inner.tsx`

Dodaj import na początku pliku (po istniejących importach):
```typescript
import { ErrorBoundary } from './error-boundary'
```

Opakuj return DashboardInner w ErrorBoundary. Znajdź ostatni `return (` w funkcji `DashboardInner` i opakuj cały JSX:
```tsx
  return (
    <ErrorBoundary>
      {/* cala istniejaca tresc return */}
    </ErrorBoundary>
  )
```

---

## KROKI

1. Utwórz plik `error-boundary.tsx` przez GitHub MCP (`create_or_update_file`)
2. Pobierz `dashboard-inner.tsx` przez `get_file_contents` i dodaj import + opakowanie
3. Wgraj `dashboard-inner.tsx` przez `create_or_update_file`
4. Zweryfikuj `get_file_contents` że import `ErrorBoundary` jest w pliku
5. **STOP — nie robimy deployu. Zakończ na commitach.**

---

## RAPORT — dual-write

1. `video-seo-engine/.agents/reports/2026-07-11_vse-worker_error-boundary.md`
2. `sonic-void/.agents/reports/inbox/2026-07-11_vse-worker_error-boundary.md`

Raport: commit SHA dla `error-boundary.tsx` + commit SHA dla `dashboard-inner.tsx`. BEZ informacji o deployu.

---
*[Supervisor-03 | sonic-void 11.07.2026]*
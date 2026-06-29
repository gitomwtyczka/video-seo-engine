# DISPATCH VSE-DEV-33 — Chirurgiczny fix JSX w dashboard-inner.tsx

**Callsign:** vse-dev (Pro High)
**Projekt:** video-seo-engine
**Data:** 2026-06-29
**Priorytet:** 🔴 PILNY
**Typ:** HOTFIX — 1 plik, 20 linii, deploy

---

## Problem (zdiagnozowany przez Supervisora)

Na stronie `https://vse.impresjapr.pl/dashboard` widoczny jest tekst `)}` pod dropdownem.
Modal `+ Dodaj nowy portal` nie otwiera się po kliknięciu.

**Przyczyna:** Worker z DISPATCH-32 wstawił `Publication type selector` **poza** `<div className="grid grid-cols-2">` przez błąd wcięcia. Linia 1130 zawiera dosłowne `)}` które React renderuje jako tekst na stronie.

---

## Twoje zadanie — TYLKO te zmiany

### Plik: `web/src/app/dashboard/dashboard-inner.tsx`

Pobierz plik przez GitHub MCP. SHA aktualne: `c780bc7c2c7518e2c3482198a42c8e6185172f24`

**Znajdź ten fragment (linie ~1111-1130):**

```tsx
              )}
            </div>

              {/* Publication type selector */}
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Typ publikacji</label>
                <select
                  id="publication-type-selector"
                  value={publicationType}
                  onChange={(e) => setPublicationType(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
                  style={{ backgroundImage: 'url("data:image/svg+xml,...)' ...}}
                >
                  <option value="full_analysis">📝 Pełna analiza</option>
                  <option value="watching_page">🎬 Strona z filmem</option>
                  <option value="discover">🔍 Discover</option>
                </select>
              </div>
            </div>
          )}
```

**Zamień na (fix — 2 spacje mniej wcięcia w publication selector, </div> grida na końcu):**

```tsx
              )}
            </div>

            {/* Publication type selector */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Typ publikacji</label>
              <select
                id="publication-type-selector"
                value={publicationType}
                onChange={(e) => setPublicationType(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition-colors appearance-none cursor-pointer"
                style={{ backgroundImage: 'url("data:image/svg+xml,...)' ...}}
              >
                <option value="full_analysis">📝 Pełna analiza</option>
                <option value="watching_page">🎬 Strona z filmem</option>
                <option value="discover">🔍 Discover</option>
              </select>
            </div>
          </div>
```

**Co się zmieniło:**
- `{/* Publication type selector */}` i cały blok: usunięto 2 spacje wcięcia (14→12)
- Ostatnie dwie linie: `</div>` + `)}` zastąpiono przez `</div>` (zamknięcie grida)
- Efekt: publication type selector wraca do siatki `grid-cols-2`, `)}` znika z DOM

**WAŻNE:** Styl `backgroundImage` w `<select>` skopiuj 1:1 z oryginału — nie przepisuj ręcznie.

---

## Deploy po commicie

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-web && docker compose -f docker-compose.vse.yml up -d vse-web"
```

Po deploy: `docker compose -f docker-compose.vse.yml logs vse-web --tail 10` — brak błędów kompilacji.

---

## Deliverable

- [ ] Fix wcięcia publication type selector (2 spacje)
- [ ] Usunięte `)}` z linii 1130
- [ ] Commit na main
- [ ] Deploy vse-web na VPS
- [ ] Logi bez błędów

**Dual-write raport:**
- `video-seo-engine/.agents/reports/2026-06-29_vse-dev_dashboard-jsx-fix.md`
- `sonic-void/.agents/reports/inbox/2026-06-29_vse-dev_dashboard-jsx-fix.md`

Heartbeat `status: done`.

---

*[Supervisor 01 | sonic-void 29.06.2026]*

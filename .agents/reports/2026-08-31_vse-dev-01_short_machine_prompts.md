# Raport: Aktualizacja promptów Short Machine (YouTube Best Practices 2025/2026)

**Data:** 2026-08-31 22:32
**Autor:** `vse-dev-01`
**Repozytorium:** `gitomwtyczka/video-seo-engine` (branch: `main`)

---

## 1. Cel zadania
Dostosowanie promptów generowania metadanych Short Machine do wytycznych YouTube 2025/2026 oraz rozszerzenie modeli o pole `related_video_id` (powiązanie z odcinkiem-rodzicem).

---

## 2. Zrealizowane zmiany

### A. `core/shorts.py` (commit: `4659a18ad15f3bb939976c9a6f34f511545cb3fc`)
1. **`optimized_title` (oraz `suggested_title`):**
   - Limit: **Max 45 znaków** (twarde ograniczenie w prompcie + sanitizator regex i word-boundary cut).
   - **Kategoryczny zakaz `#Shorts`** w tytule (usunięty z promptu, przykładów oraz czyszczony w sanityzacji).
   - **Front-loading:** najważniejsze słowa w pierwszych 30 znakach.
   - Emocja i luka ciekawości (*curiosity gap*).
2. **`description`:**
   - 1–3 zdania (150–350 znaków z hashtagami).
   - Słowa kluczowe z transkrypcji pod indeksację AI YouTube.
   - CTA z `@NazwaKanału` mention.
   - 3–5 hashtagów na końcu opisu.
   - **Zakaz URLi** (usunięte wszelkie linki).
3. **`hashtags` (oraz `tags`):**
   - Usunięto `#Shorts` / `#shorts` z listy.
   - Max 5 hashtagów tematycznych / niszowych.
4. **`pinned_comment`:**
   - Zakaz linków / URLi.
   - Polaryzujące pytanie na bazie puenty + CTA: „całą rozmowę znajdziesz w powiązanym filmie poniżej”.
   - Format: `💬 [Pytanie]? 👇\n\n🎬 Całą rozmowę znajdziesz w powiązanym filmie poniżej!`.
5. **`ShortCandidate` dataclass:**
   - Dodane pola: `optimized_title`, `description`, `hashtags`, `pinned_comment`, `related_video_id`.
   - Zachowano `suggested_title` i `tags` jako zsynchronizowane aliasy dla kompatybilności wstecznej.
   - Zaktualizowano `to_dict()`.

### B. `api/models/response.py` (commit: `c7e5fd384c7a073c01243a84c33a5d421a57d05b`)
- Dodano model `DescribeResponse`:
  - `status: str = "ok"`
  - `optimized_title: str = ""`
  - `suggested_title: str = ""`
  - `description: str = ""`
  - `hashtags: List[str] = []`
  - `tags: List[str] = []`
  - `pinned_comment: str = ""`
  - `related_video_id: Optional[str] = None`
  - `start_sec: Optional[float] = None`
  - `end_sec: Optional[float] = None`
  - `error: Optional[str] = None`

### C. `api/routers/shorts.py` (commit: `1af70b476576bccc7165564a5da24f24f9eaf888`)
- `CandidatesRequest` rozszerzony o `channel_name` i `related_video_id`.
- `get_candidates` (`POST /v1/shorts/candidates`) przekazuje `related_video_id` i `channel_name` oraz dołącza `related_video_id` do każdego kandydata.
- `regenerate_title` (`POST /v1/shorts/title`) zaktualizowany prompt i sanitizator pod standardy 2025/2026.
- Dodano endpoint `POST /v1/shorts/describe` (model wejściowy `DescribeRequest`, wyjściowy `DescribeResponse`).

---

## 3. Lista commitów SHA
- `c7e5fd384c7a073c01243a84c33a5d421a57d05b` (`api/models/response.py`)
- `4659a18ad15f3bb939976c9a6f34f511545cb3fc` (`core/shorts.py`)
- `1af70b476576bccc7165564a5da24f24f9eaf888` (`api/routers/shorts.py`)
- `e874edbfb534f05ea09f4df7a78ef511a6ea58cd` (`.agents/heartbeat.json`)

---

## 4. Status deploy / backup
- Pre-deploy backup (`/home/ubuntu/scripts/backup_pre_deploy.sh`) wykonany pomyślnie na VPS (`147.224.162.100`).
- Kod zsynchronizowany na GitHub remote `main`.

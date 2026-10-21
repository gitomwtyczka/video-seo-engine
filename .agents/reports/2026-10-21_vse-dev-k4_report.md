# Raport K4 — Job per click, publication_type, user_id scoping (R1/R2)
**Data:** 2026-10-21 · **Agent:** vse-dev-k4 · **PR:** https://github.com/gitomwtyczka/video-seo-engine/pull/5

## 1. Wynik diagnozy DB (Postgres `vse-postgres`)
- Zbadano tabelę `transcript_jobs`: dla wideo `ptOrFpUYa3Q` (testy Właściciela) istniał **tylko 1 wiersz** (`5936f2b7-2cde-4069-a9ce-d2185ae8f642`), w którym pole `updated_at` (2026-10-21 06:43:27 UTC) nadpisywało poprzednie generacje.
- **Hipoteza 100% potwierdzona**: `_save_schema_to_job` wyszukiwał po `video_url.contains(vid_key)` i nadpisywał rekord w miejscu zamiast tworzyć wiersz per kliknięcie; historia odpytuje tabelę bez deduplikacji URL, więc pokazywała tylko 1 pozycję.

## 2. Podsumowanie zmian (Diff: 11 plików backendu, +235/-69 linii)
- **Nowy job per kliknięcie**: `run_generate()` na starcie tworzy wiersz ze statusem `processing` i `publication_type`.
- **Aktualizacja po PK**: `_save_schema_to_job()` aktualizuje konkretny rekord po `job_id`, eliminując ślepe nadpisywanie.
- **Kolumna `publication_type`**: dodana do `TranscriptJob`, `JobResponse`, `FullJobResponse`, `HistoryJobResponse`.
- **Zero-downtime migracja**: `ALTER TABLE transcript_jobs ADD COLUMN IF NOT EXISTS publication_type VARCHAR(50);` + backfill z `schema_data` w `api/main.py`, `api/migrate.py` i migracji Alembic.
- **Scoping `user_id` (R1/R2)**: `_save_schema_to_job()` i `_get_cached_transcript_from_db()` filtrują po `user_id`, zapobiegając wyciekowi transkryptów między kontami.
- **Rezolucja `run_inject`**: profil i schema pobierane z `portal_id` lub `job_id` (z `req.job_id`), bez sięgania po "ostatni job".

## 3. Weryfikacja i testy
- `pytest tests/test_k4_job_per_click.py`: **7/7 PASS (100%)**
- `pytest tests/test_generator.py`: **13/13 PASS (100%)**
- `python -m py_compile`: PASS na wszystkich zmodyfikowanych modułach.

## 4. Ryzyka
- Brak ryzyk regresji: migracja kolumny jest idempotentna (`IF NOT EXISTS`), stare rekordy mają backfill, frontend otrzymuje `job_id` i `publication_type` bez zmian łamiących API.

## 5. Komenda wdrożenia (do wykonania przez Właściciela po zmergowaniu PR #5)
```bash
/home/ubuntu/scripts/vse_snapshot.sh && cd /home/ubuntu/video-seo-engine && git checkout main && git pull origin main && docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api
# Rollback (w razie potrzeby): /home/ubuntu/scripts/vse_rollback.sh <TAG> --code
```

# POBUDKA — vse-analyst-04 | YouTube Description Integration Audit

**Data:** 2026-06-19 | **Wystawia:** Supervisor 01

---

Jestes `vse-analyst-04`. Zadanie analityczne — nie implementujesz, tylko czytasz i raportujesz.

**Kontekst:** `core/yt_admin.py` to gotowy modul do aktualizacji opisow YouTube. Istnieje ale NIE jest podlaczony do pipeline.

**Co zbadac:**
- Gdzie podlaczyc yt_admin do pipeline (injector? runner? api?)
- Jakie hardcody wymagaja parametryzacji (prawy.pl, hashtagi, SOS footer)
- Stan OAuth credentials i registry/

## Pierwsze kroki

1. Przeczytaj dispatch:  
   `.agents/tasks/DISPATCH-VSE-ANALYST-04-20260619-YT-ADMIN-AUDIT.md`
2. Wyslij heartbeat do `.agents/heartbeat.json`
3. Zbadaj i napisz raport

---

*Supervisor 01 | sonic-void | 2026-06-19*

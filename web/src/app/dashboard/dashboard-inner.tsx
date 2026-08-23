'use client'



/**



 * CO: Dashboard — główny widok aplikacji po zalogowaniu



 * PO CO: Daje użytkownikowi dwie ścieżki:



 *   A (Free/Starter) — generuje SEO i pokazuje gotowe snippety HTML do skopiowania



 *   B (Pro/Agency)   — dodatkowo umożliwia automatyczną publikację na WordPress



 * JAK: Wywołuje POST /v1/generate → schema_data → renderuje 3 zakładki wynikowe



 *      (Schemat, Artykuł, Rozdziały). Dla planu pro/agency InjectModal → POST /v1/inject.
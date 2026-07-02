# Raport: Dodanie logowania Google do formularza rejestracji

## Co
Dodano przycisk "Kontynuuj z Google" (OAuth) na ekranie rejestracji nowego konta w aplikacji webowej VSE (`web/src/app/register/page.tsx`).

## Po co
Aby ułatwić użytkownikom zakładanie kont przy użyciu kont Google, zapewniając identyczne doświadczenie jak przy logowaniu i zmniejszając opór (friction) przy procesie rejestracji.

## Jak
1. Zapożyczono ostylowany przycisk OAuth oraz separator "lub" z `web/src/app/login/page.tsx`.
2. Dołączono import `signIn` z `next-auth/react` oraz ikonę `Chrome` z `lucide-react`.
3. Przycisk odnosi się poprzez protokół OAuth przyznawania uwierzytelnień - `signIn('google', { callbackUrl: '/dashboard' })`.
4. Wykonano deploy na środowisko VPS na Oracle Cloud (w tym backup przed deployem `backup_pre_deploy.sh` oraz komenda Docker dla `vse-web`). Wdrożenie zakończone pomyślnie.

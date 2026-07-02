# Raport Diagnostyczny: Błąd weryfikacji email (404 Not Found)

## 🐛 Opis błędu
Podczas rejestracji użytkownik otrzymuje email z linkiem weryfikacyjnym. Po kliknięciu w link, API zwraca goły JSON z błędem: `{"detail":"Not Found"}`.

## 🔎 Root Cause (Przyczyna)
Problem leży na styku konfiguracji proxy w Nginx oraz generowania linków w backendzie (FastAPI).

Zgodnie z konfiguracją Nginx na VPS (`/etc/nginx/conf.d/vse.conf` / `default.conf` w kontenerze `crimson-nginx`):
1. Ścieżki zaczynające się od `/v1/` są kierowane bezpośrednio do FastAPI (np. `/v1/auth/login`).
2. Ścieżki zaczynające się od `/api/` są również kierowane do FastAPI, ale **Nginx nie obcina prefiksu `/api`** w przekazywanym żądaniu (brak trailing slasha w `proxy_pass http://172.17.0.1:8085;`).

W kodzie w `api/utils/email.py` link do weryfikacji jest twardo zakodowany z prefiksem `/api/v1/`:
```python
# ŹLE
verify_url = f"{base_url.rstrip('/')}/api/v1/auth/verify?token={token}"
```
Ponieważ Nginx nie obcina `/api/`, FastAPI dostaje pełny URL: `/api/v1/auth/verify`. 
Jednakże router auth w FastAPI jest zdefiniowany z prefiksem `/v1/auth` (bez `/api/`), dlatego zwraca domyślny błąd 404 `{"detail": "Not Found"}`.

Ten sam problem dotyczy logowania przez Google. Zmienna środowiskowa jako fallback również posiada zły prefiks.

## 🛠️ Rozwiązanie (Fix)
Należy zaktualizować linki tak, aby korzystały ze ścieżki `/v1/`, do której Nginx ma już ustawioną prawidłową regułę routingu.

Do poprawy w kodzie:

**1. `api/utils/email.py` (linia 83):**
Było:
```python
verify_url = f"{base_url.rstrip('/')}/api/v1/auth/verify?token={token}"
```
Ma być:
```python
verify_url = f"{base_url.rstrip('/')}/v1/auth/verify?token={token}"
```

**2. `api/routers/auth.py` (linie 21-24):**
Było:
```python
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "https://vse.impresjapr.pl/api/v1/auth/google/callback"
)
```
Ma być:
```python
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "https://vse.impresjapr.pl/v1/auth/google/callback"
)
```

Po tej zmianie, frontend wyśle użytkownika na `https://vse.impresjapr.pl/v1/auth/...`, Nginx poprawnie złapie `location /v1/` i przekaże to do FastAPI, a FastAPI skutecznie rozpozna ścieżkę.

## ✅ Kolejne kroki
Gotowy fix jest do wdrożenia przez agenta `vse-dev-01` w ramach dispatchu naprawczego.

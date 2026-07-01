"""
Auth router: register, login, token refresh, Google OAuth.
"""
import os
import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.db import get_db
from api.models.user import User
from api.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    get_current_user, SECRET_KEY, ALGORITHM
)
from api.utils.email import send_verification_email
from jose import JWTError, jwt

router = APIRouter(prefix="/v1/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "https://vse.impresjapr.pl/api/v1/auth/google/callback"
)


# --- Pydantic schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleTokenExchangeRequest(BaseModel):
    """
    CO: Żądanie wymiany tokenu Google na token VSE.

    PO CO: NextAuth GoogleProvider dostarcza id_token podpisany przez Google.
    Frontned nie posiada naszego backend JWT — dopiero po zamianie tutaj
    uzyskuje token VSE, z którym może pobrać plan/is_admin przez /v1/users/me.

    JAK: NextAuth jwt callback → POST /v1/auth/google/token-exchange
    z id_token z konta Google → backend weryfikuje przez Google tokeninfo,
    upsertuje usera, zwraca nasz JWT pair.
    """
    id_token: str


# --- Endpoints ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    CO: Rejestracja nowego użytkownika email+hasło.

    PO CO: Tworzy konto i wysyła email weryfikacyjny (RODO).
           Użytkownik musi potwierdzić adres email przez link.

    JAK: Generuje verification_token, zapisuje w bazie.
         Wysyła email przez send_verification_email (soft fail — nie blokuje rejestracji).
    """
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters"
        )

    verification_token = secrets.token_urlsafe(32)

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        plan_id="free",
        is_verified=False,
        verification_token=verification_token
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email — soft fail (don’t block registration if SMTP unavailable)
    base_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
    try:
        send_verification_email(payload.email, verification_token, base_url)
    except Exception:  # noqa: BLE001
        pass  # Email failure must not block registration

    return {
        "message": "Registration successful. Please check your email to verify your account.",
        "user_id": str(user.id)
    }


@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """
    CO: Weryfikuje adres email użytkownika.

    PO CO: Potwierdza tożsamość użytkownika przez kliknięcie linku z emaila.
           Spełnia wymogi RODO dla potwierdzenia adresu.

    JAK: Szuka usera z danym verification_token.
         Ustawia is_verified=True, czyści token.
         Redirectuje na /dashboard?verified=1.
    """
    result = await db.execute(
        select(User).where(User.verification_token == token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired verification token"
        )

    user.is_verified = True
    user.verification_token = None
    await db.commit()

    frontend_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
    return RedirectResponse(f"{frontend_url}/dashboard?verified=1")


@router.post("/resend-verification")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    CO: Ponownie wysyła email weryfikacyjny.

    PO CO: Użytkownik mógł nie otrzymać pierwszego emaila lub token wygasł.
           Umożliwia samodzielne wysłanie nowego linku weryfikacyjnego.

    JAK: Generuje nowy token, aktualizuje bazę, wysyła email.
         Zwraca błąd 400 jeśli konto już zweryfikowane.
    """
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )

    # Generate new token
    new_token = secrets.token_urlsafe(32)

    # Refresh user from DB to get writable instance
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.verification_token = new_token
    await db.commit()

    base_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
    email_sent = False
    try:
        email_sent = send_verification_email(current_user.email, new_token, base_url)
    except Exception:  # noqa: BLE001
        pass

    return {
        "message": "Verification email sent" if email_sent else "Token regenerated (email not sent — SMTP not configured)",
        "email_sent": email_sent
    }


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password, returns JWT pair."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated"
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.email),
        refresh_token=create_refresh_token(str(user.id))
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new JWT pair."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token"
    )
    try:
        data = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = data.get("sub")
        if not user_id or data.get("type") != "refresh":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.email),
        refresh_token=create_refresh_token(str(user.id))
    )


@router.post("/google/token-exchange", response_model=TokenResponse)
async def google_token_exchange(
    payload: GoogleTokenExchangeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    CO: Wymienia Google id_token na parę JWT VSE (access_token + refresh_token).

    PO CO: NextAuth GoogleProvider nie przekazuje naszego backend JWT do jwt callback.
    Ten endpoint uzupełnia brakujące ogniwo: NextAuth dostaje Google id_token
    z account.id_token, wysyła go tutaj, dostaje nasz JWT, zapisuje do sesji.
    Dzięki temu plan i is_admin są dostępne natychmiast po pierwszym logowaniu,
    bez czekania 5 minut na refresh.

    JAK:
    1. Weryfikuje Google id_token przez Google tokeninfo endpoint
    2. Pobiera google_id (sub) i email
    3. Upsertuje usera w bazie (create or link by email)
    4. Google OAuth users — auto-verified (is_verified=True)
    5. Zwraca nasz JWT pair — identycznie jak POST /v1/auth/login
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )

    # Verify the Google id_token via Google's tokeninfo endpoint
    async with httpx.AsyncClient() as client:
        tokeninfo_resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": payload.id_token},
        )

    if tokeninfo_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google id_token"
        )

    tokeninfo = tokeninfo_resp.json()

    # Verify the token was issued for our app (security check)
    if tokeninfo.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google id_token audience mismatch"
        )

    google_id = tokeninfo.get("sub")
    email = tokeninfo.get("email")
    full_name = tokeninfo.get("name")
    email_verified = tokeninfo.get("email_verified") == "true"

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required fields in Google id_token"
        )

    # Upsert user — identycznie jak w /google/callback
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        # Check if email already exists (link accounts)
        result2 = await db.execute(select(User).where(User.email == email))
        user = result2.scalar_one_or_none()
        if user:
            user.google_id = google_id
            # Auto-verify existing user when linking Google account
            if not user.is_verified and email_verified:
                user.is_verified = True
                user.verification_token = None
        else:
            user = User(
                email=email,
                full_name=full_name,
                google_id=google_id,
                plan_id="free",
                is_verified=email_verified  # Google-verified = auto-verified
            )
            db.add(user)

    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.email),
        refresh_token=create_refresh_token(str(user.id))
    )


@router.get("/google")
async def google_oauth_start():
    """Redirect user to Google OAuth consent screen."""
    params = (
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_oauth_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback, create/login user, return JWT."""
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )
        token_data = token_resp.json()
        if "error" in token_data:
            raise HTTPException(status_code=400, detail=f"Google OAuth error: {token_data['error']}")

        # Get user info
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        userinfo = userinfo_resp.json()

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    full_name = userinfo.get("name")

    # Upsert user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        # Check if email already exists (link accounts)
        result2 = await db.execute(select(User).where(User.email == email))
        user = result2.scalar_one_or_none()
        if user:
            user.google_id = google_id
            # Auto-verify when linking Google account
            if not user.is_verified:
                user.is_verified = True
                user.verification_token = None
        else:
            user = User(
                email=email,
                full_name=full_name,
                google_id=google_id,
                plan_id="free",
                is_verified=True  # Google verified email
            )
            db.add(user)

    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))

    # Redirect to frontend with tokens in query (frontend will store in httpOnly cookie)
    frontend_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
    return RedirectResponse(
        f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
    )

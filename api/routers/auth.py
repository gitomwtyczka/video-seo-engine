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
    id_token: str


# --- Endpoints ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
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

    base_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
    try:
        send_verification_email(payload.email, verification_token, base_url)
    except Exception:  # noqa: BLE001
        pass

    return {
        "message": "Registration successful. Please check your email to verify your account.",
        "user_id": str(user.id)
    }


@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
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
    CO: Ponownie wysyla email weryfikacyjny.
    PO CO: Uzytkownik mogl nie otrzymac pierwszego emaila lub token wygasl.
    JAK: Generuje nowy token, aktualizuje baze, wysyla email.
         Zwraca blad 400 jesli konto juz zweryfikowane.
    """
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )

    new_token = secrets.token_urlsafe(32)

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.verification_token = new_token
    await db.commit()

    base_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
    email_sent = False
    email_error = None
    try:
        email_sent = send_verification_email(current_user.email, new_token, base_url)
    except Exception as exc:  # noqa: BLE001
        email_error = str(exc)

    if email_sent:
        message = "Verification email sent"
    elif email_error:
        message = f"Token regenerated (email send failed: {email_error})"
    else:
        # send_verification_email returned False - see api logs for SMTP error details
        message = "Token regenerated (email not sent - check server logs for SMTP error)"

    return {
        "message": message,
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
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )

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

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result2 = await db.execute(select(User).where(User.email == email))
        user = result2.scalar_one_or_none()
        if user:
            user.google_id = google_id
            if not user.is_verified and email_verified:
                user.is_verified = True
                user.verification_token = None
        else:
            user = User(
                email=email,
                full_name=full_name,
                google_id=google_id,
                plan_id="free",
                is_verified=email_verified
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

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        userinfo = userinfo_resp.json()

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    full_name = userinfo.get("name")

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result2 = await db.execute(select(User).where(User.email == email))
        user = result2.scalar_one_or_none()
        if user:
            user.google_id = google_id
            if not user.is_verified:
                user.is_verified = True
                user.verification_token = None
        else:
            user = User(
                email=email,
                full_name=full_name,
                google_id=google_id,
                plan_id="free",
                is_verified=True
            )
            db.add(user)

    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))

    frontend_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
    return RedirectResponse(
        f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
    )

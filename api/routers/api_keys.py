import secrets
import hashlib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from api.db import get_db
from api.auth import get_current_user
from api.models.user import ApiKey, User

router = APIRouter(prefix="/v1/api-keys", tags=["API Keys"])

class ApiKeyCreate(BaseModel):
    name: str

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key: Optional[str] = None
    created_at: datetime

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

@router.post("", response_model=ApiKeyResponse)
async def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    raw_key = f"vse_{secrets.token_urlsafe(32)}"
    key_hash = hash_key(raw_key)
    new_key = ApiKey(
        id=uuid.uuid4(),
        user_id=current_user.id,
        key_hash=key_hash,
        name=body.name,
        is_active=True,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return ApiKeyResponse(
        id=str(new_key.id),
        name=new_key.name,
        key=raw_key,
        created_at=new_key.created_at,
    )

@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id, ApiKey.is_active == True)
    )
    keys = result.scalars().all()
    return [ApiKeyResponse(id=str(k.id), name=k.name, created_at=k.created_at) for k in keys]

@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid API key ID format")
        
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_uuid, ApiKey.user_id == current_user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    await db.commit()
    return {"status": "deleted"}

"""
panel.auth
~~~~~~~~~~

JWT kimlik doğrulama yardımcıları ve FastAPI dependency'leri.

- create_access_token: JWT encode (pyjwt)
- decode_access_token: JWT decode + doğrulama
- get_password_hash: bcrypt hash
- verify_password: bcrypt doğrulama
- get_current_tenant: JWT'den tenant_id çıkarır (role=tenant zorunlu)
- get_current_admin: JWT'den admin_id çıkarır (role=super_admin zorunlu)

Author: Mergen Platform -- Auth Team
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# Config — .env'den oku
# ---------------------------------------------------------------------------
_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "mergen-super-secret-change-in-production")
_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

import bcrypt


def get_password_hash(plain: str) -> str:
    """Düz metin şifreyi bcrypt hash'ine dönüştürür (72 byte sınırı korumalı)."""
    pwd_bytes = plain.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Düz metin şifreyi hash ile karşılaştırır."""
    if not hashed:
        return False
    pwd_bytes = plain.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT encode / decode
# ---------------------------------------------------------------------------

def create_access_token(sub: str, role: str, expire_minutes: Optional[int] = None) -> str:
    """
    JWT access token oluşturur.

    Args:
        sub: Token sahibinin kimliği (tenant_id veya admin_id).
        role: "tenant" veya "super_admin".
        expire_minutes: Geçerlilik süresi (dakika). None ise env'den okunur.

    Returns:
        Kodlanmış JWT string'i.
    """
    minutes = expire_minutes if expire_minutes is not None else _EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": sub,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    JWT token'ı doğrular ve payload'ı döner.

    Raises:
        HTTPException 401: Token geçersiz, süresi dolmuş veya hatalı.
    """
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum süresi doldu. Lütfen yeniden giriş yapın.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgisi.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# FastAPI Security Scheme
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
    """Bearer token'ı çıkarır; yoksa 401 fırlatır."""
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------

def get_current_tenant(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """
    Kâtip endpoint'leri için JWT dependency.

    JWT'den tenant_id çıkarır. role == "tenant" zorunludur.
    X-Tenant-ID header'ına HİÇBİR fallback yoktur.

    Returns:
        tenant_id string'i.

    Raises:
        HTTPException 401: Token eksik veya geçersiz.
        HTTPException 403: Token geçerli ama role uyuşmuyor (super_admin bu endpoint'e giremez).
    """
    token = _extract_token(credentials)
    payload = decode_access_token(token)

    role = payload.get("role")
    if role != "tenant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu endpoint yalnızca ajans/tenant hesapları için erişilebilir.",
        )

    tenant_id = payload.get("sub")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token içinde geçersiz kimlik.",
        )
    return tenant_id


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """
    Admin endpoint'leri için JWT dependency.

    JWT'den admin_id çıkarır. role == "super_admin" zorunludur.

    Returns:
        admin_id string'i.

    Raises:
        HTTPException 401: Token eksik veya geçersiz.
        HTTPException 403: Token geçerli ama role uyuşmuyor.
    """
    token = _extract_token(credentials)
    payload = decode_access_token(token)

    role = payload.get("role")
    if role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu endpoint yalnızca süper yöneticilere açıktır.",
        )

    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token içinde geçersiz kimlik.",
        )
    return admin_id

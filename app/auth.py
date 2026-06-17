import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from passlib.hash import argon2
from jose import jwt, JWTError

SECRET_KEY = os.environ.get("JWT_SECRET", "neocortex-dev-secret-key-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8


def hash_password(password: str) -> str:
    return argon2.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return argon2.verify(password, hashed)


def create_token(user_data: dict) -> str:
    payload = {**user_data, "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def get_current_user(neocortex_token: Optional[str] = Cookie(default=None)) -> dict:
    if not neocortex_token:
        raise HTTPException(status_code=401, detail="לא מחובר")
    try:
        return decode_token(neocortex_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="טוקן פג תוקף — נא להתחבר מחדש")


def require_doctor(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("doctor", "admin", "nurse", "intern"):
        raise HTTPException(status_code=403, detail="גישה מותרת לצוות רפואי בלבד")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="גישה מותרת למנהלים בלבד")
    return user


def require_permission(perm: str):
    """Server-side permission check — admin always passes, others need explicit permission."""
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") == "admin":
            return user
        if perm not in user.get("permissions", []):
            raise HTTPException(status_code=403, detail=f"אין הרשאה לפעולה זו")
        return user
    return dep

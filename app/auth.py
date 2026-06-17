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


ROLE_DEFAULT_PERMISSIONS = {
    "doctor": ["view_records", "edit_records", "prescribe", "clinical_analysis", "session_summary", "drug_interactions"],
    "intern": ["view_records", "clinical_analysis", "session_summary"],
    "nurse":  ["view_records", "edit_records", "drug_interactions"],
    "secretary": ["view_records"],
}


def require_permission(perm: str):
    """Server-side permission check — admin always passes, others check JWT permissions.
    Falls back to role defaults for tokens issued before permissions were added."""
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") == "admin":
            return user
        perms = user.get("permissions")
        if not perms:
            # Old token without permissions — fall back to role defaults
            perms = ROLE_DEFAULT_PERMISSIONS.get(user.get("role", ""), [])
        if perm not in perms:
            raise HTTPException(status_code=403, detail="אין הרשאה לפעולה זו")
        return user
    return dep

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.environ.get("SECRET_KEY", "neocortex-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Default users — in production these should be in the DB
USERS = {
    "doctor": {
        "username": "doctor",
        "hashed_password": pwd_context.hash(os.environ.get("DOCTOR_PASSWORD", "doctor123")),
        "role": "doctor",
        "display_name": "רופא",
    },
    "secretary": {
        "username": "secretary",
        "hashed_password": pwd_context.hash(os.environ.get("SECRETARY_PASSWORD", "secretary123")),
        "role": "secretary",
        "display_name": "מזכירה",
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": username, "role": role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(neocortex_token: Optional[str] = Cookie(default=None)) -> dict:
    if not neocortex_token:
        raise HTTPException(status_code=401, detail="לא מחובר")
    try:
        payload = jwt.decode(neocortex_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or not role:
            raise HTTPException(status_code=401, detail="טוקן לא תקין")
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="טוקן פג תוקף — נא להתחבר מחדש")


def require_doctor(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "doctor":
        raise HTTPException(status_code=403, detail="גישה מותרת לרופאים בלבד")
    return user

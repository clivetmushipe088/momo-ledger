import secrets

import bcrypt
from fastapi import HTTPException, Request

from . import db

COOKIE_NAME = "session"


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes of a password
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def start_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.create_session(token, user_id)
    return token


def current_user(request: Request):
    """Used as Depends(current_user): gives the logged-in user, or stops with 401."""
    token = request.cookies.get(COOKIE_NAME)
    user = db.user_for_session(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in first.")
    return user

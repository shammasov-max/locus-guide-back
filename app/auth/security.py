import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

# Password hashing with Argon2id
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        ph.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return ph.check_needs_rehash(password_hash)


# Token hashing (for refresh tokens and reset tokens)
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


# JWT Access Token
def create_access_token(
    user_id: int,
    token_version: int,
    role: str = "user",
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "sub": str(user_id),
        "tv": token_version,  # token version for logout-all
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# Refresh Token
def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Returns: (raw_token, hashed_token, expires_at)
    """
    raw_token = generate_token()
    hashed_token = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return raw_token, hashed_token, expires_at


# Password Reset Token
def create_password_reset_token() -> tuple[str, str, datetime]:
    """
    Returns: (raw_token, hashed_token, expires_at)
    Password reset tokens expire in 1 hour.
    """
    raw_token = generate_token()
    hashed_token = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return raw_token, hashed_token, expires_at

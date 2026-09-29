import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


BACKEND_ROOT = Path(__file__).resolve().parent.parent
AUTH_DATABASE_PATH = BACKEND_ROOT / "data" / "tca_auth.db"
AUTH_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

PBKDF2_ITERATIONS = 310_000
TOKEN_TTL_SECONDS = 60 * 60 * 24
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    name: str
    created_at: datetime
    onboarding_completed: bool

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "onboarding_completed": self.onboarding_completed,
        }


def _auth_secret() -> bytes:
    secret = os.getenv("TCA_AUTH_SECRET", "")
    if not secret:
        # Development fallback only. Production deployment must set TCA_AUTH_SECRET.
        secret = "tca-v0.5-development-secret-change-me"
    return secret.encode("utf-8")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(AUTH_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_database() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                onboarding_completed INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "onboarding_completed" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN onboarding_completed INTEGER NOT NULL DEFAULT 0"
            )

        connection.commit()


def normalize_email(email: str) -> str:
    return " ".join(email.strip().split()).casefold()


def validate_signup(name: str, email: str, password: str) -> tuple[str, str, str]:
    clean_name = " ".join(name.strip().split())
    clean_email = normalize_email(email)

    if len(clean_name) < 2:
        raise ValueError("Name must be at least 2 characters.")

    if len(clean_name) > 120:
        raise ValueError("Name must be 120 characters or fewer.")

    if not EMAIL_PATTERN.fullmatch(clean_email):
        raise ValueError("Enter a valid email address.")

    if len(clean_email) > 320:
        raise ValueError("Email address is too long.")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    if len(password) > 200:
        raise ValueError("Password must be 200 characters or fewer.")

    return clean_name, clean_email, password


def _hash_password(password: str, salt: bytes) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(derived).decode("ascii")


def _verify_password(password: str, salt_b64: str, expected_hash: str) -> bool:
    try:
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
    except (ValueError, TypeError):
        return False

    actual_hash = _hash_password(password, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def create_user(name: str, email: str, password: str) -> AuthUser:
    clean_name, clean_email, clean_password = validate_signup(
        name,
        email,
        password,
    )

    initialize_auth_database()

    user_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(clean_password, salt)
    password_salt = base64.urlsafe_b64encode(salt).decode("ascii")

    try:
        with _connect() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id,
                    email,
                    name,
                    password_hash,
                    password_salt,
                    created_at,
                    onboarding_completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    clean_email,
                    clean_name,
                    password_hash,
                    password_salt,
                    created_at.isoformat(),
                    0,
                ),
            )
            connection.commit()
    except sqlite3.IntegrityError as error:
        raise ValueError("An account with that email already exists.") from error

    return AuthUser(
        id=user_id,
        email=clean_email,
        name=clean_name,
        created_at=created_at,
        onboarding_completed=False,
    )


def authenticate_user(email: str, password: str) -> AuthUser | None:
    initialize_auth_database()
    clean_email = normalize_email(email)

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, email, name, password_hash, password_salt, created_at, onboarding_completed
            FROM users
            WHERE email = ?
            """,
            (clean_email,),
        ).fetchone()

    if row is None:
        return None

    if not _verify_password(
        password,
        row["password_salt"],
        row["password_hash"],
    ):
        return None

    return _row_to_user(row)


def get_user(user_id: str) -> AuthUser | None:
    initialize_auth_database()

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, email, name, created_at, onboarding_completed
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_user(row)


def _row_to_user(row: sqlite3.Row) -> AuthUser:
    created_at = datetime.fromisoformat(row["created_at"])
    return AuthUser(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        created_at=created_at,
        onboarding_completed=bool(row["onboarding_completed"]),
    )


def update_user_profile(
    user_id: str,
    name: str,
    onboarding_completed: bool,
) -> AuthUser:
    clean_name = " ".join(name.strip().split())

    if len(clean_name) < 2:
        raise ValueError("Name must be at least 2 characters.")
    if len(clean_name) > 120:
        raise ValueError("Name must be 120 characters or fewer.")

    initialize_auth_database()

    with _connect() as connection:
        connection.execute(
            """
            UPDATE users
            SET name = ?, onboarding_completed = ?
            WHERE id = ?
            """,
            (clean_name, int(onboarding_completed), user_id),
        )
        connection.commit()

    user = get_user(user_id)
    if user is None:
        raise ValueError("Account no longer exists.")

    return user


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def create_access_token(user: AuthUser) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }

    header = {
        "alg": "HS256",
        "typ": "JWT",
    }

    encoded_header = _base64url(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    encoded_payload = _base64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        _auth_secret(),
        signing_input,
        hashlib.sha256,
    ).digest()

    return f"{encoded_header}.{encoded_payload}.{_base64url(signature)}"


def decode_access_token(token: str) -> AuthUser:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected_signature = hmac.new(
            _auth_secret(),
            signing_input,
            hashlib.sha256,
        ).digest()
        actual_signature = _base64url_decode(encoded_signature)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Invalid token signature.")

        header = json.loads(_base64url_decode(encoded_header).decode("utf-8"))
        payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))

        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise ValueError("Invalid token header.")

        expires_at = int(payload["exp"])
        if int(time.time()) >= expires_at:
            raise ValueError("Token has expired.")

        user_id = str(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return decode_access_token(credentials.credentials)

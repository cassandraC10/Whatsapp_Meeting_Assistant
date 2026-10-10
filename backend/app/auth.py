from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.cloud import cloud_database_connection, load_cloud_config
from backend.app.config import get_config

BACKEND_ROOT = Path(__file__).resolve().parent.parent

AUTH_DATABASE_PATH = BACKEND_ROOT / "data" / "tca_auth.db"

AUTH_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)



PBKDF2_ITERATIONS = 310_000

TOKEN_TTL_SECONDS = 60 * 60 * 24

CAPTURE_HANDOFF_TTL_SECONDS = 120

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





def _cloud_auth_enabled() -> bool:

    config = load_cloud_config()

    return config.enabled and config.database_configured





def _auth_secret() -> bytes:

    secret = get_config().auth_secret

    if not secret:

        if get_config().production:

            raise RuntimeError("TCA_AUTH_SECRET is required in production.")

        secret = "tca-v0.5-development-secret-change-me"

    return secret.encode("utf-8")





def _connect() -> sqlite3.Connection:

    connection = sqlite3.connect(AUTH_DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    return connection



@contextmanager
def _auth_connection():

    connection = _connect()

    try:

        with connection:

            yield connection

    finally:

        connection.close()





def initialize_auth_database() -> None:

    with _auth_connection() as connection:

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



        connection.execute(

            """

            CREATE TABLE IF NOT EXISTS capture_handoffs (

                code_hash TEXT PRIMARY KEY,

                user_id TEXT NOT NULL,

                created_at INTEGER NOT NULL,

                expires_at INTEGER NOT NULL,

                used_at INTEGER

            )

            """

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

    if len(password) < 12:

        raise ValueError("Password must be at least 12 characters.")

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





def _cloud_fetchone_as_dict(cursor):
    """Fetch one cloud database row as a dict, regardless of cursor row format."""
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    description = cursor.description
    if not description:
        raise RuntimeError("Cloud database cursor returned a row without column metadata.")
    return {column[0]: value for column, value in zip(description, row)}


def _cloud_row_to_user(row) -> AuthUser:

    created_at = row["created_at"]

    if isinstance(created_at, str):

        created_at = datetime.fromisoformat(created_at)

    if created_at.tzinfo is None:

        created_at = created_at.replace(tzinfo=timezone.utc)

    return AuthUser(

        id=str(row["id"]),

        email=str(row["email"]),

        name=str(row["name"]),

        created_at=created_at,

        onboarding_completed=bool(row["onboarding_completed"]),

    )





def _local_row_to_user(row: sqlite3.Row) -> AuthUser:

    created_at = datetime.fromisoformat(row["created_at"])

    return AuthUser(

        id=row["id"],

        email=row["email"],

        name=row["name"],

        created_at=created_at,

        onboarding_completed=bool(row["onboarding_completed"]),

    )





def create_user(name: str, email: str, password: str) -> AuthUser:

    clean_name, clean_email, clean_password = validate_signup(name, email, password)

    user_id = str(uuid4())

    created_at = datetime.now(timezone.utc)

    salt = secrets.token_bytes(16)

    password_hash = _hash_password(clean_password, salt)

    password_salt = base64.urlsafe_b64encode(salt).decode("ascii")



    if _cloud_auth_enabled():

        try:

            with cloud_database_connection() as connection:

                with connection.cursor() as cursor:

                    cursor.execute(

                        """

                        INSERT INTO tca_users (

                            id, email, name, password_hash, password_salt,

                            onboarding_completed, created_at, updated_at

                        ) VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)

                        """,

                        (

                            user_id,

                            clean_email,

                            clean_name,

                            password_hash,

                            password_salt,

                            created_at,

                            created_at,

                        ),

                    )

                connection.commit()

        except Exception as error:

            if "unique" in str(error).casefold() or "duplicate" in str(error).casefold():

                raise ValueError("An account with that email already exists.") from error

            raise



        return AuthUser(

            id=user_id,

            email=clean_email,

            name=clean_name,

            created_at=created_at,

            onboarding_completed=False,

        )



    initialize_auth_database()

    try:

        with _auth_connection() as connection:

            connection.execute(

                """

                INSERT INTO users (

                    id, email, name, password_hash, password_salt,

                    created_at, onboarding_completed

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



    return AuthUser(user_id, clean_email, clean_name, created_at, False)





def authenticate_user(email: str, password: str) -> AuthUser | None:

    clean_email = normalize_email(email)



    if _cloud_auth_enabled():

        with cloud_database_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(

                    """

                    SELECT id, email, name, password_hash, password_salt,

                           created_at, onboarding_completed

                    FROM tca_users

                    WHERE email = %s

                    """,

                    (clean_email,),

                )

                row = _cloud_fetchone_as_dict(cursor)



        if row is None or not row["password_hash"] or not row["password_salt"]:

            return None

        if not _verify_password(password, row["password_salt"], row["password_hash"]):

            return None

        return _cloud_row_to_user(row)



    initialize_auth_database()

    with _auth_connection() as connection:

        row = connection.execute(

            """

            SELECT id, email, name, password_hash, password_salt, created_at, onboarding_completed

            FROM users WHERE email = ?

            """,

            (clean_email,),

        ).fetchone()



    if row is None or not _verify_password(password, row["password_salt"], row["password_hash"]):

        return None

    return _local_row_to_user(row)





def get_user(user_id: str) -> AuthUser | None:

    if _cloud_auth_enabled():

        with cloud_database_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(

                    """

                    SELECT id, email, name, created_at, onboarding_completed

                    FROM tca_users WHERE id = %s

                    """,

                    (user_id,),

                )

                row = _cloud_fetchone_as_dict(cursor)

        return _cloud_row_to_user(row) if row else None



    initialize_auth_database()

    with _auth_connection() as connection:

        row = connection.execute(

            """

            SELECT id, email, name, created_at, onboarding_completed

            FROM users WHERE id = ?

            """,

            (user_id,),

        ).fetchone()

    return _local_row_to_user(row) if row else None





def update_user_profile(user_id: str, name: str, onboarding_completed: bool) -> AuthUser:

    clean_name = " ".join(name.strip().split())

    if len(clean_name) < 2:

        raise ValueError("Name must be at least 2 characters.")

    if len(clean_name) > 120:

        raise ValueError("Name must be 120 characters or fewer.")



    if _cloud_auth_enabled():

        with cloud_database_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(

                    """

                    UPDATE tca_users

                    SET name = %s, onboarding_completed = %s, updated_at = %s

                    WHERE id = %s

                    """,

                    (clean_name, onboarding_completed, datetime.now(timezone.utc), user_id),

                )

            connection.commit()

    else:

        initialize_auth_database()

        with _auth_connection() as connection:

            connection.execute(

                "UPDATE users SET name = ?, onboarding_completed = ? WHERE id = ?",

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





def _hash_capture_handoff(code: str) -> str:

    return hashlib.sha256(code.encode("utf-8")).hexdigest()





def create_capture_handoff(user: AuthUser) -> tuple[str, int]:

    now = int(time.time())

    expires_at = now + CAPTURE_HANDOFF_TTL_SECONDS

    code = secrets.token_urlsafe(32)

    code_hash = _hash_capture_handoff(code)



    if _cloud_auth_enabled():

        with cloud_database_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(

                    "DELETE FROM tca_capture_handoffs WHERE expires_at <= %s OR used_at IS NOT NULL",

                    (now,),

                )

                cursor.execute(

                    """

                    INSERT INTO tca_capture_handoffs

                    (code_hash, user_id, created_at, expires_at, used_at)

                    VALUES (%s, %s, %s, %s, NULL)

                    """,

                    (code_hash, user.id, now, expires_at),

                )

            connection.commit()

        return code, expires_at



    initialize_auth_database()

    with _auth_connection() as connection:

        connection.execute(

            "DELETE FROM capture_handoffs WHERE expires_at <= ? OR used_at IS NOT NULL",

            (now,),

        )

        connection.execute(

            "INSERT INTO capture_handoffs (code_hash, user_id, created_at, expires_at, used_at) VALUES (?, ?, ?, ?, NULL)",

            (code_hash, user.id, now, expires_at),

        )

        connection.commit()

    return code, expires_at





def exchange_capture_handoff(code: str) -> AuthUser | None:

    clean_code = code.strip()

    if not clean_code or len(clean_code) > 256:

        return None



    now = int(time.time())

    code_hash = _hash_capture_handoff(clean_code)



    if _cloud_auth_enabled():

        with cloud_database_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute("SELECT user_id, expires_at, used_at FROM tca_capture_handoffs WHERE code_hash = %s FOR UPDATE", (code_hash,))

                row = _cloud_fetchone_as_dict(cursor)

                if row is None or row["used_at"] is not None or int(row["expires_at"]) <= now:

                    connection.rollback()

                    return None

                cursor.execute("UPDATE tca_capture_handoffs SET used_at = %s WHERE code_hash = %s", (now, code_hash))

            connection.commit()

        return get_user(str(row["user_id"]))



    initialize_auth_database()

    with _auth_connection() as connection:

        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(

            "SELECT user_id, expires_at, used_at FROM capture_handoffs WHERE code_hash = ?",

            (code_hash,),

        ).fetchone()

        if row is None or row["used_at"] is not None or int(row["expires_at"]) <= now:

            connection.rollback()

            return None

        connection.execute("UPDATE capture_handoffs SET used_at = ? WHERE code_hash = ?", (now, code_hash))

        connection.commit()

    return get_user(str(row["user_id"]))





def migrate_local_auth_users_to_cloud() -> int:

    """Copy local development/beta auth credentials into cloud auth once."""

    if not _cloud_auth_enabled():

        return 0



    initialize_auth_database()

    with _auth_connection() as local_connection:

        rows = local_connection.execute(

            "SELECT id, email, name, password_hash, password_salt, created_at, onboarding_completed FROM users"

        ).fetchall()



    migrated = 0

    with cloud_database_connection() as connection:

        with connection.cursor() as cursor:

            for row in rows:

                cursor.execute(

                    """

                    INSERT INTO tca_users (

                        id, email, name, password_hash, password_salt,

                        onboarding_completed, created_at, updated_at

                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)

                    ON CONFLICT (id) DO UPDATE SET

                        email = EXCLUDED.email,

                        name = EXCLUDED.name,

                        password_hash = COALESCE(EXCLUDED.password_hash, tca_users.password_hash),

                        password_salt = COALESCE(EXCLUDED.password_salt, tca_users.password_salt),

                        onboarding_completed = EXCLUDED.onboarding_completed,

                        updated_at = EXCLUDED.updated_at

                    """,

                    (

                        row["id"],

                        row["email"],

                        row["name"],

                        row["password_hash"],

                        row["password_salt"],

                        bool(row["onboarding_completed"]),

                        datetime.fromisoformat(row["created_at"]),

                        datetime.now(timezone.utc),

                    ),

                )

                migrated += 1

        connection.commit()

    return migrated





def create_access_token(user: AuthUser) -> str:

    now = int(time.time())

    payload = {"sub": user.id, "email": user.email, "name": user.name, "iat": now, "exp": now + TOKEN_TTL_SECONDS}

    header = {"alg": "HS256", "typ": "JWT"}

    encoded_header = _base64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))

    encoded_payload = _base64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")

    signature = hmac.new(_auth_secret(), signing_input, hashlib.sha256).digest()

    return f"{encoded_header}.{encoded_payload}.{_base64url(signature)}"





def decode_access_token(token: str) -> AuthUser:

    try:

        encoded_header, encoded_payload, encoded_signature = token.split(".")

        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")

        expected_signature = hmac.new(_auth_secret(), signing_input, hashlib.sha256).digest()

        actual_signature = _base64url_decode(encoded_signature)

        if not hmac.compare_digest(expected_signature, actual_signature):

            raise ValueError("Invalid token signature.")

        header = json.loads(_base64url_decode(encoded_header).decode("utf-8"))

        payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))

        if header.get("alg") != "HS256" or header.get("typ") != "JWT":

            raise ValueError("Invalid token header.")

        if int(time.time()) >= int(payload["exp"]):

            raise ValueError("Token has expired.")

        user_id = str(payload["sub"])

    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication token.", headers={"WWW-Authenticate": "Bearer"})



    user = get_user(user_id)

    if user is None:

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.", headers={"WWW-Authenticate": "Bearer"})

    return user





def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> AuthUser:

    if credentials is None or credentials.scheme.casefold() != "bearer":

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})

    return decode_access_token(credentials.credentials)

import asyncio
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"

# bcrypt 演算法上限 72 bytes;bcrypt>=4.1 超長直接 raise → 統一先截斷(舊版 bcrypt 行為)
_BCRYPT_MAX_BYTES = 72


def _password_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    # passlib 1.7.4 與鎖定的 bcrypt 5.0.0 不相容,改用 bcrypt 直呼(見 fixed.md §3)
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("ascii"))
    except ValueError:
        # hash 格式不合法(如非 bcrypt hash)一律視為驗證失敗
        return False


async def hash_password_async(plain: str) -> str:
    return await asyncio.to_thread(hash_password, plain)


async def verify_password_async(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(verify_password, plain, hashed)


def create_access_token(
    *, subject: str, role: str, secret_key: str, expires_minutes: int
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict[str, object]:
    """解析 JWT;無效 / 過期時拋 jwt.PyJWTError,由呼叫端轉 401。"""
    payload: dict[str, object] = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    return payload

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import base64
import hashlib
import hmac
import secrets

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390_000
SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """使用随机盐和 PBKDF2 生成可入库的密码哈希。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return ".".join(
        [
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            _b64encode(salt),
            _b64encode(digest),
        ],
    )


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码是否匹配已保存的密码哈希。"""
    try:
        algorithm, iterations_text, salt_text, expected_text = password_hash.split(".", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = _b64decode(salt_text)
        expected = _b64decode(expected_text)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> str:
    """生成用于 Cookie 会话的随机令牌。"""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """对会话令牌做 SHA-256 哈希，避免明文令牌入库。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(days: int) -> datetime:
    """根据会话有效天数计算 UTC 过期时间。"""
    return datetime.now(UTC) + timedelta(days=days)


def _b64encode(value: bytes) -> str:
    """把二进制值编码为无填充的 URL 安全 Base64 文本。"""
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    """还原无填充的 URL 安全 Base64 文本。"""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def encrypt_token(token: str) -> str:
    """加密访问令牌，返回可安全写入数据库的密文。"""
    return _get_fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """解密数据库中的访问令牌密文，供抓取客户端临时使用。"""
    return _get_fernet().decrypt(encrypted_token.encode("utf-8")).decode("utf-8")


def _get_fernet() -> Fernet:
    """基于当前配置生成 Fernet 加解密实例。"""
    return Fernet(_resolve_key())


def _resolve_key() -> bytes:
    """解析令牌加密密钥；本地开发缺省使用稳定派生密钥。"""
    if settings.token_encryption_key:
        return settings.token_encryption_key.encode("utf-8")

    digest = hashlib.sha256(b"github-sentinel-local-development-key").digest()
    return base64.urlsafe_b64encode(digest)

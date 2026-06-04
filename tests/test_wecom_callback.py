import base64
import hashlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.core.config import settings


def _sign(token: str, timestamp: str, nonce: str, encrypted: str) -> str:
    raw = "".join(sorted([token, timestamp, nonce, encrypted]))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _encrypt_wecom_message(encoding_aes_key: str, message: str, corp_id: str) -> str:
    aes_key = base64.b64decode(f"{encoding_aes_key}=")
    random_prefix = b"0" * 16
    message_bytes = message.encode("utf-8")
    corp_id_bytes = corp_id.encode("utf-8")
    payload = (
        random_prefix
        + len(message_bytes).to_bytes(4, byteorder="big")
        + message_bytes
        + corp_id_bytes
    )
    padding_size = 32 - (len(payload) % 32)
    padded = payload + bytes([padding_size]) * padding_size
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16]))
    encryptor = cipher.encryptor()
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode("utf-8")


async def test_wecom_callback_verifies_url(client, monkeypatch):
    token = "callback-token"
    encoding_aes_key = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
    corp_id = "corp-1"
    echostr = _encrypt_wecom_message(encoding_aes_key, "verified", corp_id)
    timestamp = "1710000000"
    nonce = "nonce-1"

    monkeypatch.setattr(settings, "notification_wecom_callback_token", token)
    monkeypatch.setattr(settings, "notification_wecom_callback_encoding_aes_key", encoding_aes_key)
    monkeypatch.setattr(settings, "notification_wecom_corp_id", corp_id)

    response = await client.get(
        "/wecom/callback",
        params={
            "msg_signature": _sign(token, timestamp, nonce, echostr),
            "timestamp": timestamp,
            "nonce": nonce,
            "echostr": echostr,
        },
    )

    assert response.status_code == 200
    assert response.text == "verified"
    assert response.headers["content-type"].startswith("text/plain")


async def test_wecom_callback_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "notification_wecom_callback_token", "callback-token")
    monkeypatch.setattr(
        settings,
        "notification_wecom_callback_encoding_aes_key",
        "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",
    )
    monkeypatch.setattr(settings, "notification_wecom_corp_id", "corp-1")

    response = await client.get(
        "/wecom/callback",
        params={
            "msg_signature": "invalid",
            "timestamp": "1710000000",
            "nonce": "nonce-1",
            "echostr": "encrypted",
        },
    )

    assert response.status_code == 400

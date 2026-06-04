import base64
import binascii
import hashlib
import hmac
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class WeComCallbackError(ValueError):
    """企业微信回调验证失败。"""


def verify_wecom_url(
    *,
    token: str | None,
    encoding_aes_key: str | None,
    corp_id: str | None,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> str:
    """校验企业微信 URL 验证请求并返回解密后的 echostr 明文。"""
    if not token or not encoding_aes_key or not corp_id:
        raise WeComCallbackError("企业微信回调配置不完整")
    if not hmac.compare_digest(_signature(token, timestamp, nonce, echostr), msg_signature):
        raise WeComCallbackError("企业微信回调签名无效")

    return _decrypt_message(encoding_aes_key, echostr, corp_id)


def _signature(token: str, timestamp: str, nonce: str, encrypted: str) -> str:
    raw = "".join(sorted([token, timestamp, nonce, encrypted]))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _decrypt_message(encoding_aes_key: str, encrypted: str, corp_id: str) -> str:
    try:
        aes_key = base64.b64decode(f"{encoding_aes_key}=", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise WeComCallbackError("企业微信 EncodingAESKey 无效") from exc
    if len(aes_key) != 32:
        raise WeComCallbackError("企业微信 EncodingAESKey 长度无效")

    try:
        ciphertext = base64.b64decode(encrypted, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise WeComCallbackError("企业微信 echostr 无效") from exc

    try:
        decryptor = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16])).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
    except ValueError as exc:
        raise WeComCallbackError("企业微信 echostr 解密失败") from exc
    plaintext = _remove_pkcs7_padding(padded)
    if len(plaintext) < 20:
        raise WeComCallbackError("企业微信 echostr 内容无效")

    message_length = struct.unpack("!I", plaintext[16:20])[0]
    message_start = 20
    message_end = message_start + message_length
    message = plaintext[message_start:message_end]
    try:
        received_corp_id = plaintext[message_end:].decode("utf-8")
        decoded_message = message.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WeComCallbackError("企业微信 echostr 文本编码无效") from exc
    if not hmac.compare_digest(received_corp_id, corp_id):
        raise WeComCallbackError("企业微信 CorpId 不匹配")
    return decoded_message


def _remove_pkcs7_padding(payload: bytes) -> bytes:
    if not payload:
        raise WeComCallbackError("企业微信 echostr 解密内容为空")
    padding_size = payload[-1]
    if padding_size < 1 or padding_size > 32:
        raise WeComCallbackError("企业微信 echostr 填充无效")
    if payload[-padding_size:] != bytes([padding_size]) * padding_size:
        raise WeComCallbackError("企业微信 echostr 填充不一致")
    return payload[:-padding_size]

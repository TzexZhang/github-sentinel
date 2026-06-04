from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.core.errors import ApiError
from app.services.wecom_callback import WeComCallbackError, verify_wecom_url

router = APIRouter(prefix="/wecom", tags=["wecom"])


@router.get("/callback", response_class=PlainTextResponse)
async def verify_wecom_callback_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
) -> str:
    """处理企业微信保存接收消息服务器 URL 时的 GET 验证请求。"""
    try:
        return verify_wecom_url(
            token=settings.notification_wecom_callback_token,
            encoding_aes_key=settings.notification_wecom_callback_encoding_aes_key,
            corp_id=settings.notification_wecom_corp_id,
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echostr=echostr,
        )
    except WeComCallbackError as exc:
        raise ApiError(400, "wecom_callback_verification_failed", str(exc)) from exc

"""报告相关路由。"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.repositories.reports import batch_delete_reports, list_reports
from app.schemas.reports import ReportBatchDeleteRequest, ReportBatchDeleteResult, ReportRead
from app.schemas.responses import ApiResponse, success_response
from app.services.time_utils import report_now

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ApiResponse)
async def list_reports_endpoint(
    session: DbSession,
    current_user: CurrentUser,
    within_seconds: int | None = Query(default=None, ge=1, le=31_536_000),
) -> dict[str, object]:
    """查询已生成报告，可按生成时间范围过滤。"""
    generated_since = _resolve_generated_since(within_seconds)
    reports = await list_reports(
        session,
        user_id=current_user.user.id,
        generated_since=generated_since,
    )
    data = [ReportRead.model_validate(report).model_dump() for report in reports]
    return success_response(data)


@router.post("/batch-delete", response_model=ApiResponse)
async def batch_delete_reports_endpoint(
    payload: ReportBatchDeleteRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, object]:
    deleted_count, not_found_ids = await batch_delete_reports(
        session,
        payload.report_ids,
        current_user.user.id,
    )
    result = ReportBatchDeleteResult(
        requested_count=len(payload.report_ids),
        deleted_count=deleted_count,
        not_found_ids=not_found_ids,
    )
    return success_response(result.model_dump())


def _resolve_generated_since(within_seconds: int | None) -> datetime | None:
    """把最近秒数转换为报告生成时间下限。"""
    if within_seconds is None:
        return None
    return report_now() - timedelta(seconds=within_seconds)

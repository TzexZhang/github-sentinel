from datetime import date, datetime, timezone

from sqlalchemy import select

from app.db.models import NotificationJob, Report, Subscription


async def test_batch_delete_reports_physically_removes_current_user_reports(client, session_factory):
    async with session_factory() as session:
        subscription = Subscription(
            user_id=1,
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=60,
        )
        session.add(subscription)
        await session.flush()
        report = Report(
            subscription_id=subscription.id,
            name="acme_sentinel_2026-06-05",
            content_markdown="# report",
            generated_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
            period_start_date=date(2026, 6, 5),
            period_end_date=date(2026, 6, 5),
        )
        session.add(report)
        await session.flush()
        session.add(
            NotificationJob(
                subscription_id=subscription.id,
                report_id=report.id,
                notification_channel_id=1,
                subject=report.name,
                dedupe_key="report-1:channel-1",
            ),
        )
        await session.commit()
        report_id = report.id

    response = await client.post("/api/reports/batch-delete", json={"report_ids": [report_id, 404]})

    assert response.status_code == 200
    assert response.json()["data"] == {
        "requested_count": 2,
        "deleted_count": 1,
        "not_found_ids": [404],
    }
    async with session_factory() as session:
        reports = list((await session.execute(select(Report))).scalars().all())
        jobs = list((await session.execute(select(NotificationJob))).scalars().all())
    assert reports == []
    assert jobs == []


async def test_batch_delete_reports_does_not_delete_another_users_report(client, session_factory):
    async with session_factory() as session:
        other_subscription = Subscription(
            user_id=2,
            platform="github",
            owner="acme",
            repo="private",
            repository_url="https://github.com/acme/private",
            interval_seconds=60,
        )
        session.add(other_subscription)
        await session.flush()
        report = Report(
            subscription_id=other_subscription.id,
            name="other",
            content_markdown="# other",
            generated_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
        )
        session.add(report)
        await session.commit()
        report_id = report.id

    response = await client.post("/api/reports/batch-delete", json={"report_ids": [report_id]})

    assert response.status_code == 200
    assert response.json()["data"] == {
        "requested_count": 1,
        "deleted_count": 0,
        "not_found_ids": [report_id],
    }
    async with session_factory() as session:
        remaining = list((await session.execute(select(Report))).scalars().all())
    assert len(remaining) == 1

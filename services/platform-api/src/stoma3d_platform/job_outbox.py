"""Retry durable queued jobs without relying on a client to repeat its request."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import or_, select

from .job_queue import QueueUnavailable
from .models import Job, JobStatus, utc_now


async def dispatch_job_outbox_once(app) -> int:
    """Publish new or stale queued envelopes using at-least-once delivery."""

    settings = app.state.settings
    cutoff = utc_now() - timedelta(seconds=settings.queue_redelivery_after_seconds)
    async with app.state.database.sessions() as session:
        jobs = list(
            await session.scalars(
                select(Job)
                .where(
                    Job.status == JobStatus.QUEUED,
                    Job.result_outcome.is_(None),
                    Job.cancellation_requested_at.is_(None),
                    Job.queue_envelope.is_not(None),
                    or_(
                        Job.queue_published_at.is_(None),
                        Job.queue_published_at < cutoff,
                    ),
                )
                .order_by(Job.created_at, Job.id)
                .limit(settings.queue_dispatch_batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        published = 0
        for job in jobs:
            try:
                message_id = await app.state.job_queue.publish(job.queue_envelope)
            except QueueUnavailable:
                await session.rollback()
                return published
            job.queue_message_id = message_id
            job.queue_published_at = utc_now()
            published += 1
        await session.commit()
        return published


async def job_outbox_loop(app) -> None:
    interval = app.state.settings.queue_dispatch_interval_seconds
    while True:
        await dispatch_job_outbox_once(app)
        await asyncio.sleep(interval)

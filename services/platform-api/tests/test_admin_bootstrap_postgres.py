from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import func, select

from oralsight_platform.admin_bootstrap import (
    FIRST_ADMIN_CONFIRMATION_PHRASE,
    AdminBootstrapError,
    bootstrap_first_admin,
)
from oralsight_platform.config import RuntimeEnvironment, Settings
from oralsight_platform.database import Database
from oralsight_platform.models import AuditEvent, User, UserRole


async def test_postgres_advisory_lock_allows_only_one_first_admin() -> None:
    database_url = os.environ.get("ORALSIGHT_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("A dedicated PostgreSQL test URL was not provided.")

    settings = Settings(
        _env_file=None,
        environment=RuntimeEnvironment.DEVELOPMENT,
        database_url=database_url,
        create_schema_on_start=False,
        auth_mode="local_test",
        local_test_signing_secret="postgres-bootstrap-test-signing-secret-32-bytes",
        share_secret_derivation_key="postgres-bootstrap-test-share-secret-32-bytes",
        worker_service_hmac_secret="postgres-bootstrap-test-worker-secret-32-bytes",
    )
    database = Database(settings)
    try:
        await database.drop_schema()
        await database.create_schema()
        subjects = ("auth0|postgres-race-a", "auth0|postgres-race-b")
        async with database.sessions() as session:
            session.add_all([User(oidc_subject=value) for value in subjects])
            await session.commit()

        async def attempt(subject: str):
            async with database.sessions() as session:
                async with session.begin():
                    return await bootstrap_first_admin(
                        session,
                        oidc_subject=subject,
                        confirmation=FIRST_ADMIN_CONFIRMATION_PHRASE,
                    )

        results = await asyncio.gather(
            *(attempt(subject) for subject in subjects),
            return_exceptions=True,
        )
        successes = [value for value in results if not isinstance(value, Exception)]
        failures = [
            value for value in results if isinstance(value, AdminBootstrapError)
        ]
        assert len(successes) == 1
        assert len(failures) == 1
        assert failures[0].code == "bootstrap_sealed"

        async with database.sessions() as session:
            assert (
                await session.scalar(
                    select(func.count(User.id)).where(User.role == UserRole.ADMIN)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count(AuditEvent.id)).where(
                        AuditEvent.event_type == "admin.bootstrap_completed"
                    )
                )
                == 1
            )
    finally:
        await database.drop_schema()
        await database.dispose()

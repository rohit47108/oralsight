from __future__ import annotations

import asyncio
import importlib.util
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from oralsight_platform.deletion_tombstones import (
    LEGACY_SHARE_KEY_VERSION,
    legacy_deletion_receipt_fingerprint,
)
from oralsight_platform.models import (
    DeletedSubjectTombstone,
    DeletionRequest,
    DeletionStatus,
    User,
    UserStatus,
    new_id,
    utc_now,
)
from oralsight_platform.retention import sweep_retention


async def _accept_deletion(client, auth_headers, *, suffix: str = "base"):
    account = await client.get("/v2/me", headers=auth_headers())
    assert account.status_code == 200
    response = await client.post(
        "/v2/me/deletion-requests",
        headers={
            **auth_headers(),
            "Idempotency-Key": f"durable-tombstone-{suffix}-0001",
        },
        json={"confirmation": "DELETE"},
    )
    assert response.status_code == 202, response.text
    return account.json(), response.json()


async def _finish_deletion_in_database(app, account_id: str, request_id: str) -> None:
    async with app.state.database.sessions() as session:
        user = await session.get(User, account_id)
        deletion = await session.get(DeletionRequest, request_id)
        assert user is not None and deletion is not None
        now = utc_now()
        user.oidc_subject = f"deleted:{new_id()}"
        user.status = UserStatus.SUSPENDED
        deletion.status = DeletionStatus.COMPLETED
        deletion.completed_at = now
        deletion.retention_expires_at = now - timedelta(seconds=1)
        await session.commit()


async def test_deletion_acceptance_creates_durable_tombstone_before_anonymization(
    client, app, auth_headers
) -> None:
    account, deletion = await _accept_deletion(client, auth_headers)

    async with app.state.database.sessions() as session:
        user = await session.get(User, account["id"])
        tombstones = list(await session.scalars(select(DeletedSubjectTombstone)))
        assert user is not None
        assert user.oidc_subject == "auth0|patient-1"
        assert len(tombstones) == 1
        assert tombstones[0].fingerprint_key_version != LEGACY_SHARE_KEY_VERSION
        assert tombstones[0].first_deleted_at <= tombstones[0].last_deleted_at
        assert deletion["requestId"]


async def test_deleted_subject_stays_blocked_after_receipt_retention_sweep(
    client, app, auth_headers
) -> None:
    account, deletion = await _accept_deletion(client, auth_headers, suffix="expiry")
    await _finish_deletion_in_database(app, account["id"], deletion["requestId"])

    await sweep_retention(app)

    blocked = await client.get("/v2/me", headers=auth_headers())
    assert blocked.status_code == 410
    assert blocked.json()["error"]["code"] == "account_deleted_recreation_required"
    async with app.state.database.sessions() as session:
        receipt = await session.get(DeletionRequest, deletion["requestId"])
        assert receipt is not None and receipt.subject_fingerprint is None
        assert await session.scalar(select(func.count(DeletedSubjectTombstone.id))) == 1
        assert await session.scalar(select(func.count(User.id))) == 1


async def test_explicit_recreation_is_confirmed_idempotent_and_empty(
    client, app, auth_headers
) -> None:
    account, deletion = await _accept_deletion(client, auth_headers, suffix="recreate")
    await _finish_deletion_in_database(app, account["id"], deletion["requestId"])

    wrong = await client.post(
        "/v2/account-recreations",
        headers=auth_headers(),
        json={"confirmation": "RECREATE"},
    )
    assert wrong.status_code == 422

    body = {"confirmation": "RECREATE_AND_ALLOW_LOCAL_RESYNC"}
    first = await client.post(
        "/v2/account-recreations", headers=auth_headers(), json=body
    )
    replay = await client.post(
        "/v2/account-recreations", headers=auth_headers(), json=body
    )
    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json() == replay.json()
    assert first.json()["recreatedAfterDeletion"] is True
    assert first.json()["account"]["id"] != account["id"]
    assert first.json()["account"]["deletionPending"] is False

    async with app.state.database.sessions() as session:
        assert await session.scalar(select(func.count(User.id))) == 2
        assert await session.scalar(select(func.count(DeletedSubjectTombstone.id))) == 1
        new_user = await session.get(User, first.json()["account"]["id"])
        assert new_user is not None
        assert new_user.devices == []
        assert new_user.consents == []
        assert new_user.scan_sessions == []


async def test_concurrent_recreation_creates_exactly_one_new_account(
    client, app, auth_headers
) -> None:
    account, deletion = await _accept_deletion(client, auth_headers, suffix="race")
    await _finish_deletion_in_database(app, account["id"], deletion["requestId"])
    body = {"confirmation": "RECREATE_AND_ALLOW_LOCAL_RESYNC"}

    first, second = await asyncio.gather(
        client.post("/v2/account-recreations", headers=auth_headers(), json=body),
        client.post("/v2/account-recreations", headers=auth_headers(), json=body),
    )

    assert {first.status_code, second.status_code} == {200}
    assert first.json()["account"]["id"] == second.json()["account"]["id"]
    async with app.state.database.sessions() as session:
        active = await session.scalar(
            select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
        )
        assert active == 1


async def test_recreation_is_subject_scoped_and_not_an_enumeration_endpoint(
    client, app, auth_headers
) -> None:
    account, deletion = await _accept_deletion(client, auth_headers, suffix="scope")
    await _finish_deletion_in_database(app, account["id"], deletion["requestId"])

    unrelated = await client.post(
        "/v2/account-recreations",
        headers=auth_headers("auth0|another-person"),
        json={"confirmation": "RECREATE_AND_ALLOW_LOCAL_RESYNC"},
    )
    assert unrelated.status_code == 409
    assert unrelated.json()["error"]["code"] == "recreation_not_required"

    still_blocked = await client.get("/v2/me", headers=auth_headers())
    assert still_blocked.status_code == 410


async def test_legacy_tombstone_blocks_and_missing_key_version_fails_closed(
    client, app, settings, auth_headers
) -> None:
    subject = "auth0|legacy-deleted"
    async with app.state.database.sessions() as session:
        now = utc_now()
        session.add(
            DeletedSubjectTombstone(
                subject_fingerprint=legacy_deletion_receipt_fingerprint(
                    settings, subject
                ),
                fingerprint_key_version=LEGACY_SHARE_KEY_VERSION,
                first_deleted_at=now,
                last_deleted_at=now,
            )
        )
        await session.commit()

    legacy = await client.get("/v2/me", headers=auth_headers(subject))
    assert legacy.status_code == 410

    async with app.state.database.sessions() as session:
        now = utc_now()
        session.add(
            DeletedSubjectTombstone(
                subject_fingerprint="f" * 64,
                fingerprint_key_version="missing-key-v9",
                first_deleted_at=now,
                last_deleted_at=now,
            )
        )
        await session.commit()

    unavailable = await client.get("/v2/me", headers=auth_headers("auth0|new-person"))
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "deletion_tombstone_key_unavailable"


def test_migration_backfills_all_legacy_fingerprints_without_receipt_expiry_filter() -> (
    None
):
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260814_0011_durable_deleted_subject_tombstones.py"
    )
    source = path.read_text(encoding="utf-8")
    assert "deleted_subject_tombstones" in source
    assert "subject_fingerprint IS NOT NULL" in source
    assert "retention_expires_at" not in source
    assert "legacy-share-v1" in source


def test_tombstone_migration_sql_binds_legacy_values(monkeypatch) -> None:
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260814_0011_durable_deleted_subject_tombstones.py"
    )
    spec = importlib.util.spec_from_file_location("durable_tombstone_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    statements = []
    monkeypatch.setattr(migration.op, "create_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    assert len(statements) == 1
    assert statements[0].compile().params == {
        "legacy_suffix": ":legacy-share-v1",
        "legacy_key_version": "legacy-share-v1",
    }

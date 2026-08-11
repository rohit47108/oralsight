from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from oralsight_platform.models import EntityTombstone, SyncChange, SyncEntityState


def _headers(auth_headers, key: str, subject: str = "auth0|sync-patient"):
    return {**auth_headers(subject), "Idempotency-Key": key}


async def _device(client, auth_headers, subject: str = "auth0|sync-patient") -> str:
    response = await client.post(
        "/v2/devices",
        headers=_headers(auth_headers, "sync-device-register-001", subject),
        json={
            "installationId": "installation-identifier-0001",
            "platform": "ios",
            "displayName": "Test phone",
            "publicKey": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["deviceId"]


def _operation(
    device_id: str,
    *,
    operation_id: str,
    operation_key: str,
    operation: str,
    version: int,
    payload: str | None,
):
    return {
        "contractVersion": "2.0.0",
        "operationId": operation_id,
        "idempotencyKey": operation_key,
        "deviceId": device_id,
        "entityType": "capture_set",
        "entityId": "offline-capture-set-001",
        "version": version,
        "sequence": version,
        "occurredAt": datetime.now(UTC).isoformat(),
        "operation": operation,
        "encryptedPayload": payload,
        "tombstone": operation == "delete",
    }


async def test_sync_pull_push_is_idempotent_and_tombstone_wins(
    client, app, auth_headers
) -> None:
    device_id = await _device(client, auth_headers)
    upsert = _operation(
        device_id,
        operation_id="operation-upsert-0001",
        operation_key="operation-key-upsert-0001",
        operation="upsert",
        version=1,
        payload="encrypted-payload-v1",
    )
    headers = _headers(auth_headers, "sync-push-request-upsert-01")
    pushed = await client.post(
        "/v2/sync/push", headers=headers, json={"operations": [upsert]}
    )
    replay = await client.post(
        "/v2/sync/push", headers=headers, json={"operations": [upsert]}
    )
    assert pushed.status_code == replay.status_code == 200
    assert pushed.json() == replay.json()
    assert pushed.json()["results"][0]["status"] == "applied"

    pulled = await client.get(
        f"/v2/sync/pull?cursor={pushed.json()['cursor']['cursor']}&limit=10",
        headers=auth_headers("auth0|sync-patient"),
    )
    assert pulled.status_code == 200, pulled.text
    assert len(pulled.json()["operations"]) == 1
    assert pulled.json()["operations"][0]["encryptedPayload"] == "encrypted-payload-v1"
    next_pull = await client.get(
        f"/v2/sync/pull?cursor={pulled.json()['cursor']['cursor']}&limit=10",
        headers=auth_headers("auth0|sync-patient"),
    )
    assert next_pull.json()["operations"] == []

    duplicate = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-push-duplicate-batch-1"),
        json={"operations": [upsert]},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["results"][0]["status"] == "duplicate"

    stale = _operation(
        device_id,
        operation_id="operation-stale-0004",
        operation_key="operation-key-stale-0004",
        operation="upsert",
        version=1,
        payload="encrypted-stale-payload",
    )
    stale_result = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-push-stale-request-04"),
        json={"operations": [stale]},
    )
    assert stale_result.json()["results"][0]["status"] == "stale_ignored"

    newer = _operation(
        device_id,
        operation_id="operation-newer-0005",
        operation_key="operation-key-newer-0005",
        operation="upsert",
        version=2,
        payload="encrypted-newer-payload",
    )
    newer_result = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-push-newer-request-05"),
        json={"operations": [newer]},
    )
    assert newer_result.json()["results"][0]["status"] == "applied"

    delete = _operation(
        device_id,
        operation_id="operation-delete-0002",
        operation_key="operation-key-delete-0002",
        operation="delete",
        version=2,
        payload=None,
    )
    deleted = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-push-request-delete-02"),
        json={"operations": [delete]},
    )
    assert deleted.status_code == 200
    assert deleted.json()["results"][0]["status"] == "applied"

    resurrection = _operation(
        device_id,
        operation_id="operation-resurrect-0003",
        operation_key="operation-key-resurrect-0003",
        operation="upsert",
        version=999,
        payload="encrypted-payload-must-not-win",
    )
    blocked = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-push-resurrection-003"),
        json={"operations": [resurrection]},
    )
    assert blocked.status_code == 200
    assert blocked.json()["results"][0]["status"] == "tombstone_wins"

    async with app.state.database.sessions() as session:
        assert await session.scalar(select(func.count(EntityTombstone.id))) == 1
        assert await session.scalar(select(func.count(SyncEntityState.id))) == 0
        assert await session.scalar(select(func.count(SyncChange.server_sequence))) == 5

    conflict_operation = dict(upsert)
    conflict_operation["idempotencyKey"] = "different-key-for-same-operation"
    conflict_operation["encryptedPayload"] = "different-encrypted-payload"
    conflict = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-conflicting-operation-01"),
        json={"operations": [conflict_operation]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "sync_operation_conflict"


async def test_sync_rejects_cross_account_device_cursor_and_malformed_delete(
    client, auth_headers
) -> None:
    device_id = await _device(client, auth_headers)
    operation = _operation(
        device_id,
        operation_id="operation-owner-0001",
        operation_key="operation-owner-key-0001",
        operation="upsert",
        version=1,
        payload="encrypted-owner-payload",
    )
    pushed = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-owner-push-request-01"),
        json={"operations": [operation]},
    )
    cursor = pushed.json()["cursor"]["cursor"]
    cursor_denied = await client.get(
        f"/v2/sync/pull?cursor={cursor}",
        headers=auth_headers("auth0|other-sync-account"),
    )
    assert cursor_denied.status_code == 400
    assert cursor_denied.json()["error"]["code"] == "invalid_sync_cursor"

    other_operation = _operation(
        device_id,
        operation_id="operation-other-0002",
        operation_key="operation-other-key-0002",
        operation="upsert",
        version=2,
        payload="encrypted-other-payload",
    )
    device_denied = await client.post(
        "/v2/sync/push",
        headers=_headers(
            auth_headers, "sync-other-device-request-01", "auth0|other-sync-account"
        ),
        json={"operations": [other_operation]},
    )
    assert device_denied.status_code == 404

    malformed = _operation(
        device_id,
        operation_id="operation-malformed-0003",
        operation_key="operation-malformed-key-0003",
        operation="delete",
        version=3,
        payload=None,
    )
    malformed["encryptedPayload"] = "delete-must-not-have-payload"
    invalid = await client.post(
        "/v2/sync/push",
        headers=_headers(auth_headers, "sync-malformed-request-001"),
        json={"operations": [malformed]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_request"
    assert "delete-must-not-have-payload" not in invalid.text

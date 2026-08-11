from __future__ import annotations

from sqlalchemy import Enum
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from oralsight_platform.database import Base
from oralsight_platform.models import User, UserRole


def test_initial_metadata_contains_every_required_product_table() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "devices",
        "consent_records",
        "scan_sessions",
        "capture_assets",
        "jobs",
        "idempotency_records",
        "audit_events",
        "deletion_requests",
        "capture_sets",
        "capture_views",
        "analysis_runs",
        "candidate_observations",
        "match_proposals",
        "match_decisions",
        "lesion_records",
        "lesion_observation_links",
        "report_artifacts",
        "sync_entity_states",
        "entity_tombstones",
        "sync_changes",
        "sync_cursors",
        "clinician_verifications",
        "clinician_access_grants",
        "access_grant_resources",
        "share_links",
        "share_link_resources",
        "share_exchange_tokens",
        "clinician_reviews",
        "review_annotations",
        "access_events",
        "generated_artifacts",
        "service_request_nonces",
        "analytics_events",
        "data_export_artifacts",
    }


def test_database_enums_store_public_values() -> None:
    role_type = User.__table__.c.role.type
    assert isinstance(role_type, Enum)
    assert role_type.enums == [role.value for role in UserRole]


def test_every_table_compiles_for_postgresql() -> None:
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f"CREATE TABLE {table.name}" in ddl

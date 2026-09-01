"""Persistent, provenance-checked analysis runs and candidate observations."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import Actor, get_current_actor, get_session
from ..errors import ServiceError
from ..idempotency import (
    commit_idempotent,
    find_replay,
    request_sha256,
    validate_idempotency_key,
)
from ..models import (
    AnalysisRun,
    CalibrationStatus,
    CandidateObservation,
    CaptureAsset,
    CaptureSet,
    CaptureView,
)
from ..product_schemas import (
    AnalysisRunCreate,
    AnalysisRunResponse,
    CandidateObservationResponse,
)
from .capture import _owned

router = APIRouter(prefix="/v2", tags=["analysis"])


def _calibration_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _observation_response(value: CandidateObservation) -> CandidateObservationResponse:
    calibration = value.calibration_evidence
    uv = (
        (value.uv_u, value.uv_v)
        if value.uv_u is not None and value.uv_v is not None
        else None
    )
    return CandidateObservationResponse(
        observation_id=value.id,
        analysis_run_id=value.analysis_run_id,
        capture_view_id=value.capture_view_id,
        region=value.region,
        anatomical_site=value.anatomical_site,
        candidate_mask=value.candidate_mask,
        descriptors=value.descriptors,
        calibration=calibration,
        appearance_output=value.appearance_output,
        disease_research_output=value.disease_research_output,
        uncertainty=value.uncertainty,
        named_mesh=value.named_mesh,
        uv_coordinates=uv,
        asset_version=value.asset_version,
        limitations=value.limitations,
        created_at=value.created_at,
    )


async def analysis_response(
    session: AsyncSession, value: AnalysisRun
) -> AnalysisRunResponse:
    observations = list(
        await session.scalars(
            select(CandidateObservation)
            .where(
                CandidateObservation.analysis_run_id == value.id,
                CandidateObservation.deleted_at.is_(None),
            )
            .order_by(CandidateObservation.created_at, CandidateObservation.id)
        )
    )
    return AnalysisRunResponse(
        analysis_run_id=value.id,
        capture_set_id=value.capture_set_id,
        requested_heads=value.requested_heads,
        status=value.status,
        observations=[_observation_response(item) for item in observations],
        input_origin=value.input_origin,
        analysis_origin=value.analysis_origin,
        source_asset_sha256=value.source_asset_sha256,
        model_versions=value.model_versions,
        artifact_hashes=value.artifact_hashes,
        abstention_reasons=value.abstention_reasons,
        started_at=value.started_at,
        completed_at=value.completed_at,
        persisted=True,
        signed_envelope_id=value.signed_envelope_id,
    )


@router.post(
    "/capture-sets/{capture_set_id}/analysis-runs",
    response_model=AnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis_run(
    capture_set_id: str,
    body: AnalysisRunCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AnalysisRunResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.capture_set.{capture_set_id}.analysis_runs"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=AnalysisRunResponse,
    )
    if replay:
        return replay
    capture_set = await _owned(session, CaptureSet, capture_set_id, actor.user_id)
    if not capture_set.complete:
        raise ServiceError(
            409,
            "capture_set_incomplete",
            "Analysis requires a complete accepted capture set.",
        )

    view_rows = (
        await session.execute(
            select(CaptureView, CaptureAsset)
            .join(CaptureAsset, CaptureView.asset_id == CaptureAsset.id)
            .where(
                CaptureView.capture_set_id == capture_set.id,
                CaptureView.deleted_at.is_(None),
                CaptureAsset.deleted_at.is_(None),
            )
        )
    ).all()
    if not view_rows:
        raise ServiceError(
            409, "capture_set_empty", "No accepted capture is available."
        )
    view_by_id = {view.id: view for view, _asset in view_rows}
    expected_hashes = {asset.content_sha256 for _view, asset in view_rows}
    if set(body.source_asset_sha256) != expected_hashes:
        raise ServiceError(
            422,
            "source_asset_mismatch",
            "Analysis provenance must name the exact capture assets in this set.",
        )
    asset_origins = {asset.input_origin for _view, asset in view_rows}
    if asset_origins != {body.input_origin}:
        raise ServiceError(
            422,
            "input_origin_mismatch",
            "Analysis input origin must match every source capture.",
        )

    run = AnalysisRun(
        user_id=actor.user_id,
        capture_set_id=capture_set.id,
        requested_heads=[head.value for head in body.requested_heads],
        status=body.status,
        input_origin=body.input_origin,
        analysis_origin=body.analysis_origin,
        source_asset_sha256=body.source_asset_sha256,
        model_versions=body.model_versions,
        artifact_hashes=body.artifact_hashes,
        abstention_reasons=body.abstention_reasons,
        started_at=body.started_at,
        completed_at=body.completed_at,
        persisted=True,
        signed_envelope_id=body.signed_envelope_id,
    )
    session.add(run)
    await session.flush()

    observations: list[CandidateObservation] = []
    for item in body.observations:
        view = view_by_id.get(item.capture_view_id)
        if view is None or view.user_id != actor.user_id:
            raise ServiceError(
                404, "resource_not_found", "The requested resource was not found."
            )
        calibration = (
            item.calibration.model_dump(mode="json", by_alias=True)
            if item.calibration
            else None
        )
        calibration_status = (
            item.calibration.status
            if item.calibration
            else CalibrationStatus.NOT_ATTEMPTED
        )
        evidence_hash = _calibration_hash(calibration) if calibration else None
        observation = CandidateObservation(
            user_id=actor.user_id,
            analysis_run_id=run.id,
            capture_view_id=view.id,
            region=capture_set.region,
            anatomical_site=item.anatomical_site.value
            if item.anatomical_site
            else None,
            candidate_mask=item.candidate_mask.model_dump(mode="json", by_alias=True),
            descriptors=item.descriptors.model_dump(mode="json", by_alias=True),
            uncertainty=item.uncertainty.model_dump(mode="json", by_alias=True),
            appearance_output=(
                item.appearance_output.model_dump(mode="json", by_alias=True)
                if item.appearance_output
                else None
            ),
            disease_research_output=(
                item.disease_research_output.model_dump(mode="json", by_alias=True)
                if item.disease_research_output
                else None
            ),
            calibration_status=calibration_status,
            calibration_evidence=calibration,
            calibration_evidence_sha256=evidence_hash,
            estimated_width_mm=(
                item.calibration.estimated_width_mm if item.calibration else None
            ),
            estimated_height_mm=(
                item.calibration.estimated_height_mm if item.calibration else None
            ),
            estimated_area_mm2=(
                item.calibration.estimated_area_mm2 if item.calibration else None
            ),
            named_mesh=item.named_mesh,
            uv_u=item.uv_coordinates[0] if item.uv_coordinates else None,
            uv_v=item.uv_coordinates[1] if item.uv_coordinates else None,
            asset_version=item.asset_version,
            limitations=item.limitations,
        )
        session.add(observation)
        observations.append(observation)
    await session.flush()
    response = AnalysisRunResponse(
        analysis_run_id=run.id,
        capture_set_id=run.capture_set_id,
        requested_heads=run.requested_heads,
        status=run.status,
        observations=[_observation_response(item) for item in observations],
        input_origin=run.input_origin,
        analysis_origin=run.analysis_origin,
        source_asset_sha256=run.source_asset_sha256,
        model_versions=run.model_versions,
        artifact_hashes=run.artifact_hashes,
        abstention_reasons=run.abstention_reasons,
        started_at=run.started_at,
        completed_at=run.completed_at,
        persisted=True,
        signed_envelope_id=run.signed_envelope_id,
    )
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/analysis-runs/{analysis_run_id}", response_model=AnalysisRunResponse)
async def get_analysis_run(
    analysis_run_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalysisRunResponse:
    value = await _owned(session, AnalysisRun, analysis_run_id, actor.user_id)
    return await analysis_response(session, value)

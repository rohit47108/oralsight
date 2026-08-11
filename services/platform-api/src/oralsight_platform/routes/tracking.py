"""User-confirmed observation matching and lesion timeline routes."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
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
    AuditEvent,
    CandidateObservation,
    LesionObservationLink,
    LesionRecord,
    MatchDecision,
    MatchDecisionValue,
    MatchProposal,
    utc_now,
)
from ..product_schemas import (
    LesionCreate,
    LesionResponse,
    MatchDecisionCreate,
    MatchDecisionResponse,
    MatchProposalCreate,
    MatchProposalResponse,
)
from .capture import _owned

router = APIRouter(prefix="/v2", tags=["tracking"])


def _proposal_response(value: MatchProposal) -> MatchProposalResponse:
    return MatchProposalResponse(
        proposal_id=value.id,
        current_observation_id=value.current_observation_id,
        candidate_prior_observation_id=value.candidate_prior_observation_id,
        candidate_lesion_id=value.candidate_lesion_id,
        proposal_origin=value.proposal_origin,
        score=value.score,
        rank=value.rank,
        state="proposed",
        automatically_confirmed=False,
        model_versions=value.model_versions,
        generated_at=value.generated_at,
        expires_at=value.expires_at,
    )


def _decision_response(value: MatchDecision) -> MatchDecisionResponse:
    return MatchDecisionResponse(
        decision_id=value.id,
        proposal_id=value.proposal_id,
        decision=value.decision,
        decided_by="patient",
        actor_id=value.actor_id,
        rationale=value.rationale,
        decided_at=value.decided_at,
        lesion_id=value.lesion_id,
    )


async def lesion_response(session: AsyncSession, value: LesionRecord) -> LesionResponse:
    links = list(
        await session.scalars(
            select(LesionObservationLink)
            .join(
                CandidateObservation,
                LesionObservationLink.observation_id == CandidateObservation.id,
            )
            .where(LesionObservationLink.lesion_id == value.id)
            .order_by(CandidateObservation.created_at, CandidateObservation.id)
        )
    )
    return LesionResponse(
        lesion_id=value.id,
        region=value.region,
        anatomical_site=value.anatomical_site,
        label=value.label,
        status=value.status,
        confirmed_observation_ids=[link.observation_id for link in links],
        match_decision_ids=[link.decision_id for link in links if link.decision_id],
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


@router.post(
    "/match-proposals",
    response_model=MatchProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_match_proposal(
    body: MatchProposalCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MatchProposalResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.match_proposals.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=MatchProposalResponse,
    )
    if replay:
        return replay
    current = await _owned(
        session, CandidateObservation, body.current_observation_id, actor.user_id
    )
    prior = await _owned(
        session,
        CandidateObservation,
        body.candidate_prior_observation_id,
        actor.user_id,
    )
    if current.region is not prior.region:
        raise ServiceError(
            422,
            "region_mismatch",
            "Match proposals require observations from the same mouth region.",
        )
    if current.created_at < prior.created_at:
        raise ServiceError(
            422,
            "observation_order_invalid",
            "The proposed current observation cannot predate the prior observation.",
        )
    lesion = None
    if body.candidate_lesion_id:
        lesion = await _owned(
            session, LesionRecord, body.candidate_lesion_id, actor.user_id
        )
        prior_link = await session.scalar(
            select(LesionObservationLink).where(
                LesionObservationLink.lesion_id == lesion.id,
                LesionObservationLink.observation_id == prior.id,
            )
        )
        if prior_link is None:
            raise ServiceError(
                422,
                "candidate_lesion_mismatch",
                "The prior observation is not confirmed in the candidate lesion.",
            )
    if body.expires_at is not None and body.expires_at <= utc_now():
        raise ServiceError(
            422, "invalid_expiry", "Proposal expiry must be in the future."
        )
    value = MatchProposal(
        user_id=actor.user_id,
        current_observation_id=current.id,
        candidate_prior_observation_id=prior.id,
        candidate_lesion_id=lesion.id if lesion else None,
        proposal_origin=body.proposal_origin,
        score=body.score,
        rank=body.rank,
        model_versions=body.model_versions,
        expires_at=body.expires_at,
    )
    session.add(value)
    await session.flush()
    response = _proposal_response(value)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/match-proposals/{proposal_id}", response_model=MatchProposalResponse)
async def get_match_proposal(
    proposal_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MatchProposalResponse:
    value = await _owned(session, MatchProposal, proposal_id, actor.user_id)
    return _proposal_response(value)


@router.post(
    "/match-proposals/{proposal_id}/decisions",
    response_model=MatchDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def decide_match_proposal(
    proposal_id: str,
    body: MatchDecisionCreate,
    request: Request,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MatchDecisionResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = f"v2.match_proposal.{proposal_id}.decisions"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=MatchDecisionResponse,
    )
    if replay:
        return replay
    proposal = await _owned(session, MatchProposal, proposal_id, actor.user_id)
    if proposal.expires_at:
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= utc_now():
            raise ServiceError(
                409, "proposal_expired", "This match proposal has expired."
            )
    decisions = list(
        await session.scalars(
            select(MatchDecision)
            .where(MatchDecision.proposal_id == proposal.id)
            .order_by(MatchDecision.sequence.desc())
        )
    )
    if decisions and decisions[0].decision in {
        MatchDecisionValue.CONFIRMED,
        MatchDecisionValue.REJECTED,
    }:
        raise ServiceError(
            409,
            "proposal_already_decided",
            "This proposal already has a final decision.",
        )
    decision = MatchDecision(
        user_id=actor.user_id,
        proposal_id=proposal.id,
        decision=body.decision,
        actor_id=actor.user_id,
        rationale=body.rationale,
        sequence=(decisions[0].sequence + 1) if decisions else 1,
    )
    session.add(decision)
    await session.flush()

    lesion = None
    if body.decision is MatchDecisionValue.CONFIRMED:
        current = await _owned(
            session,
            CandidateObservation,
            proposal.current_observation_id,
            actor.user_id,
        )
        prior = await _owned(
            session,
            CandidateObservation,
            proposal.candidate_prior_observation_id,
            actor.user_id,
        )
        current_link = await session.scalar(
            select(LesionObservationLink).where(
                LesionObservationLink.observation_id == current.id
            )
        )
        if current_link:
            raise ServiceError(
                409,
                "observation_already_linked",
                "The current observation is already linked to a lesion.",
            )
        if proposal.candidate_lesion_id:
            lesion = await _owned(
                session, LesionRecord, proposal.candidate_lesion_id, actor.user_id
            )
            prior_link = await session.scalar(
                select(LesionObservationLink).where(
                    LesionObservationLink.lesion_id == lesion.id,
                    LesionObservationLink.observation_id == prior.id,
                )
            )
            if prior_link is None:
                raise ServiceError(
                    409,
                    "candidate_lesion_changed",
                    "The candidate lesion no longer contains the prior observation.",
                )
        else:
            prior_link = await session.scalar(
                select(LesionObservationLink).where(
                    LesionObservationLink.observation_id == prior.id
                )
            )
            if prior_link:
                lesion = await _owned(
                    session, LesionRecord, prior_link.lesion_id, actor.user_id
                )
            else:
                lesion = LesionRecord(
                    user_id=actor.user_id,
                    region=prior.region,
                    anatomical_site=prior.anatomical_site,
                )
                session.add(lesion)
                await session.flush()
                session.add(
                    LesionObservationLink(
                        user_id=actor.user_id,
                        lesion_id=lesion.id,
                        observation_id=prior.id,
                    )
                )
        if lesion.region is not current.region:
            raise ServiceError(
                422,
                "region_mismatch",
                "Confirmed observations must use the lesion mouth region.",
            )
        decision.lesion_id = lesion.id
        session.add(
            LesionObservationLink(
                user_id=actor.user_id,
                lesion_id=lesion.id,
                observation_id=current.id,
                decision_id=decision.id,
            )
        )
        lesion.version += 1

    session.add(
        AuditEvent(
            user_id=actor.user_id,
            actor_user_id=actor.user_id,
            event_type="match.decision_recorded",
            resource_type="match_proposal",
            resource_id=proposal.id,
            request_id=request.state.request_id,
            details={"decision": body.decision.value},
        )
    )
    await session.flush()
    response = _decision_response(decision)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/match-decisions/{decision_id}", response_model=MatchDecisionResponse)
async def get_match_decision(
    decision_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MatchDecisionResponse:
    value = await _owned(session, MatchDecision, decision_id, actor.user_id)
    return _decision_response(value)


@router.post(
    "/lesions", response_model=LesionResponse, status_code=status.HTTP_201_CREATED
)
async def create_lesion(
    body: LesionCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> LesionResponse:
    key = validate_idempotency_key(idempotency_header)
    digest = request_sha256(body)
    scope = "v2.lesions.create"
    replay = await find_replay(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response_model=LesionResponse,
    )
    if replay:
        return replay
    observation = await _owned(
        session, CandidateObservation, body.first_observation_id, actor.user_id
    )
    existing = await session.scalar(
        select(LesionObservationLink).where(
            LesionObservationLink.observation_id == observation.id
        )
    )
    if existing:
        raise ServiceError(
            409,
            "observation_already_linked",
            "This observation already belongs to a lesion timeline.",
        )
    lesion = LesionRecord(
        user_id=actor.user_id,
        region=observation.region,
        anatomical_site=observation.anatomical_site,
        label=body.label,
    )
    session.add(lesion)
    await session.flush()
    session.add(
        LesionObservationLink(
            user_id=actor.user_id,
            lesion_id=lesion.id,
            observation_id=observation.id,
        )
    )
    await session.flush()
    response = await lesion_response(session, lesion)
    return await commit_idempotent(
        session,
        user_id=actor.user_id,
        scope=scope,
        key=key,
        digest=digest,
        response=response,
        response_status=201,
    )


@router.get("/lesions/{lesion_id}", response_model=LesionResponse)
async def get_lesion(
    lesion_id: str,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LesionResponse:
    value = await _owned(session, LesionRecord, lesion_id, actor.user_id)
    return await lesion_response(session, value)

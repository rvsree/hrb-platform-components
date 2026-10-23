"""Ported from hrb_chatbot_v2's api/admin/manage_admin.py (Phase 187, lines
~774-821) - the 5 /interview-qa* routes. This repo has no RBAC/gateway layer
yet (ROADMAP.md Phase 1's spec), so these routes accept requests without an
identity check - the original's require_role(..., Role.ADMIN) calls and the
GET routes' query-param identity dependency are both dropped rather than
ported as dead code."""

from fastapi import APIRouter, Depends

from src.platform.common import error_codes
from src.platform.common.responses import json_error
from src.platform.interview_qa.models import (
    CreateInterviewQaRequest,
    DeleteInterviewQaResponse,
    InterviewQaCard,
    InterviewQaListResponse,
    UpdateInterviewQaRequest,
)
from src.platform.interview_qa.store import InterviewQaStore

router_interview_qa = APIRouter(tags=["interview-qa"])

_store = InterviewQaStore()


def get_interview_qa_store() -> InterviewQaStore:
    """A plain function, not a gateway - this module has exactly one backend,
    unlike hrb_chatbot_v2's multi-provider db_gateway. Overridable in tests
    via app.dependency_overrides[get_interview_qa_store]."""
    return _store


@router_interview_qa.get("/interview-qa", response_model=InterviewQaListResponse)
async def list_interview_qa_cards(topic: str | None = None, store: InterviewQaStore = Depends(get_interview_qa_store)):
    rows = await store.list_cards(topic)
    return InterviewQaListResponse(count=len(rows), cards=[InterviewQaCard(**row) for row in rows])


@router_interview_qa.get("/interview-qa/{card_id}", response_model=InterviewQaCard)
async def get_interview_qa_card(card_id: int, store: InterviewQaStore = Depends(get_interview_qa_store)):
    row = await store.get_card(card_id)
    if row is None:
        return json_error(404, f"No interview Q&A card found with id {card_id}.", code=error_codes.INTERVIEW_QA_NOT_FOUND)
    return InterviewQaCard(**row)


@router_interview_qa.post("/interview-qa", response_model=InterviewQaCard)
async def create_interview_qa_card(payload: CreateInterviewQaRequest, store: InterviewQaStore = Depends(get_interview_qa_store)):
    row = await store.create_card(payload.fields.model_dump())
    return InterviewQaCard(**row)


@router_interview_qa.put("/interview-qa/{card_id}", response_model=InterviewQaCard)
async def update_interview_qa_card(
    card_id: int, payload: UpdateInterviewQaRequest, store: InterviewQaStore = Depends(get_interview_qa_store)
):
    row = await store.update_card(card_id, payload.fields.model_dump())
    if row is None:
        return json_error(404, f"No interview Q&A card found with id {card_id}.", code=error_codes.INTERVIEW_QA_NOT_FOUND)
    return InterviewQaCard(**row)


@router_interview_qa.delete("/interview-qa/{card_id}", response_model=DeleteInterviewQaResponse)
async def delete_interview_qa_card(card_id: int, store: InterviewQaStore = Depends(get_interview_qa_store)):
    deleted = await store.delete_card(card_id)
    return DeleteInterviewQaResponse(id=card_id, deleted=deleted)

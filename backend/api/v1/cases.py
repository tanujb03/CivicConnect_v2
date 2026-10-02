from fastapi import APIRouter, Depends, HTTPException, Header
from backend.db.session import get_db
from sqlalchemy.orm import Session
from backend.ai_gateway import AIGateway, get_actor, get_gateway
from backend.ai_gateway.contracts import (
    FusionAnalyzeResponse, IntakeAnalyzeRequest, IntakeAnalyzeResponse,
    TriageAnalyzeResponse, TriageDecisionRequest, TriageDecisionResponse,
)
from backend.ai_gateway.service import Actor
from backend.schemas.case import CivicCaseCreate, CivicCaseResponse, CaseListResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# AI endpoints (§51A.5 / 51A.7 / 51A.8): contract shapes, §51A.18 roles and the adapter call live in ``backend.ai_gateway``.
# They are plain ``def`` handlers on purpose: the adapter is synchronous (HTTP + numpy) and FastAPI runs these in its thread pool.


@router.post("/intake/analyze", response_model=IntakeAnalyzeResponse)
def analyze_intake(request: IntakeAnalyzeRequest, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway)):
    return gateway.intake(request, actor)


@router.post("/{case_id}/fusion/analyze", response_model=FusionAnalyzeResponse)
def analyze_fusion(case_id: str, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway)):
    return gateway.fusion(case_id, actor)


@router.post("/{case_id}/triage/analyze", response_model=TriageAnalyzeResponse)
def analyze_triage(case_id: str, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway)):
    return gateway.triage(case_id, actor)


@router.post("/{case_id}/triage/decision", response_model=TriageDecisionResponse)
def apply_triage_decision(case_id: str, decision: TriageDecisionRequest, actor: Actor = Depends(get_actor),
                          gateway: AIGateway = Depends(get_gateway)):
    """Records the authorized human triage decision; a decision that differs from the stored AI recommendation is audited as an AI override."""
    return gateway.triage_decision(case_id, decision, actor)


@router.post("/", response_model=CivicCaseResponse)
def create_case(
    case_in: CivicCaseCreate,
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    # db_case = CivicCase(**case_in.dict())
    return {**case_in.dict(), "id": "CC-MOCK-1", "status": "reported", "created_at": "2026-10-01T00:00:00Z"}

@router.get("/", response_model=CaseListResponse)
def list_cases(
    cursor: str = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    return {"items": [], "next_cursor": None}

@router.get("/{case_id}", response_model=CivicCaseResponse)
def get_case(case_id: str, db: Session = Depends(get_db)):
    raise HTTPException(status_code=404, detail="Case not found")

@router.get("/{case_id}/timeline")
def get_case_timeline(case_id: str, db: Session = Depends(get_db)):
    return {"events": []}

@router.post("/{case_id}/verification")
def verify_case(
    case_id: str,
    db: Session = Depends(get_db)
):
    return {"status": "verified"}

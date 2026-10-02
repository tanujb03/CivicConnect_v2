from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from backend.db.session import get_db
from sqlalchemy.orm import Session
import os
from ai.inference.service import AIService
from ai.inference.schemas import (
    IntakeRequest, IntakeResponse,
    FusionRequest, FusionResponse,
    TriageRequest, TriageResponse,
)
from backend.schemas.case import CivicCaseCreate, CivicCaseResponse, CaseListResponse
from backend.models.case import CivicCase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency to get AI Service
def get_ai_service():
    # In production, this might be a singleton initialized at app startup
    return AIService.from_env()

@router.post("/intake/analyze", response_model=IntakeResponse)
async def analyze_intake(
    request: IntakeRequest,
    ai_service: AIService = Depends(get_ai_service)
):
    try:
        response = ai_service.analyze_intake(request)
        return response
    except Exception as e:
        logger.error(f"Error in analyze_intake: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{case_id}/fusion/analyze", response_model=FusionResponse)
async def analyze_fusion(
    case_id: str,
    request: FusionRequest,
    ai_service: AIService = Depends(get_ai_service)
):
    try:
        response = ai_service.analyze_fusion(request)
        return response
    except Exception as e:
        logger.error(f"Error in analyze_fusion for case {case_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{case_id}/triage/analyze", response_model=TriageResponse)
async def analyze_triage(
    case_id: str,
    request: TriageRequest,
    ai_service: AIService = Depends(get_ai_service)
):
    try:
        response = ai_service.analyze_triage(request)
        return response
    except Exception as e:
        logger.error(f"Error in analyze_triage for case {case_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{case_id}/triage/decision")
async def apply_triage_decision(
    case_id: str,
    decision: dict, # Would be a proper Pydantic schema in full implementation
    db: Session = Depends(get_db)
):
    """
    Applies the decision made by an operator after reviewing the triage analysis.
    """
    # Logic to update case status and create work orders based on decision
    return {"status": "success", "case_id": case_id, "action": "decision_applied"}

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

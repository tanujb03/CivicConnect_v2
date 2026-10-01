from fastapi import APIRouter, Depends, HTTPException
from ai.inference.service import AIService
from ai.inference.schemas import CopilotQuery, CopilotResponse, ActorContext
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def get_ai_service():
    return AIService.from_env()

@router.post("/query", response_model=CopilotResponse)
async def query_copilot(
    query: CopilotQuery,
    actor_context: ActorContext, # Should be extracted from auth token in reality
    ai_service: AIService = Depends(get_ai_service)
):
    try:
        response = ai_service.copilot_query(query, actor_context)
        return response
    except Exception as e:
        logger.error(f"Error in copilot_query: {e}")
        raise HTTPException(status_code=400, detail=str(e))

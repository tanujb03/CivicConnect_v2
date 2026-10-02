from fastapi import APIRouter, Depends
from backend.ai_gateway import AIGateway, get_actor, get_gateway
from backend.ai_gateway.contracts import CopilotQueryRequest, CopilotQueryResponse
from backend.ai_gateway.service import Actor

router = APIRouter()


@router.post("/query", response_model=CopilotQueryResponse)
def query_copilot(request: CopilotQueryRequest, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway)):
    """§51A.15. The actor comes from the bearer token (never the body); roles per §51A.18 (admin roles, overlooker scoped)."""
    return gateway.copilot(request, actor)

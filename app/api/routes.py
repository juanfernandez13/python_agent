from fastapi import APIRouter, Depends

from app.api.message_request import MessageRequest
from app.api.message_response import MessageResponse
from app.api.source_item import SourceItem
from app.core.deps import get_orchestrator
from app.flow.orchestrator import Orchestrator

router = APIRouter()


@router.post("/messages", response_model=MessageResponse)
async def post_messages(
    payload: MessageRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> MessageResponse:
    result = await orchestrator.handle(payload.message, payload.session_id)
    return MessageResponse(
        answer=result.answer,
        sources=[SourceItem(**item) for item in result.sources],
    )

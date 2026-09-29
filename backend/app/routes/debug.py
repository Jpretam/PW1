from fastapi import APIRouter, HTTPException

from app.agent.debugger import DebuggingAgent
from app.agent.models import DebugRequest, DebugDiagnosis
from app.logging_config import get_app_logger

logger = get_app_logger("debug_route")

router = APIRouter(
    prefix="/debug",
    tags=["debugging-agent"],
)

agent = DebuggingAgent()


@router.post(
    "/diagnose",
    response_model=DebugDiagnosis,
)
async def diagnose(
    request: DebugRequest,
) -> DebugDiagnosis:
    try:
        result = await agent.diagnose(
            execution_id=request.execution_id,
            initial_context=request.initial_context,
            mode=request.mode or "dynamic",
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Debugging agent failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="AI service is currently unavailable. Please try again later.",
        )

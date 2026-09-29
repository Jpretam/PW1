from fastapi import APIRouter, HTTPException
from app.agent.fixer import FixerAgent
from app.agent.models import FixRequest, FixResult
from app.logging_config import get_app_logger

logger = get_app_logger("fix_route")

router = APIRouter(
    prefix="/debug",
    tags=["fixer-agent"],
)

agent = FixerAgent()


@router.post(
    "/fix",
    response_model=FixResult,
)
async def fix_bug(
    request: FixRequest,
) -> FixResult:
    try:
        result = await agent.fix(
            execution_id=request.execution_id,
            max_attempts=request.max_attempts,
            mode=request.mode or "dynamic",
        )
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Fix request trace not found: %s", exc)
        raise HTTPException(
            status_code=404,
            detail="Execution trace not found.",
        )
    except Exception as exc:
        logger.error("Fixer agent failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="AI service is currently unavailable. Please try again later.",
        )

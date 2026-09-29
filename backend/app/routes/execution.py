from fastapi import APIRouter, HTTPException, status
from app.models.execution import ExecutionRequest, ExecutionResponse
from app.services.executor import CodeExecutionService
from app.logging_config import get_app_logger

logger = get_app_logger("execution_route")

router = APIRouter(tags=["execution"])
execution_service = CodeExecutionService()


@router.post(
    "/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute user code securely in sandbox",
    description="Accepts Python or Java code, executes it inside isolated execution sandbox, and returns standard execution results."
)
async def execute_code(payload: ExecutionRequest) -> ExecutionResponse:
    try:
        response = execution_service.execute_code(payload)
        return response
    except Exception as e:
        logger.error("Execution service failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again."
        )

"""
FastAPI router for Milestone 8 evaluation endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from app.evaluation.benchmarks import get_all_benchmarks, get_benchmark
from app.evaluation.logger import logger
from app.evaluation.models import (
    BenchmarkCase,
    BenchmarkRunRequest,
    ComparisonResult,
    ExperimentRecord,
    PairedBenchmarkRunRequest,
)
from app.evaluation.service import EvaluationService

router = APIRouter(
    prefix="/evaluation",
    tags=["evaluation"],
)

eval_service = EvaluationService()


@router.get(
    "/benchmarks",
    response_model=list[BenchmarkCase],
)
async def list_benchmarks() -> list[BenchmarkCase]:
    """Retrieve all fixed debugging benchmark tasks (B001 - B008)."""
    return get_all_benchmarks()


@router.get(
    "/benchmarks/{bug_id}",
    response_model=BenchmarkCase,
)
async def get_benchmark_by_id(bug_id: str) -> BenchmarkCase:
    """Retrieve a single benchmark by its bug_id (e.g., B001)."""
    bench = get_benchmark(bug_id)
    if not bench:
        raise HTTPException(
            status_code=404,
            detail=f"Benchmark '{bug_id}' not found.",
        )
    return bench


@router.post(
    "/run",
    response_model=ExperimentRecord,
)
async def run_single_experiment(request: BenchmarkRunRequest) -> ExperimentRecord:
    """Run an individual experiment in 'baseline' or 'dynamic' mode."""
    code = request.code
    language = request.language or "python"
    stdin = request.stdin or ""
    bug_id = request.bug_id or "CUSTOM"

    if request.bug_id and not code:
        bench = get_benchmark(request.bug_id)
        if not bench:
            raise HTTPException(
                status_code=404,
                detail=f"Benchmark '{request.bug_id}' not found.",
            )
        code = bench.code
        language = bench.language
        stdin = bench.stdin
        bug_id = bench.bug_id

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Either code or a valid bug_id must be provided.",
        )

    try:
        record = await eval_service.run_experiment(
            code=code,
            language=language,
            stdin=stdin,
            mode=request.mode,
            bug_id=bug_id,
        )
        return record
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Experiment execution failed: {str(exc)}",
        )


@router.post(
    "/run-paired",
    response_model=ComparisonResult,
)
async def run_paired_evaluation(request: PairedBenchmarkRunRequest) -> ComparisonResult:
    """Run both Baseline (Full Context) and Dynamic (Curated Context) for controlled paired comparison."""
    try:
        result = await eval_service.run_paired_experiment(
            bug_id=request.bug_id,
            code=request.code,
            language=request.language or "python",
            stdin=request.stdin or "",
        )
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Paired evaluation failed: {str(exc)}",
        )


@router.get(
    "/experiments",
    response_model=list[ExperimentRecord],
)
async def get_recent_experiments(limit: int = Query(default=50, ge=1, le=500)) -> list[ExperimentRecord]:
    """Retrieve logged experiment records from m8_experiments.csv."""
    return logger.get_experiments(limit=limit)

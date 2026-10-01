from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.context import AppContext, get_context
from app.models import HealthStatus

router = APIRouter(prefix="/health", tags=["operations"])


@router.get("", response_model=HealthStatus)
def health() -> HealthStatus:
    """Liveness: the process is up. Does not touch the store."""
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus, responses={503: {"model": HealthStatus}})
def ready(context: Annotated[AppContext, Depends(get_context)]) -> HealthStatus | JSONResponse:
    """Readiness: the store (database) is reachable."""
    try:
        reachable = context.store.ping()
    except Exception:
        reachable = False
    if reachable:
        return HealthStatus(status="ok")
    return JSONResponse(status_code=503, content={"status": "unavailable"})

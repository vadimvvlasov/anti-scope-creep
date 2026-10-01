from fastapi import APIRouter

from app.auth import CurrentUser
from app.errors import AppError, ErrorCode
from app.models import HistoryQueryRequest, HistoryQueryResult

router = APIRouter(tags=["query"])


@router.post("/query", response_model=HistoryQueryResult)
def query_history(body: HistoryQueryRequest, user: CurrentUser) -> HistoryQueryResult:
    """MVP: auth and input are validated, then the feature reports itself unavailable."""
    raise AppError(ErrorCode.FEATURE_NOT_AVAILABLE)

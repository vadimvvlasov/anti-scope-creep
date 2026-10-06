from typing import Annotated

from fastapi import APIRouter, Depends

from app.context import AppContext, get_context
from app.models import VersionInfo

router = APIRouter(prefix="/version", tags=["operations"])


@router.get("", response_model=VersionInfo)
def version(context: Annotated[AppContext, Depends(get_context)]) -> VersionInfo:
    """The image tag this backend was built as (sha-<7 hex>), or "local"."""
    return VersionInfo(version=context.settings.version)

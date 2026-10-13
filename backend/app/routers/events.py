import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.context import AppContext, get_context
from app.event_limits import client_ip
from app.models import AnalyticsEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["analytics"])


@router.post("", status_code=204, response_class=Response)
def record_event(
    body: AnalyticsEvent, request: Request, context: Annotated[AppContext, Depends(get_context)]
) -> Response:
    """Store one product event. No login; spam over the limits is dropped quietly."""
    if context.event_limiter.allow(client_ip(request), context.clock()):
        properties = body.properties.model_dump(exclude_none=True)
        context.store.add_event(body.event.value, body.distinct_id, properties, context.clock())
    else:
        logger.warning("Analytics event dropped: rate limit")
    return Response(status_code=204)

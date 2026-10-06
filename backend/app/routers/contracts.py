from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Response, UploadFile, status

from app.auth import CurrentUser
from app.context import AppContext, get_context
from app.errors import AppError, ErrorCode
from app.extraction import MAX_FILE_BYTES, UploadedFile, build_contract_input
from app.models import ContractDetail, ContractPage, ExportReportRequest, RenameContractRequest
from app.report import MEDIA_TYPES
from app.runner import AnalysisRunner, BackgroundTasksRunner
from app.services import ContractService

router = APIRouter(prefix="/contracts", tags=["contracts"])


def get_runner(
    background_tasks: BackgroundTasks, context: Annotated[AppContext, Depends(get_context)]
) -> AnalysisRunner:
    return BackgroundTasksRunner(background_tasks, context)


def get_service(
    context: Annotated[AppContext, Depends(get_context)],
    runner: Annotated[AnalysisRunner, Depends(get_runner)],
) -> ContractService:
    return ContractService(context, runner)


Service = Annotated[ContractService, Depends(get_service)]


def parse_contract_id(contract_id: str) -> UUID:
    """A malformed ID is just another contract that does not exist."""
    try:
        return UUID(contract_id)
    except ValueError:
        raise AppError(ErrorCode.CONTRACT_NOT_FOUND) from None


def _read_upload(file: UploadFile | None) -> UploadedFile | None:
    if file is None:
        return None
    # Read one byte past the limit so oversized files are detected without reading them fully.
    data = file.file.read(MAX_FILE_BYTES + 1)
    return UploadedFile(filename=file.filename or "", content_type=file.content_type, data=data)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ContractDetail)
def create_contract(
    user: CurrentUser,
    service: Service,
    file: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
) -> ContractDetail:
    data = build_contract_input(_read_upload(file), text or None, title)
    return service.create(user.id, data)


@router.get("", response_model=ContractPage)
def list_contracts(
    user: CurrentUser,
    service: Service,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ContractPage:
    return service.list_page(user.id, page, page_size)


@router.get("/{id}", response_model=ContractDetail)
def get_contract(id: str, user: CurrentUser, service: Service) -> ContractDetail:
    return service.get(user.id, parse_contract_id(id))


@router.patch("/{id}", response_model=ContractDetail)
def rename_contract(
    id: str, body: RenameContractRequest, user: CurrentUser, service: Service
) -> ContractDetail:
    return service.rename(user.id, parse_contract_id(id), body.title)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(id: str, user: CurrentUser, service: Service) -> Response:
    service.delete(user.id, parse_contract_id(id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/retry", status_code=status.HTTP_202_ACCEPTED, response_model=ContractDetail)
def retry_analysis(id: str, user: CurrentUser, service: Service) -> ContractDetail:
    return service.retry(user.id, parse_contract_id(id))


@router.post(
    "/{id}/export",
    response_class=Response,
    responses={
        200: {
            "description": "The report file.",
            "content": {
                media_type: {"schema": {"type": "string", "format": "binary"}}
                for media_type in MEDIA_TYPES.values()
            },
        }
    },
)
def export_report(id: str, body: ExportReportRequest, user: CurrentUser, service: Service) -> Response:
    """The counter-proposal report of the last successful analysis, as a file download."""
    report = service.export(user.id, parse_contract_id(id), body.format)
    return Response(
        content=report.content,
        media_type=report.media_type,
        headers={"Content-Disposition": f'attachment; filename="{report.filename}"'},
    )

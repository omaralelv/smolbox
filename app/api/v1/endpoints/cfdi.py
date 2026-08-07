from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.expense import Expense
from app.schemas.cfdi import CfdiParseResult, CfdiValidationResult
from app.services.cfdi_parser import CfdiParseError, parse_cfdi_xml
from app.services.cfdi_validator import validate_cfdi_for_expense


router = APIRouter()


async def _parse_upload(file: UploadFile) -> CfdiParseResult:
    content_type = file.content_type or "application/octet-stream"
    allowed_types = {"application/xml", "text/xml", "application/octet-stream"}
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {content_type}",
        )

    try:
        return parse_cfdi_xml(await file.read())
    except CfdiParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cfdi/parse", response_model=CfdiParseResult)
async def parse_cfdi(file: UploadFile = File(...)) -> CfdiParseResult:
    return await _parse_upload(file)


@router.post("/expenses/{expense_id}/cfdi/validate", response_model=CfdiValidationResult)
async def validate_expense_cfdi(
    expense_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CfdiValidationResult:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    parsed = await _parse_upload(file)
    return validate_cfdi_for_expense(
        parsed,
        expense,
        expected_receiver_rfc=settings.cfdi_receiver_rfc,
    )

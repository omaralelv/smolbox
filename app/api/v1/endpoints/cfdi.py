from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.cfdi_validation import CfdiValidation
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.schemas.cfdi import CfdiParseResult, CfdiUuidAvailability, CfdiValidationResult
from app.services.cfdi_parser import CfdiParseError, parse_cfdi_xml
from app.services.cfdi_validator import normalize_cfdi_uuid, validate_cfdi_for_expense
from app.services.request_editability import is_request_editable
from app.services.storage import (
    EmptyUpload,
    StorageService,
    UploadTooLarge,
    read_upload_limited,
)

router = APIRouter()


async def _parse_upload(
    file: UploadFile,
    settings: Settings,
) -> tuple[bytes, CfdiParseResult]:
    try:
        content = await read_upload_limited(file, settings.max_upload_bytes)
    except EmptyUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc

    if Path(file.filename or "upload.xml").suffix.lower() != ".xml":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="CFDI evidence must use the .xml extension",
        )

    try:
        return content, parse_cfdi_xml(content)
    except CfdiParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post("/cfdi/parse", response_model=CfdiParseResult)
async def parse_cfdi(
    file: Annotated[UploadFile, File()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CfdiParseResult:
    _, parsed = await _parse_upload(file, settings)
    return parsed


@router.get("/cfdi/uuid/{uuid}/availability", response_model=CfdiUuidAvailability)
def check_cfdi_uuid_availability(
    uuid: str,
    db: Annotated[Session, Depends(get_db)],
) -> CfdiUuidAvailability:
    normalized_uuid = normalize_cfdi_uuid(uuid)
    if normalized_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_CFDI_UUID",
                "message": "The fiscal UUID is not valid",
                "uuid": uuid,
            },
        )

    duplicate_expense_id, duplicate_validation_expense_id = _find_duplicate_cfdi_uuid(
        db,
        normalized_uuid,
    )
    return CfdiUuidAvailability(
        uuid=normalized_uuid,
        is_available=duplicate_expense_id is None and duplicate_validation_expense_id is None,
        existing_expense_id=duplicate_expense_id,
        existing_validation_expense_id=duplicate_validation_expense_id,
    )


@router.post("/expenses/{expense_id}/cfdi/validate", response_model=CfdiValidationResult)
async def validate_expense_cfdi(
    expense_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CfdiValidationResult:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.reimbursement_request is not None:
        _ensure_request_editable(
            expense.reimbursement_request,
            message="CFDI evidence can only be validated while the request is draft or in correction.",
        )

    content, parsed = await _parse_upload(file, settings)
    result = validate_cfdi_for_expense(
        parsed,
        expense,
        expected_receiver_rfc=settings.cfdi_receiver_rfc,
    )

    normalized_uuid = normalize_cfdi_uuid(parsed.uuid)
    if normalized_uuid is not None:
        duplicate_expense_id, duplicate_validation_expense_id = _find_duplicate_cfdi_uuid(
            db,
            normalized_uuid,
            exclude_expense_id=expense.id,
        )
        if duplicate_expense_id is not None or duplicate_validation_expense_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_CFDI_UUID",
                    "message": "The fiscal UUID is already registered for another expense",
                    "uuid": normalized_uuid,
                },
            )

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    stored = storage.save_bytes(
        content,
        filename=file.filename or "cfdi.xml",
        expense_id=expense.id,
    )
    attachment = Attachment(
        expense_id=expense.id,
        attachment_type=AttachmentType.cfdi_xml,
        filename=stored.filename,
        content_type="application/xml",
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )

    try:
        db.add(attachment)
        db.flush()
        db.execute(
            update(CfdiValidation)
            .where(CfdiValidation.expense_id == expense.id, CfdiValidation.is_current.is_(True))
            .values(is_current=False)
        )
        db.add(
            CfdiValidation(
                expense_id=expense.id,
                attachment_id=attachment.id,
                uuid=normalized_uuid,
                issuer_rfc=parsed.issuer_rfc,
                receiver_rfc=parsed.receiver_rfc,
                subtotal=parsed.subtotal,
                total=parsed.total,
                currency=parsed.currency,
                tax_amount=parsed.tax_amount,
                tax_rate=parsed.tax_rate,
                issued_at=parsed.issued_at,
                is_valid=result.is_valid,
                issues=[issue.model_dump(mode="json") for issue in result.issues],
                checksum_sha256=stored.checksum_sha256,
                validator_version="1.0",
                is_current=True,
            )
        )
        expense.cfdi_uuid = normalized_uuid
        expense.cfdi_issuer_rfc = parsed.issuer_rfc
        expense.cfdi_receiver_rfc = parsed.receiver_rfc
        expense.cfdi_subtotal = parsed.subtotal
        expense.cfdi_total = parsed.total
        expense.cfdi_currency = parsed.currency
        expense.cfdi_tax_amount = parsed.tax_amount
        expense.cfdi_tax_rate = parsed.tax_rate
        if expense.reimbursement_request_id is not None:
            db.add(
                AuditLog(
                    reimbursement_request_id=expense.reimbursement_request_id,
                    expense_id=expense.id,
                    actor_type=AuditActorType.system,
                    action="expense_cfdi_validated",
                    message="CFDI XML parsed, validated and stored.",
                    event_payload={
                        "is_valid": result.is_valid,
                        "uuid": normalized_uuid,
                        "issue_codes": [issue.code for issue in result.issues],
                    },
                )
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        storage.delete(stored.storage_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_CFDI_UUID",
                "message": "The fiscal UUID is already registered",
                "uuid": normalized_uuid,
            },
        ) from exc
    except Exception:
        db.rollback()
        storage.delete(stored.storage_path)
        raise

    return result


def _find_duplicate_cfdi_uuid(
    db: Session,
    normalized_uuid: str,
    *,
    exclude_expense_id: UUID | None = None,
) -> tuple[UUID | None, UUID | None]:
    expense_filters = [Expense.cfdi_uuid == normalized_uuid]
    validation_filters = [CfdiValidation.uuid == normalized_uuid]
    if exclude_expense_id is not None:
        expense_filters.append(Expense.id != exclude_expense_id)
        validation_filters.append(CfdiValidation.expense_id != exclude_expense_id)

    duplicate_expense_id = db.scalar(select(Expense.id).where(*expense_filters))
    duplicate_validation_expense_id = db.scalar(
        select(CfdiValidation.expense_id).where(*validation_filters)
    )
    return duplicate_expense_id, duplicate_validation_expense_id


def _ensure_request_editable(reimbursement_request: ReimbursementRequest, *, message: str) -> None:
    if not is_request_editable(reimbursement_request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": message,
            },
        )

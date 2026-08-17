from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.cfdi_validation import CfdiValidation
from app.models.expense import Expense, ExpenseStatus
from app.models.payment import Payment, PaymentStatus
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.store import Store
from app.models.user import User, UserRole
from app.schemas.attachment import AttachmentRead
from app.schemas.audit_log import AuditLogRead
from app.schemas.expense_import import ExpenseImportErrorRead, ExpenseImportResult
from app.schemas.payment import PaymentCreate, PaymentRead
from app.schemas.reimbursement_request import (
    AuthenticatedReimbursementRequestTransition,
    AuthenticatedSapPolicyPrepare,
    AutomatedReviewRead,
    ExpenseDetailRead,
    ReimbursementRequestCreate,
    ReimbursementRequestDetailRead,
    ReimbursementRequestRead,
    ReimbursementRequestTransition,
    ReimbursementRequestUpdate,
    ReimbursementValidationSummary,
    SapPolicyPrepare,
    SapPolicyRead,
)
from app.services.automation_review import build_automated_review
from app.services.expense_import import ExpenseImportUnsupported, parse_expense_import
from app.services.file_validation import InvalidAttachment, detect_attachment_content_type
from app.services.frontend_actions import available_actions_for_request
from app.services.permissions import user_can_transition_store_request
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.request_editability import is_request_editable
from app.services.sap_policy import SapPolicyPreparationError, prepare_sap_policy_placeholder
from app.services.storage import (
    EmptyUpload,
    StorageService,
    UploadTooLarge,
    read_upload_limited,
)
from app.services.workflow import (
    REVIEW_STEP_RETURN_TARGETS,
    WorkflowTransitionError,
    transition_reimbursement_request,
)

router = APIRouter()

@router.post("/", response_model=ReimbursementRequestRead, status_code=status.HTTP_201_CREATED)
def create_reimbursement_request(
    request_in: ReimbursementRequestCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    store = db.get(Store, request_in.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    period = db.get(Period, request_in.period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERIOD_CLOSED", "message": "The reimbursement period is closed"},
        )

    request_data = request_in.model_dump()
    request_data["folio"] = request_data.get("folio") or _generate_request_folio(store, db)

    reimbursement_request = ReimbursementRequest(**request_data)
    db.add(reimbursement_request)
    try:
        db.flush()
        db.add(
            AuditLog(
                reimbursement_request_id=reimbursement_request.id,
                actor_type=AuditActorType.system,
                action="request_created",
                to_status=reimbursement_request.status.value,
                message="Reimbursement request created.",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_REIMBURSEMENT_FOLIO",
                "message": "A request already exists with this folio",
            },
        ) from exc
    db.refresh(reimbursement_request)
    return reimbursement_request


@router.get("/", response_model=list[ReimbursementRequestRead])
def list_reimbursement_requests(
    db: Annotated[Session, Depends(get_db)],
    store_id: UUID | None = None,
    period_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReimbursementRequest]:
    statement = (
        select(ReimbursementRequest)
        .order_by(ReimbursementRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if store_id is not None:
        statement = statement.where(ReimbursementRequest.store_id == store_id)
    if period_id is not None:
        statement = statement.where(ReimbursementRequest.period_id == period_id)
    return list(db.scalars(statement))


@router.get("/{request_id}", response_model=ReimbursementRequestRead)
def get_reimbursement_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    return reimbursement_request


@router.get("/{request_id}/detail/me", response_model=ReimbursementRequestDetailRead)
def get_reimbursement_request_detail_as_current_user(
    request_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequestDetailRead:
    reimbursement_request = _get_request_detail_or_404(request_id, db)
    _ensure_request_visible_to_user(reimbursement_request, current_user, db)
    return _build_request_detail(reimbursement_request, current_user)


@router.patch("/{request_id}", response_model=ReimbursementRequestRead)
def update_reimbursement_request(
    request_id: UUID,
    request_in: ReimbursementRequestUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    _ensure_request_editable(reimbursement_request)
    updates = request_in.model_dump(exclude_unset=True)
    starts_on = updates.get(
        "previous_reimbursement_starts_on",
        reimbursement_request.previous_reimbursement_starts_on,
    )
    ends_on = updates.get(
        "previous_reimbursement_ends_on",
        reimbursement_request.previous_reimbursement_ends_on,
    )
    if starts_on and ends_on and ends_on < starts_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "previous_reimbursement_ends_on must be on or after "
                "previous_reimbursement_starts_on"
            ),
        )

    changed_fields = sorted(updates)
    for field, value in updates.items():
        setattr(reimbursement_request, field, value)

    if changed_fields:
        db.add(
            AuditLog(
                reimbursement_request_id=reimbursement_request.id,
                actor_type=AuditActorType.system,
                action="request_updated",
                message="Reimbursement request updated.",
                event_payload={"changed_fields": changed_fields},
            )
        )
    db.commit()
    db.refresh(reimbursement_request)
    return reimbursement_request


@router.get("/{request_id}/validation-summary", response_model=ReimbursementValidationSummary)
def get_reimbursement_validation_summary(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementValidationSummary:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        )
        .where(ReimbursementRequest.id == request_id)
    )
    reimbursement_request = db.scalars(statement).first()
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    return summarize_reimbursement_request(reimbursement_request)


@router.post("/{request_id}/automated-review", response_model=AutomatedReviewRead)
def run_reimbursement_automated_review(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> AutomatedReviewRead:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        )
        .where(ReimbursementRequest.id == request_id)
    )
    reimbursement_request = db.scalars(statement).first()
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    summary = summarize_reimbursement_request(reimbursement_request)
    review = build_automated_review(reimbursement_request, summary)
    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_type=AuditActorType.system,
            action="automated_review_completed",
            message="Automatic validation flow completed.",
            event_payload={
                "overall_status": review.overall_status,
                "automatic_steps": [
                    {"code": step.code, "status": step.status, "blocking": step.blocking}
                    for step in review.automatic_steps
                ],
                "human_steps": [
                    {"code": step.code, "status": step.status, "blocking": step.blocking}
                    for step in review.human_steps
                ],
                "alert_codes": [issue.code for issue in review.alerts],
            },
        )
    )
    db.commit()
    return review


@router.post("/{request_id}/transition", response_model=ReimbursementRequestRead)
def transition_request(
    request_id: UUID,
    transition_in: ReimbursementRequestTransition,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    actor = db.get(User, transition_in.actor_user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actor user not found")
    return _transition_request_with_actor(
        request_id,
        actor=actor,
        target_status=transition_in.target_status,
        note=transition_in.note,
        authenticated=False,
        db=db,
    )


@router.post("/{request_id}/transition/me", response_model=ReimbursementRequestRead)
def transition_request_as_current_user(
    request_id: UUID,
    transition_in: AuthenticatedReimbursementRequestTransition,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    return _transition_request_with_actor(
        request_id,
        actor=current_user,
        target_status=transition_in.target_status,
        note=transition_in.note,
        authenticated=True,
        db=db,
    )


@router.post("/{request_id}/sap-policy/prepare", response_model=SapPolicyRead)
def prepare_reimbursement_request_sap_policy(
    request_id: UUID,
    policy_in: SapPolicyPrepare,
    db: Annotated[Session, Depends(get_db)],
) -> SapPolicyRead:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    actor = db.get(User, policy_in.actor_user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actor user not found")
    if not user_can_transition_store_request(db, actor, reimbursement_request.store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the request store for this action",
            },
        )

    try:
        payload = prepare_sap_policy_placeholder(
            reimbursement_request,
            actor=actor,
            reference=policy_in.reference,
        )
    except SapPolicyPreparationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SAP_POLICY_NOT_READY", "message": str(exc)},
        ) from exc

    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="sap_policy_placeholder_prepared",
            message=policy_in.note or "SAP policy placeholder prepared.",
            event_payload={
                "reference": reimbursement_request.sap_policy_reference,
                "payload": payload,
            },
        )
    )
    db.commit()
    db.refresh(reimbursement_request)
    return SapPolicyRead(
        request_id=reimbursement_request.id,
        status="prepared",
        reference=reimbursement_request.sap_policy_reference or "",
        generated_at=reimbursement_request.sap_policy_generated_at,
        generated_by_user_id=actor.id,
        payload=reimbursement_request.sap_policy_payload or {},
    )


@router.post("/{request_id}/sap-policy/prepare/me", response_model=SapPolicyRead)
def prepare_reimbursement_request_sap_policy_as_current_user(
    request_id: UUID,
    policy_in: AuthenticatedSapPolicyPrepare,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SapPolicyRead:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    return _prepare_sap_policy_with_actor(
        reimbursement_request,
        actor=current_user,
        reference=policy_in.reference,
        note=policy_in.note,
        authenticated=True,
        db=db,
    )


@router.get("/{request_id}/payments", response_model=list[PaymentRead])
def list_reimbursement_request_payments(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[Payment]:
    if db.get(ReimbursementRequest, request_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.reimbursement_request_id == request_id)
            .order_by(Payment.created_at.desc())
        )
    )


@router.post("/{request_id}/payments/me", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def record_reimbursement_request_payment_as_current_user(
    request_id: UUID,
    payment_in: PaymentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    if current_user.role not in {UserRole.treasury, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": f"Role {current_user.role.value} cannot record payments",
            },
        )
    if not user_can_transition_store_request(db, current_user, reimbursement_request.store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the request store for this action",
            },
        )
    existing_paid_payment = db.scalar(
        select(Payment.id).where(
            Payment.reimbursement_request_id == reimbursement_request.id,
            Payment.status == PaymentStatus.paid,
        )
    )
    if (
        reimbursement_request.status == ReimbursementRequestStatus.paid
        or existing_paid_payment is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PAYMENT_ALREADY_RECORDED",
                "message": "This request already has a recorded treasury payment",
                "suggestion": "Open the payment history instead of recording a second payment.",
            },
        )
    if reimbursement_request.status != ReimbursementRequestStatus.approved_for_payment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_APPROVED_FOR_PAYMENT",
                "message": "Payments can only be recorded after payment approval",
            },
        )

    summary = summarize_reimbursement_request(reimbursement_request)
    expected_amount = summary.calculated_total.quantize(Decimal("0.01"))
    payment_amount = (payment_in.amount or expected_amount).quantize(Decimal("0.01"))
    if summary.expense_count == 0 or expected_amount <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "NO_PAYABLE_EXPENSES",
                "message": "The request does not have an approved amount to pay",
            },
        )
    payment_currency = payment_in.currency.upper()
    expected_currency = _active_request_currency(reimbursement_request)
    if payment_currency != expected_currency:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PAYMENT_CURRENCY_MISMATCH",
                "message": "Payment currency must match the approved request currency",
                "expected_currency": expected_currency,
                "received_currency": payment_currency,
            },
        )
    if payment_amount != expected_amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PAYMENT_AMOUNT_MISMATCH",
                "message": "Payment amount must match the approved request total",
                "expected_amount": str(expected_amount),
                "received_amount": str(payment_amount),
            },
        )
    now = datetime.now(UTC)
    payment = Payment(
        reimbursement_request_id=reimbursement_request.id,
        amount=payment_amount,
        currency=payment_currency,
        payment_method=payment_in.payment_method,
        reference=payment_in.reference,
        note=payment_in.note,
        status=PaymentStatus.paid,
        paid_at=now,
        paid_by_user_id=current_user.id,
    )
    reimbursement_request.status = ReimbursementRequestStatus.paid
    reimbursement_request.paid_at = now
    db.add(payment)
    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="payment_recorded",
            from_status=ReimbursementRequestStatus.approved_for_payment.value,
            to_status=ReimbursementRequestStatus.paid.value,
            message=payment_in.note or "Payment recorded by treasury.",
            event_payload={
                "amount": str(payment_amount),
                "currency": payment_currency,
                "payment_method": payment_in.payment_method,
                "reference": payment_in.reference,
            },
        )
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{request_id}/audit-events", response_model=list[AuditLogRead])
def list_reimbursement_request_audit_events(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLog]:
    if db.get(ReimbursementRequest, request_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    statement = (
        select(AuditLog)
        .where(AuditLog.reimbursement_request_id == request_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement))


@router.post(
    "/{request_id}/expenses/import",
    response_model=ExpenseImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_reimbursement_request_expenses(
    request_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    dry_run: Annotated[bool, Form()] = False,
) -> ExpenseImportResult:
    statement = (
        select(ReimbursementRequest)
        .options(selectinload(ReimbursementRequest.period))
        .where(ReimbursementRequest.id == request_id)
    )
    reimbursement_request = db.scalars(statement).first()
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    _ensure_request_editable(reimbursement_request)
    if reimbursement_request.period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERIOD_CLOSED", "message": "The reimbursement period is closed"},
        )

    try:
        content = await read_upload_limited(file, settings.max_upload_bytes)
    except EmptyUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc

    try:
        content_type = detect_attachment_content_type(
            file.filename or "expense-import.xlsx",
            content,
            AttachmentType.cash_box_format,
        )
        parsed_rows, row_errors = parse_expense_import(content, file.filename or "expense-import.xlsx")
    except InvalidAttachment as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except ExpenseImportUnsupported as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "IMPORT_FILE_NOT_READABLE", "message": str(exc)},
        ) from exc

    errors = [
        ExpenseImportErrorRead(
            row_number=error.row_number,
            field=error.field,
            message=error.message,
        )
        for error in row_errors
    ]
    for row in parsed_rows:
        if not reimbursement_request.period.starts_on <= row.spent_on <= reimbursement_request.period.ends_on:
            errors.append(
                ExpenseImportErrorRead(
                    row_number=row.row_number,
                    field="spent_on",
                    message="Expense date is outside the reimbursement period",
                )
            )

    if not parsed_rows and not errors:
        errors.append(
            ExpenseImportErrorRead(
                row_number=1,
                field="file",
                message="No expense rows found",
            )
        )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "IMPORT_VALIDATION_FAILED",
                "message": "The file contains rows that cannot be imported",
                "errors": [error.model_dump(mode="json") for error in errors],
            },
        )

    if dry_run:
        return ExpenseImportResult(
            request_id=reimbursement_request.id,
            imported_count=len(parsed_rows),
            dry_run=True,
            attachment_id=None,
            expenses=[],
            errors=[],
        )

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    stored = storage.save_bytes(
        content,
        filename=file.filename or "expense-import.xlsx",
        reimbursement_request_id=request_id,
    )
    attachment = Attachment(
        reimbursement_request_id=reimbursement_request.id,
        attachment_type=AttachmentType.cash_box_format,
        filename=stored.filename,
        content_type=content_type,
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    expenses = [
        Expense(
            period_id=reimbursement_request.period_id,
            reimbursement_request_id=reimbursement_request.id,
            merchant=row.merchant,
            amount=row.amount,
            currency=row.currency,
            spent_on=row.spent_on,
            category=row.category,
            description=row.description,
            supplier_tax_id=row.supplier_tax_id,
            requires_authorization=row.requires_authorization,
        )
        for row in parsed_rows
    ]

    try:
        db.add(attachment)
        for expense in expenses:
            db.add(expense)
        db.flush()
        db.add(
            AuditLog(
                reimbursement_request_id=reimbursement_request.id,
                actor_type=AuditActorType.system,
                action="expenses_imported",
                message=f"{len(expenses)} expenses imported from {stored.filename}.",
                event_payload={
                    "attachment_id": str(attachment.id),
                    "filename": stored.filename,
                    "imported_count": len(expenses),
                },
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(stored.storage_path)
        raise

    db.refresh(attachment)
    for expense in expenses:
        db.refresh(expense)

    return ExpenseImportResult(
        request_id=reimbursement_request.id,
        imported_count=len(expenses),
        dry_run=False,
        attachment_id=attachment.id,
        expenses=expenses,
        errors=[],
    )


@router.post(
    "/{request_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reimbursement_request_attachment(
    request_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    attachment_type: Annotated[AttachmentType, Form()] = AttachmentType.cash_box_format,
) -> Attachment:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    if attachment_type != AttachmentType.cash_box_format:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Request-level attachments must use the cash_box_format type",
        )

    _ensure_request_editable(reimbursement_request)

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    try:
        content = await read_upload_limited(file, settings.max_upload_bytes)
    except EmptyUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc

    try:
        content_type = detect_attachment_content_type(
            file.filename or "upload",
            content,
            attachment_type,
        )
    except InvalidAttachment as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    stored = storage.save_bytes(
        content,
        filename=file.filename or "upload",
        reimbursement_request_id=request_id,
    )
    attachment = Attachment(
        reimbursement_request_id=reimbursement_request.id,
        attachment_type=attachment_type,
        filename=stored.filename,
        content_type=content_type,
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    db.add(attachment)
    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_type=AuditActorType.system,
            action="request_attachment_uploaded",
            message=f"Attachment uploaded: {stored.filename}",
            event_payload={
                "attachment_type": attachment_type.value,
                "size_bytes": stored.size_bytes,
                "checksum_sha256": stored.checksum_sha256,
            },
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(stored.storage_path)
        raise
    db.refresh(attachment)
    return attachment


def _transition_request_with_actor(
    request_id: UUID,
    *,
    actor: User,
    target_status: ReimbursementRequestStatus,
    note: str | None,
    authenticated: bool,
    db: Session,
) -> ReimbursementRequest:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        )
        .where(ReimbursementRequest.id == request_id)
    )
    reimbursement_request = db.scalars(statement).first()
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    if not user_can_transition_store_request(db, actor, reimbursement_request.store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the request store for this transition",
            },
        )

    summary = summarize_reimbursement_request(reimbursement_request)
    try:
        from_status, to_status = transition_reimbursement_request(
            reimbursement_request,
            actor=actor,
            target_status=target_status,
            summary=summary,
        )
    except WorkflowTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_WORKFLOW_TRANSITION", "message": str(exc)},
        ) from exc

    if to_status == ReimbursementRequestStatus.correction_required:
        reimbursement_request.correction_requested_at = datetime.now(UTC)
        reimbursement_request.correction_requested_by_user_id = actor.id
        reimbursement_request.correction_return_status = from_status
        reimbursement_request.correction_reason = note
    elif _is_review_step_return(from_status, to_status):
        reimbursement_request.correction_requested_at = datetime.now(UTC)
        reimbursement_request.correction_requested_by_user_id = actor.id
        reimbursement_request.correction_return_status = to_status
        reimbursement_request.correction_reason = note

    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="request_status_changed",
            from_status=from_status.value,
            to_status=to_status.value,
            message=note,
            event_payload={
                "ready_for_submission": summary.ready_for_submission,
                "ready_for_authorization_approval": summary.ready_for_authorization_approval,
                "ready_for_accounting_approval": summary.ready_for_accounting_approval,
                "authenticated": authenticated,
            },
        )
    )
    db.commit()
    db.refresh(reimbursement_request)
    return reimbursement_request


def _generate_request_folio(store: Store, db: Session) -> str:
    prefix = f"{store.code}-{datetime.now(UTC).date():%d%m%Y}"
    existing_folios = db.scalars(
        select(ReimbursementRequest.folio).where(
            ReimbursementRequest.folio.is_not(None),
            ReimbursementRequest.folio.like(f"{prefix}%"),
        )
    )
    highest_sequence = 0
    for folio in existing_folios:
        if folio is None or not folio.startswith(prefix):
            continue
        suffix = folio.removeprefix(prefix)
        if suffix.isdecimal():
            highest_sequence = max(highest_sequence, int(suffix))
    return f"{prefix}{highest_sequence + 1}"


def _get_request_detail_or_404(request_id: UUID, db: Session) -> ReimbursementRequest:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.store),
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
            selectinload(ReimbursementRequest.payments),
            selectinload(ReimbursementRequest.audit_events),
        )
        .where(ReimbursementRequest.id == request_id)
    )
    reimbursement_request = db.scalars(statement).first()
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    return reimbursement_request


def _ensure_request_visible_to_user(
    reimbursement_request: ReimbursementRequest,
    current_user: User,
    db: Session,
) -> None:
    if not user_can_transition_store_request(db, current_user, reimbursement_request.store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the request store",
            },
        )


def _build_request_detail(
    reimbursement_request: ReimbursementRequest,
    current_user: User,
) -> ReimbursementRequestDetailRead:
    summary = summarize_reimbursement_request(reimbursement_request)
    return ReimbursementRequestDetailRead(
        **ReimbursementRequestRead.model_validate(reimbursement_request).model_dump(),
        store=reimbursement_request.store,
        period=reimbursement_request.period,
        expenses=[
            _build_expense_detail(expense)
            for expense in sorted(
                reimbursement_request.expenses,
                key=lambda expense: expense.created_at,
            )
        ],
        attachments=sorted(
            reimbursement_request.attachments,
            key=lambda attachment: attachment.uploaded_at,
            reverse=True,
        ),
        validation_summary=summary,
        payments=sorted(
            reimbursement_request.payments,
            key=lambda payment: payment.created_at,
            reverse=True,
        ),
        audit_events=sorted(
            reimbursement_request.audit_events,
            key=lambda audit_event: audit_event.created_at,
            reverse=True,
        ),
        available_actions=available_actions_for_request(
            reimbursement_request,
            actor=current_user,
            summary=summary,
        ),
    )


def _build_expense_detail(expense: Expense) -> ExpenseDetailRead:
    return ExpenseDetailRead(
        **ExpenseDetailRead.model_validate(expense).model_dump(
            exclude={"attachments", "current_cfdi_validation"}
        ),
        attachments=sorted(
            expense.attachments,
            key=lambda attachment: attachment.uploaded_at,
            reverse=True,
        ),
        current_cfdi_validation=_current_cfdi_validation(expense),
    )


def _current_cfdi_validation(expense: Expense) -> CfdiValidation | None:
    current_validations = [
        validation for validation in expense.cfdi_validations if validation.is_current
    ]
    if not current_validations:
        return None
    return max(current_validations, key=lambda validation: validation.validated_at)


def _is_review_step_return(
    from_status: ReimbursementRequestStatus,
    to_status: ReimbursementRequestStatus,
) -> bool:
    return REVIEW_STEP_RETURN_TARGETS.get(from_status) == to_status


def _prepare_sap_policy_with_actor(
    reimbursement_request: ReimbursementRequest,
    *,
    actor: User,
    reference: str | None,
    note: str | None,
    authenticated: bool,
    db: Session,
) -> SapPolicyRead:
    if not user_can_transition_store_request(db, actor, reimbursement_request.store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the request store for this action",
            },
        )

    try:
        payload = prepare_sap_policy_placeholder(
            reimbursement_request,
            actor=actor,
            reference=reference,
        )
    except SapPolicyPreparationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SAP_POLICY_NOT_READY", "message": str(exc)},
        ) from exc

    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="sap_policy_placeholder_prepared",
            message=note or "SAP policy placeholder prepared.",
            event_payload={
                "reference": reimbursement_request.sap_policy_reference,
                "payload": payload,
                "authenticated": authenticated,
            },
        )
    )
    db.commit()
    db.refresh(reimbursement_request)
    return SapPolicyRead(
        request_id=reimbursement_request.id,
        status="prepared",
        reference=reimbursement_request.sap_policy_reference or "",
        generated_at=reimbursement_request.sap_policy_generated_at,
        generated_by_user_id=actor.id,
        payload=reimbursement_request.sap_policy_payload or {},
    )


def _ensure_request_editable(reimbursement_request: ReimbursementRequest) -> None:
    if not is_request_editable(reimbursement_request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": "Requests can only be edited while draft or in correction.",
            },
        )


def _active_request_currency(reimbursement_request: ReimbursementRequest) -> str:
    currencies = {
        expense.currency.upper()
        for expense in reimbursement_request.expenses
        if expense.status not in {ExpenseStatus.removed, ExpenseStatus.rejected}
        and expense.removed_at is None
    }
    if len(currencies) == 1:
        return currencies.pop()
    if not currencies:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "NO_PAYABLE_EXPENSES",
                "message": "The request does not have active expenses to pay",
            },
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "MULTI_CURRENCY_REQUEST",
            "message": "Payment recording requires one currency per request",
            "currencies": sorted(currencies),
        },
    )

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.business_rule import BusinessRule
from app.models.cfdi_validation import CfdiValidation
from app.models.expense import Expense, ExpenseStatus
from app.models.payment import Payment, PaymentStatus
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.store import Store, StoreUserAssignment
from app.models.user import User, UserRole
from app.services.automation_review import build_automated_review
from app.services.business_rules import ensure_default_business_rules
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.request_editability import is_request_editable
from app.services.sap_policy import SapPolicyPreparationError, prepare_sap_policy_placeholder
from app.services.security import hash_password
from app.services.storage import StorageService
from app.services.workflow import WorkflowTransitionError, transition_reimbursement_request

router = APIRouter()

HUD_STORE_CODE = "HUD-001"
HUD_PERIOD_NAME = "HUD Agosto 2026"
HUD_EMAIL_DOMAIN = "hud.smolbox.example.com"
HUD_DEMO_PASSWORD = "hud-password"

DEMO_RECEIPT_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"

BULK_DEMO_PROFILES = [
    {"name": "draft_missing_evidence", "status": ReimbursementRequestStatus.draft},
    {"name": "draft_ready", "status": ReimbursementRequestStatus.draft},
    {"name": "submitted", "status": ReimbursementRequestStatus.submitted},
    {"name": "authorization_review", "status": ReimbursementRequestStatus.authorization_review},
    {"name": "authorized", "status": ReimbursementRequestStatus.authorized},
    {"name": "under_accounting_review", "status": ReimbursementRequestStatus.under_accounting_review},
    {"name": "accounting_reviewed", "status": ReimbursementRequestStatus.accounting_reviewed},
    {"name": "accounting_manager_review", "status": ReimbursementRequestStatus.accounting_manager_review},
    {"name": "accounting_manager_approved", "status": ReimbursementRequestStatus.accounting_manager_approved},
    {"name": "treasury_review", "status": ReimbursementRequestStatus.treasury_review},
    {"name": "direction_review", "status": ReimbursementRequestStatus.direction_review},
    {"name": "direction_approved", "status": ReimbursementRequestStatus.direction_approved},
    {"name": "approved_for_payment", "status": ReimbursementRequestStatus.approved_for_payment},
    {"name": "paid", "status": ReimbursementRequestStatus.paid},
    {"name": "correction_required", "status": ReimbursementRequestStatus.correction_required},
]

DEMO_USERS = {
    UserRole.store: ("hud.store@hud.smolbox.example.com", "HUD Usuario Tienda"),
    UserRole.authorizer: ("hud.authorizer@hud.smolbox.example.com", "HUD Usuario Autorizacion"),
    UserRole.accountant: ("hud.accountant@hud.smolbox.example.com", "HUD Usuario Contador"),
    UserRole.accounting_manager: (
        "hud.accounting.manager@hud.smolbox.example.com",
        "HUD Gerente Contabilidad",
    ),
    UserRole.treasury: ("hud.treasury@hud.smolbox.example.com", "HUD Usuario Tesoreria"),
    UserRole.director: ("hud.director@hud.smolbox.example.com", "HUD Usuario Direccion"),
    UserRole.admin: ("hud.admin@hud.smolbox.example.com", "HUD Usuario Admin"),
}


class HudStoreCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    contact_email: str | None = Field(default=None, max_length=255)
    assigned_accountant: str | None = Field(default=None, max_length=160)

    @field_validator("code")
    @classmethod
    def normalize_hud_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not code.startswith("HUD-"):
            raise ValueError("HUD store codes must start with HUD-")
        return code

    @field_validator("contact_email")
    @classmethod
    def normalize_hud_contact_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        email = value.strip().lower()
        if email and not email.endswith(f"@{HUD_EMAIL_DOMAIN}"):
            raise ValueError(f"HUD store emails must end with @{HUD_EMAIL_DOMAIN}")
        return email or None


class HudUserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole

    @field_validator("email")
    @classmethod
    def normalize_hud_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not email.endswith(f"@{HUD_EMAIL_DOMAIN}"):
            raise ValueError(f"HUD user emails must end with @{HUD_EMAIL_DOMAIN}")
        return email


class HudAssignmentCreate(BaseModel):
    store_id: UUID
    user_id: UUID


class HudPaymentCreate(BaseModel):
    merchant: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=Decimal("0.00"))
    spent_on: date = date(2026, 8, 17)
    category: str | None = Field(default="hud_pago", max_length=120)
    description: str | None = None
    supplier_tax_id: str | None = Field(default="XAXX010101000", max_length=20)
    requires_authorization: bool = False
    create_receipt: bool = True
    keep_reported_total_balanced: bool = True


class HudScenarioExpenseCreate(BaseModel):
    merchant: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=Decimal("0.00"))
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    spent_on: date
    category: str | None = Field(default=None, max_length=120)
    description: str | None = None
    supplier_tax_id: str | None = Field(default="XAXX010101000", max_length=20)
    requires_authorization: bool = False
    create_receipt: bool = True

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("supplier_tax_id")
    @classmethod
    def normalize_supplier_tax_id(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class HudScenarioCreate(BaseModel):
    reset_existing: bool = False
    store_code: str = HUD_STORE_CODE
    store_name: str = "HUD Tienda Centro"
    contact_email: str | None = "hud.store@hud.smolbox.example.com"
    assigned_accountant: str | None = "HUD Usuario Contador"
    period_name: str = HUD_PERIOD_NAME
    starts_on: date = date(2026, 8, 1)
    ends_on: date = date(2026, 8, 31)
    reported_total: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    previous_reimbursement_starts_on: date | None = date(2026, 7, 1)
    previous_reimbursement_ends_on: date | None = date(2026, 7, 31)
    previous_reimbursement_amount: Decimal | None = Field(
        default=Decimal("1400.00"),
        ge=Decimal("0.00"),
    )
    notes: str | None = "Escenario local para probar el backend de Smolbox."
    expenses: list[HudScenarioExpenseCreate] | None = None

    @field_validator("store_code")
    @classmethod
    def normalize_store_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not code.startswith("HUD-"):
            raise ValueError("HUD scenario store codes must start with HUD-")
        return code

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        email = value.strip().lower()
        if email and not email.endswith(f"@{HUD_EMAIL_DOMAIN}"):
            raise ValueError(f"HUD scenario emails must end with @{HUD_EMAIL_DOMAIN}")
        return email or None

    @field_validator("period_name")
    @classmethod
    def validate_period_name(cls, value: str) -> str:
        name = value.strip()
        if not name.startswith("HUD "):
            raise ValueError("HUD scenario period names must start with HUD ")
        return name

    @model_validator(mode="after")
    def validate_dates(self) -> HudScenarioCreate:
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        if (
            self.previous_reimbursement_starts_on
            and self.previous_reimbursement_ends_on
            and self.previous_reimbursement_ends_on < self.previous_reimbursement_starts_on
        ):
            raise ValueError(
                "previous_reimbursement_ends_on must be on or after "
                "previous_reimbursement_starts_on"
            )
        return self


class HudBulkDemoCreate(BaseModel):
    reset_existing: bool = True
    request_count: int = Field(default=24, ge=1, le=80)
    store_count: int = Field(default=8, ge=1, le=30)


@router.get("/status")
def get_dev_hud_status(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    try:
        db.execute(select(1))
        ensure_default_business_rules(db)
        db.commit()
        counts = {
            "stores": _count(db, Store),
            "periods": _count(db, Period),
            "users": _count(db, User),
            "reimbursement_requests": _count(db, ReimbursementRequest),
            "expenses": _count(db, Expense),
            "attachments": _count(db, Attachment),
            "audit_events": _count(db, AuditLog),
            "cfdi_validations": _count(db, CfdiValidation),
            "business_rules": _count(db, BusinessRule),
        }
        database_status = "ok"
        api_status = "ok"
    except SQLAlchemyError:
        return {
            "api_status": "degraded",
            "database": "unavailable",
            "environment": settings.environment,
            "counts": {},
            "scenario": {"exists": False},
            "scenarios": [],
        }

    return {
        "api_status": api_status,
        "database": database_status,
        "environment": settings.environment,
        "counts": counts,
        "scenario": _scenario_payload(db, request_id),
        "scenarios": _scenario_list_payload(db),
        "workspace": _workspace_payload(db),
        "business_rules": _business_rules_payload(db),
    }


@router.post("/seed-bulk-demo", status_code=status.HTTP_201_CREATED)
def seed_dev_hud_bulk_demo(
    bulk_in: HudBulkDemoCreate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    if bulk_in.reset_existing:
        _delete_demo_dataset(db, storage)
        db.flush()

    created_request_ids: list[UUID] = []
    for index in range(bulk_in.request_count):
        scenario = _bulk_scenario(index, bulk_in.store_count)
        request = _ensure_demo_dataset(db, storage, scenario)
        _apply_bulk_demo_profile(db, storage, settings, request, index)
        created_request_ids.append(request.id)

    db.commit()
    active_request_id = created_request_ids[0] if created_request_ids else None
    scenarios = _scenario_list_payload(db)
    status_counts: dict[str, int] = {}
    for scenario in scenarios:
        status_counts[scenario["status"]] = status_counts.get(scenario["status"], 0) + 1

    return {
        "message": "HUD bulk demo data is ready",
        "created": len(created_request_ids),
        "status_counts": status_counts,
        "scenario": _scenario_payload(db, active_request_id),
        "scenarios": scenarios,
    }


@router.post("/seed-demo", status_code=status.HTTP_201_CREATED)
def seed_dev_hud_demo(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    scenario_in: HudScenarioCreate | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    scenario = scenario_in or HudScenarioCreate()
    if scenario.reset_existing:
        _delete_demo_dataset(db, storage)
        db.flush()
    _validate_seed_expense_dates(scenario)
    request = _ensure_demo_dataset(db, storage, scenario)
    request_id = request.id
    db.commit()

    return {
        "message": "HUD demo scenario is ready",
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/complete-cfdi")
def complete_dev_hud_cfdi(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )
    if not is_request_editable(request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": "Complete HUD CFDI evidence while the request is draft or in correction",
            },
        )

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    added = 0
    for expense in request.expenses:
        if expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected}:
            continue
        if expense.removed_at is not None:
            continue
        if _has_current_valid_cfdi(expense):
            continue
        _ensure_demo_cfdi(db, storage, expense, settings)
        added += 1

    if added:
        db.add(
            AuditLog(
                reimbursement_request_id=request.id,
                actor_type=AuditActorType.system,
                action="dev_hud_cfdi_completed",
                message=f"Created {added} synthetic CFDI validations for HUD testing.",
                event_payload={"added": added},
            )
        )
    request_id = request.id
    db.commit()

    return {
        "message": "HUD CFDI evidence completed",
        "cfdi_added": added,
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/automated-review")
def run_dev_hud_automated_review(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )

    summary = summarize_reimbursement_request(request)
    review = build_automated_review(request, summary)
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_type=AuditActorType.system,
            action="dev_hud_automated_review_completed",
            message="HUD automatic validation flow completed.",
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
    request_id = request.id
    db.commit()

    return {
        "message": "HUD automated review completed",
        "review": review.model_dump(mode="json"),
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/authorize-expenses")
def authorize_dev_hud_expenses(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )
    if request.status != ReimbursementRequestStatus.authorization_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_IN_AUTHORIZATION_REVIEW",
                "message": "Move the HUD request to authorization review first",
            },
        )

    actor = _hud_actor(db, UserRole.authorizer)
    authorized = 0
    for expense in request.expenses:
        if expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected} or expense.removed_at is not None:
            continue
        if not expense.requires_authorization or expense.authorized_at is not None:
            continue
        expense.authorized_at = datetime.now(UTC)
        expense.authorized_by_user_id = actor.id
        expense.authorization_note = "HUD authorization approved."
        expense.status = ExpenseStatus.approved
        authorized += 1
        db.add(
            AuditLog(
                reimbursement_request_id=request.id,
                expense_id=expense.id,
                actor_user_id=actor.id,
                actor_type=AuditActorType.user,
                action="dev_hud_expense_authorized",
                message="HUD expense authorization approved.",
                event_payload={"actor_role": actor.role.value},
            )
        )

    request_id = request.id
    db.commit()

    return {
        "message": "HUD expenses authorized",
        "authorized": authorized,
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/reject-authorization-expense")
def reject_dev_hud_authorization_expense(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )
    if request.status != ReimbursementRequestStatus.authorization_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_IN_AUTHORIZATION_REVIEW",
                "message": "Move the HUD request to authorization review first",
            },
        )

    actor = _hud_actor(db, UserRole.authorizer)
    expense = next(
        (
            item
            for item in request.expenses
            if item.requires_authorization
            and item.authorized_at is None
            and item.status not in {ExpenseStatus.removed, ExpenseStatus.rejected}
            and item.removed_at is None
        ),
        None,
    )
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "NO_PENDING_AUTHORIZATION_EXPENSE",
                "message": "No pending authorization expense is available to reject",
            },
        )

    expense.status = ExpenseStatus.rejected
    expense.authorization_note = "HUD authorization rejected for this product."
    request.reported_total = _active_expense_total(request)
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="dev_hud_expense_authorization_rejected",
            message=expense.authorization_note,
            event_payload={
                "actor_role": actor.role.value,
                "reported_total": str(request.reported_total),
            },
        )
    )

    request_id = request.id
    db.commit()

    return {
        "message": "HUD expense authorization rejected",
        "rejected_expense_id": expense.id,
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/prepare-sap-policy")
def prepare_dev_hud_sap_policy(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )

    actor = _hud_actor(db, UserRole.accountant)
    try:
        payload = prepare_sap_policy_placeholder(request, actor=actor)
    except SapPolicyPreparationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SAP_POLICY_NOT_READY", "message": str(exc)},
        ) from exc

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="dev_hud_sap_policy_prepared",
            message="HUD SAP policy placeholder prepared.",
            event_payload={"reference": request.sap_policy_reference, "payload": payload},
        )
    )
    request_id = request.id
    db.commit()

    return {
        "message": "HUD SAP policy placeholder prepared",
        "reference": request.sap_policy_reference,
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/transition/{target_status}")
def transition_dev_hud_request(
    target_status: ReimbursementRequestStatus,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )

    actor = _actor_for_transition(db, request.status, target_status)
    summary = summarize_reimbursement_request(request)
    try:
        from_status, to_status = transition_reimbursement_request(
            request,
            actor=actor,
            target_status=target_status,
            summary=summary,
        )
    except WorkflowTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_WORKFLOW_TRANSITION", "message": str(exc)},
        ) from exc

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="dev_hud_request_status_changed",
            from_status=from_status.value,
            to_status=to_status.value,
            message=f"HUD moved request to {to_status.value}.",
            event_payload={"actor_role": actor.role.value},
        )
    )
    request_id = request.id
    actor_payload = {"id": actor.id, "email": actor.email, "role": actor.role.value}
    db.commit()

    return {
        "message": "HUD request transitioned",
        "from_status": from_status.value,
        "to_status": to_status.value,
        "actor": actor_payload,
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/reset-demo")
def reset_dev_hud_demo(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    deleted = _delete_demo_dataset(db, storage)
    db.commit()

    return {
        "message": "HUD demo data deleted",
        "deleted": deleted,
        "scenario": {"exists": False},
        "scenarios": [],
    }


@router.post("/stores", status_code=status.HTTP_201_CREATED)
def create_dev_hud_store(
    store_in: HudStoreCreate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    store = Store(**store_in.model_dump())
    db.add(store)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_STORE_CODE", "message": "Store code already exists"},
        ) from exc
    db.refresh(store)
    return {"message": "HUD store created", "store": _store_payload(store)}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_dev_hud_user(
    user_in: HudUserCreate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    user = User(
        **user_in.model_dump(),
        is_active=True,
        password_hash=hash_password(HUD_DEMO_PASSWORD),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_USER_EMAIL", "message": "User email already exists"},
        ) from exc
    db.refresh(user)
    return {"message": "HUD user created", "user": _user_payload(user)}


@router.post("/assign-user")
def assign_dev_hud_user(
    assignment_in: HudAssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    store = db.get(Store, assignment_in.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    user = db.get(User, assignment_in.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INACTIVE_USER", "message": "Cannot assign an inactive user"},
        )

    if user.role == UserRole.store:
        store.contact_email = user.email
        assigned_field = "contact_email"
    elif user.role == UserRole.accountant:
        store.assigned_accountant = user.full_name
        assigned_field = "assigned_accountant"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "UNSUPPORTED_HUD_ASSIGNMENT",
                "message": "HUD assignment supports store and accountant users for now",
            },
        )

    db.commit()
    db.refresh(store)
    return {
        "message": "HUD user assigned to store",
        "assigned_field": assigned_field,
        "store": _store_payload(store),
        "user": _user_payload(user),
    }


@router.post("/payments", status_code=status.HTTP_201_CREATED)
def create_dev_hud_payment(
    payment_in: HudPaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: UUID | None = None,
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )
    if request.status not in {
        ReimbursementRequestStatus.draft,
        ReimbursementRequestStatus.correction_required,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": "Create HUD payments while the request is draft or in correction",
            },
        )
    if not request.period.starts_on <= payment_in.spent_on <= request.period.ends_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "PAYMENT_OUTSIDE_PERIOD",
                "message": "Payment date is outside the HUD reimbursement period",
            },
        )

    expense = Expense(
        period_id=request.period_id,
        reimbursement_request_id=request.id,
        merchant=payment_in.merchant,
        amount=payment_in.amount,
        currency="MXN",
        spent_on=payment_in.spent_on,
        category=payment_in.category,
        description=payment_in.description,
        supplier_tax_id=payment_in.supplier_tax_id,
        requires_authorization=payment_in.requires_authorization,
    )
    request.expenses.append(expense)
    db.add(expense)
    db.flush()

    if payment_in.create_receipt:
        storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
        _ensure_demo_receipt(db, storage, expense)

    if payment_in.keep_reported_total_balanced:
        request.reported_total = (request.reported_total or Decimal("0.00")) + payment_in.amount

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id,
            actor_type=AuditActorType.system,
            action="dev_hud_payment_created",
            message=f"HUD payment created for {expense.merchant}.",
            event_payload={
                "amount": str(expense.amount),
                "spent_on": expense.spent_on.isoformat(),
                "reported_total_adjusted": payment_in.keep_reported_total_balanced,
            },
        )
    )
    request_id = request.id
    expense_id = expense.id
    db.commit()

    return {
        "message": "HUD payment created",
        "expense_id": expense_id,
        "scenario": _scenario_payload(db, request_id),
    }


def _ensure_dev_hud_enabled(settings: Settings) -> None:
    if settings.environment.lower() == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def _bulk_scenario(index: int, store_count: int) -> HudScenarioCreate:
    store_number = (index % store_count) + 1
    period_index = index // store_count
    starts_on, ends_on = _bulk_period_dates(period_index)
    profile = BULK_DEMO_PROFILES[index % len(BULK_DEMO_PROFILES)]
    missing_evidence = profile["name"] == "draft_missing_evidence"
    amounts = [
        Decimal("420.00") + Decimal(index * 3),
        Decimal("180.50") + Decimal(store_number),
        Decimal("95.25") + Decimal(period_index),
    ]
    reported_total = sum(amounts, Decimal("0.00"))
    if missing_evidence:
        reported_total += Decimal("17.00")

    return HudScenarioCreate(
        reset_existing=False,
        store_code=f"HUD-BULK-{store_number:03d}",
        store_name=f"HUD Sucursal Demo {store_number:03d}",
        contact_email=f"hud.bulk.{store_number:03d}@{HUD_EMAIL_DOMAIN}",
        assigned_accountant="HUD Usuario Contador",
        period_name=f"HUD Bulk {starts_on.strftime('%Y-%m')}",
        starts_on=starts_on,
        ends_on=ends_on,
        reported_total=reported_total.quantize(Decimal("0.01")),
        previous_reimbursement_starts_on=starts_on - timedelta(days=31),
        previous_reimbursement_ends_on=starts_on - timedelta(days=1),
        previous_reimbursement_amount=(reported_total - Decimal("35.00")).quantize(Decimal("0.01")),
        notes=f"Escenario masivo HUD: {profile['name']}.",
        expenses=[
            HudScenarioExpenseCreate(
                merchant=f"HUD Papeleria Demo {index + 1}",
                amount=amounts[0],
                spent_on=starts_on + timedelta(days=4),
                category="papeleria",
                description="Material operativo demo.",
                supplier_tax_id="XAXX010101000",
                create_receipt=not missing_evidence,
            ),
            HudScenarioExpenseCreate(
                merchant=f"HUD Taxi Autorizacion {index + 1}",
                amount=amounts[1],
                spent_on=starts_on + timedelta(days=9),
                category="transporte",
                description="Traslado que requiere autorizacion demo.",
                supplier_tax_id="XEXX010101000",
                requires_authorization=True,
                create_receipt=True,
            ),
            HudScenarioExpenseCreate(
                merchant=f"HUD Cafeteria Demo {index + 1}",
                amount=amounts[2],
                spent_on=starts_on + timedelta(days=14),
                category="alimentos",
                description="Consumo operativo demo.",
                supplier_tax_id="XAXX010101000",
                create_receipt=True,
            ),
        ],
    )


def _bulk_period_dates(period_index: int) -> tuple[date, date]:
    month_number = 8 + period_index
    year = 2026 + ((month_number - 1) // 12)
    month = ((month_number - 1) % 12) + 1
    starts_on = date(year, month, 1)
    next_month_year = year + (1 if month == 12 else 0)
    next_month = 1 if month == 12 else month + 1
    ends_on = date(next_month_year, next_month, 1) - timedelta(days=1)
    return starts_on, ends_on


def _apply_bulk_demo_profile(
    db: Session,
    storage: StorageService,
    settings: Settings,
    request: ReimbursementRequest,
    index: int,
) -> None:
    profile = BULK_DEMO_PROFILES[index % len(BULK_DEMO_PROFILES)]
    target_status = profile["status"]
    complete_evidence = profile["name"] != "draft_missing_evidence"
    if complete_evidence:
        for expense in request.expenses:
            _ensure_demo_receipt(db, storage, expense)
            _ensure_demo_cfdi(db, storage, expense, settings)

    if target_status not in {
        ReimbursementRequestStatus.draft,
        ReimbursementRequestStatus.submitted,
        ReimbursementRequestStatus.authorization_review,
        ReimbursementRequestStatus.correction_required,
    }:
        _authorize_required_demo_expenses(request, _hud_actor(db, UserRole.authorizer))

    if target_status in {
        ReimbursementRequestStatus.accounting_manager_review,
        ReimbursementRequestStatus.accounting_manager_approved,
        ReimbursementRequestStatus.treasury_review,
        ReimbursementRequestStatus.direction_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    }:
        request.status = ReimbursementRequestStatus.accounting_reviewed
        prepare_sap_policy_placeholder(
            request,
            actor=_hud_actor(db, UserRole.accountant),
            reference=f"HUD-BULK-SAP-{index + 1:03d}",
        )

    _set_demo_request_status(request, target_status)
    if target_status == ReimbursementRequestStatus.paid:
        _ensure_demo_paid_payment(db, request, _hud_actor(db, UserRole.treasury), index)

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=_hud_actor(db, UserRole.admin).id,
            actor_type=AuditActorType.user,
            action="dev_hud_bulk_profile_applied",
            from_status=None,
            to_status=request.status.value,
            message=f"HUD bulk profile applied: {profile['name']}.",
            event_payload={"profile": profile["name"], "index": index},
        )
    )


def _authorize_required_demo_expenses(request: ReimbursementRequest, actor: User) -> None:
    for expense in request.expenses:
        if not expense.requires_authorization:
            continue
        if expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected}:
            continue
        expense.authorized_at = datetime.now(UTC)
        expense.authorized_by_user_id = actor.id
        expense.authorization_note = "Autorizado por perfil demo masivo."
        expense.status = ExpenseStatus.approved


def _set_demo_request_status(
    request: ReimbursementRequest,
    target_status: ReimbursementRequestStatus,
) -> None:
    now = datetime.now(UTC)
    request.status = target_status
    if target_status not in {ReimbursementRequestStatus.draft, ReimbursementRequestStatus.correction_required}:
        request.submitted_at = request.submitted_at or now
    if target_status in {
        ReimbursementRequestStatus.authorized,
        ReimbursementRequestStatus.under_accounting_review,
        ReimbursementRequestStatus.accounting_reviewed,
        ReimbursementRequestStatus.accounting_manager_review,
        ReimbursementRequestStatus.accounting_manager_approved,
        ReimbursementRequestStatus.treasury_review,
        ReimbursementRequestStatus.direction_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    }:
        request.authorization_reviewed_at = request.authorization_reviewed_at or now
    if target_status in {
        ReimbursementRequestStatus.accounting_reviewed,
        ReimbursementRequestStatus.accounting_manager_review,
        ReimbursementRequestStatus.accounting_manager_approved,
        ReimbursementRequestStatus.treasury_review,
        ReimbursementRequestStatus.direction_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    }:
        request.accounting_reviewed_at = request.accounting_reviewed_at or now
    if target_status in {
        ReimbursementRequestStatus.accounting_manager_approved,
        ReimbursementRequestStatus.treasury_review,
        ReimbursementRequestStatus.direction_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    }:
        request.accounting_manager_reviewed_at = request.accounting_manager_reviewed_at or now
    if target_status in {
        ReimbursementRequestStatus.direction_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    }:
        request.treasury_reviewed_at = request.treasury_reviewed_at or now
    if target_status in {
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    }:
        request.direction_reviewed_at = request.direction_reviewed_at or now
        request.direction_approved_at = request.direction_approved_at or now
    if target_status in {
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    }:
        request.approved_for_payment_at = request.approved_for_payment_at or now
    if target_status == ReimbursementRequestStatus.paid:
        request.paid_at = request.paid_at or now
    if target_status == ReimbursementRequestStatus.correction_required:
        request.correction_requested_at = request.correction_requested_at or now
        request.correction_reason = request.correction_reason or "Correccion requerida por perfil demo."


def _ensure_demo_paid_payment(
    db: Session,
    request: ReimbursementRequest,
    actor: User,
    index: int,
) -> None:
    existing_payment = db.scalar(
        select(Payment).where(
            Payment.reimbursement_request_id == request.id,
            Payment.status == PaymentStatus.paid,
        )
    )
    if existing_payment is not None:
        return

    payment = Payment(
        reimbursement_request_id=request.id,
        amount=_active_expense_total(request),
        currency="MXN",
        payment_method="transfer",
        reference=f"HUD-BULK-PAGO-{index + 1:03d}",
        note="Pago creado por perfil demo masivo.",
        status=PaymentStatus.paid,
        paid_at=request.paid_at or datetime.now(UTC),
        paid_by_user_id=actor.id,
    )
    db.add(payment)


def _ensure_demo_dataset(
    db: Session,
    storage: StorageService,
    scenario: HudScenarioCreate,
) -> ReimbursementRequest:
    users = {role: _get_or_create_user(db, role) for role in DEMO_USERS}
    store = _get_or_create_store(db, scenario)
    period = _get_or_create_period(db, scenario)
    for role, user in users.items():
        _ensure_store_user_assignment(db, store, user, role)
    request = _get_or_create_request(db, store, period, scenario)
    if not request.expenses:
        scenario_expenses = _scenario_expenses(scenario)
        request.expenses.extend(_create_demo_expenses(db, request, scenario_expenses))
        db.flush()
        for expense, expense_in in zip(request.expenses, scenario_expenses, strict=False):
            if expense_in.create_receipt:
                _ensure_demo_receipt(db, storage, expense)
    else:
        for expense in request.expenses:
            _ensure_demo_receipt(db, storage, expense)

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=users[UserRole.admin].id,
            actor_type=AuditActorType.user,
            action="dev_hud_seeded",
            message="HUD demo scenario seeded.",
            event_payload={"store_code": store.code, "period_name": period.name},
        )
    )
    return request


def _get_or_create_user(db: Session, role: UserRole) -> User:
    email, full_name = DEMO_USERS[role]
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        user.full_name = full_name
        user.role = role
        user.is_active = True
        user.password_hash = hash_password(HUD_DEMO_PASSWORD)
        return user

    user = User(
        email=email,
        full_name=full_name,
        role=role,
        is_active=True,
        password_hash=hash_password(HUD_DEMO_PASSWORD),
    )
    db.add(user)
    db.flush()
    return user


def _get_or_create_store(db: Session, scenario: HudScenarioCreate) -> Store:
    store = db.scalar(select(Store).where(Store.code == scenario.store_code))
    if store is not None:
        store.name = scenario.store_name
        store.contact_email = scenario.contact_email
        store.assigned_accountant = scenario.assigned_accountant
        return store

    store = Store(
        code=scenario.store_code,
        name=scenario.store_name,
        contact_email=scenario.contact_email,
        assigned_accountant=scenario.assigned_accountant,
    )
    db.add(store)
    db.flush()
    return store


def _get_or_create_period(db: Session, scenario: HudScenarioCreate) -> Period:
    period = db.scalar(select(Period).where(Period.name == scenario.period_name))
    if period is not None:
        period.starts_on = scenario.starts_on
        period.ends_on = scenario.ends_on
        period.status = PeriodStatus.open
        return period

    period = Period(
        name=scenario.period_name,
        starts_on=scenario.starts_on,
        ends_on=scenario.ends_on,
        status=PeriodStatus.open,
    )
    db.add(period)
    db.flush()
    return period


def _ensure_store_user_assignment(
    db: Session,
    store: Store,
    user: User,
    role: UserRole,
) -> StoreUserAssignment:
    assignment = db.scalar(
        select(StoreUserAssignment).where(
            StoreUserAssignment.store_id == store.id,
            StoreUserAssignment.user_id == user.id,
        )
    )
    if assignment is not None:
        assignment.role = role
        assignment.is_active = True
        return assignment

    assignment = StoreUserAssignment(
        store_id=store.id,
        user_id=user.id,
        role=role,
        is_active=True,
    )
    db.add(assignment)
    db.flush()
    return assignment


def _get_or_create_request(
    db: Session,
    store: Store,
    period: Period,
    scenario: HudScenarioCreate,
) -> ReimbursementRequest:
    request = db.scalar(
        select(ReimbursementRequest)
        .options(selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments))
        .where(
            ReimbursementRequest.store_id == store.id,
            ReimbursementRequest.period_id == period.id,
        )
    )
    if request is not None:
        request.reported_total = _scenario_reported_total(scenario)
        request.previous_reimbursement_starts_on = scenario.previous_reimbursement_starts_on
        request.previous_reimbursement_ends_on = scenario.previous_reimbursement_ends_on
        request.previous_reimbursement_amount = scenario.previous_reimbursement_amount
        request.notes = scenario.notes
        return request

    request = ReimbursementRequest(
        store_id=store.id,
        period_id=period.id,
        reported_total=_scenario_reported_total(scenario),
        previous_reimbursement_starts_on=scenario.previous_reimbursement_starts_on,
        previous_reimbursement_ends_on=scenario.previous_reimbursement_ends_on,
        previous_reimbursement_amount=scenario.previous_reimbursement_amount,
        notes=scenario.notes,
    )
    db.add(request)
    db.flush()
    return request


def _create_demo_expenses(
    db: Session,
    request: ReimbursementRequest,
    scenario_expenses: list[HudScenarioExpenseCreate],
) -> list[Expense]:
    expenses = [
        Expense(
            period_id=request.period_id,
            reimbursement_request_id=request.id,
            merchant=expense_in.merchant,
            amount=expense_in.amount,
            currency=expense_in.currency,
            spent_on=expense_in.spent_on,
            category=expense_in.category,
            description=expense_in.description,
            supplier_tax_id=expense_in.supplier_tax_id,
            requires_authorization=expense_in.requires_authorization,
        )
        for expense_in in scenario_expenses
    ]
    for expense in expenses:
        db.add(expense)
    return expenses


def _scenario_expenses(scenario: HudScenarioCreate) -> list[HudScenarioExpenseCreate]:
    if scenario.expenses:
        return scenario.expenses
    return [
        HudScenarioExpenseCreate(
            merchant="HUD Papeleria Uno",
            amount=Decimal("1000.00"),
            currency="MXN",
            spent_on=date(2026, 8, 10),
            category="papeleria",
            description="Hojas, toner y material de oficina.",
            supplier_tax_id="XAXX010101000",
        ),
        HudScenarioExpenseCreate(
            merchant="HUD Taxi Demo",
            amount=Decimal("500.00"),
            currency="MXN",
            spent_on=date(2026, 8, 11),
            category="transporte",
            description="Traslado local operativo.",
            supplier_tax_id="XEXX010101000",
            requires_authorization=True,
        ),
    ]


def _scenario_reported_total(scenario: HudScenarioCreate) -> Decimal:
    if scenario.reported_total is not None:
        return scenario.reported_total
    total = sum((expense.amount for expense in _scenario_expenses(scenario)), Decimal("0.00"))
    return total.quantize(Decimal("0.01"))


def _active_expense_total(request: ReimbursementRequest) -> Decimal:
    total = Decimal("0.00")
    for expense in request.expenses:
        if expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected}:
            continue
        if expense.removed_at is not None:
            continue
        total += Decimal(expense.amount)
    return total.quantize(Decimal("0.01"))


def _validate_seed_expense_dates(scenario: HudScenarioCreate) -> None:
    invalid_rows = [
        expense.merchant
        for expense in _scenario_expenses(scenario)
        if expense.spent_on < scenario.starts_on or expense.spent_on > scenario.ends_on
    ]
    if invalid_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "HUD_EXPENSE_OUTSIDE_PERIOD",
                "message": "Scenario expenses must be inside the reimbursement period.",
                "expenses": invalid_rows,
            },
        )


def _ensure_demo_receipt(db: Session, storage: StorageService, expense: Expense) -> None:
    if _has_attachment_type(expense, AttachmentType.receipt):
        return

    stored = storage.save_bytes(
        DEMO_RECEIPT_BYTES,
        filename=f"{expense.merchant.lower().replace(' ', '-')}-ticket.pdf",
        expense_id=expense.id,
    )
    attachment = Attachment(
        expense_id=expense.id,
        attachment_type=AttachmentType.receipt,
        filename=stored.filename,
        content_type="application/pdf",
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    expense.attachments.append(attachment)
    db.add(attachment)


def _ensure_demo_cfdi(
    db: Session,
    storage: StorageService,
    expense: Expense,
    settings: Settings,
) -> None:
    cfdi_uuid = str(uuid5(NAMESPACE_URL, f"smolbox-hud-cfdi:{expense.id}")).upper()
    issuer_rfc = expense.supplier_tax_id or "XAXX010101000"
    receiver_rfc = settings.cfdi_receiver_rfc or "BBB010101BBB"
    issued_at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    content = _demo_cfdi_xml(
        uuid=cfdi_uuid,
        issuer_rfc=issuer_rfc,
        receiver_rfc=receiver_rfc,
        amount=expense.amount,
        currency=expense.currency,
        issued_at=issued_at,
    )
    stored = storage.save_bytes(
        content,
        filename=f"{expense.merchant.lower().replace(' ', '-')}-cfdi.xml",
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
    expense.attachments.append(attachment)
    db.add(attachment)
    db.flush()

    db.execute(
        update(CfdiValidation)
        .where(CfdiValidation.expense_id == expense.id, CfdiValidation.is_current.is_(True))
        .values(is_current=False)
    )
    validation = CfdiValidation(
        expense_id=expense.id,
        attachment_id=attachment.id,
        uuid=cfdi_uuid,
        issuer_rfc=issuer_rfc,
        receiver_rfc=receiver_rfc,
        total=expense.amount,
        currency=expense.currency,
        issued_at=issued_at,
        is_valid=True,
        issues=[],
        checksum_sha256=stored.checksum_sha256,
        validator_version="dev-hud",
        is_current=True,
    )
    expense.cfdi_validations.append(validation)
    db.add(validation)
    expense.cfdi_uuid = cfdi_uuid
    expense.cfdi_issuer_rfc = issuer_rfc
    expense.cfdi_receiver_rfc = receiver_rfc
    expense.cfdi_total = expense.amount
    expense.cfdi_currency = expense.currency


def _demo_cfdi_xml(
    *,
    uuid: str,
    issuer_rfc: str,
    receiver_rfc: str,
    amount: Decimal,
    currency: str,
    issued_at: datetime,
) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
  xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0"
  Fecha="{issued_at.strftime("%Y-%m-%dT%H:%M:%S")}"
  Total="{amount}"
  Moneda="{currency}">
  <cfdi:Emisor Rfc="{issuer_rfc}" Nombre="HUD PROVEEDOR"/>
  <cfdi:Receptor Rfc="{receiver_rfc}" Nombre="SMOLBOX HUD"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
""".encode()


def _load_demo_request(db: Session, request_id: UUID | None = None) -> ReimbursementRequest | None:
    statement = (
        select(ReimbursementRequest)
        .join(Store)
        .join(Period)
        .options(
            selectinload(ReimbursementRequest.store),
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
            selectinload(ReimbursementRequest.audit_events),
        )
        .order_by(ReimbursementRequest.created_at.desc())
    )
    statement = statement.where(Store.code.like("HUD-%"), Period.name.like("HUD %"))
    if request_id is not None:
        statement = statement.where(ReimbursementRequest.id == request_id)
    return db.scalars(statement).first()


def _scenario_payload(db: Session, request_id: UUID | None = None) -> dict[str, Any]:
    request = _load_demo_request(db, request_id)
    if request is None:
        return {"exists": False}

    summary = summarize_reimbursement_request(request)
    users = {
        role.value: _user_payload(db.scalar(select(User).where(User.email == email)))
        for role, (email, _) in DEMO_USERS.items()
    }
    audit_events = sorted(request.audit_events, key=lambda event: event.created_at, reverse=True)

    return {
        "exists": True,
        "request_id": request.id,
        "status": request.status.value,
        "store_id": request.store_id,
        "store_code": request.store.code,
        "store_name": request.store.name,
        "period_id": request.period_id,
        "period_name": request.period.name,
        "sap_policy": {
            "is_prepared": request.sap_policy_generated_at is not None,
            "reference": request.sap_policy_reference,
            "generated_at": request.sap_policy_generated_at,
            "generated_by_user_id": request.sap_policy_generated_by_user_id,
            "payload": request.sap_policy_payload,
        },
        "users": users,
        "summary": summary.model_dump(mode="json"),
        "expenses": [_expense_payload(expense) for expense in request.expenses],
        "audit_events": [
            {
                "id": event.id,
                "action": event.action,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "message": event.message,
                "created_at": event.created_at,
            }
            for event in audit_events[:10]
        ],
    }


def _scenario_list_payload(db: Session) -> list[dict[str, Any]]:
    statement = (
        select(ReimbursementRequest)
        .join(Store)
        .join(Period)
        .options(
            selectinload(ReimbursementRequest.store),
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        )
        .where(Store.code.like("HUD-%"), Period.name.like("HUD %"))
        .order_by(ReimbursementRequest.created_at.desc())
        .limit(100)
    )
    return [_scenario_list_item_payload(request) for request in db.scalars(statement)]


def _scenario_list_item_payload(request: ReimbursementRequest) -> dict[str, Any]:
    summary = summarize_reimbursement_request(request).model_dump(mode="json")
    return {
        "request_id": request.id,
        "status": request.status.value,
        "store_code": request.store.code,
        "store_name": request.store.name,
        "period_name": request.period.name,
        "reported_total": summary["reported_total"],
        "calculated_total": summary["calculated_total"],
        "difference": summary["difference"],
        "expense_count": summary["expense_count"],
        "issue_count": len(summary["issues"]),
        "authorization_pending_count": len(summary["missing_authorization_expense_ids"]),
        "sap_policy_prepared": request.sap_policy_generated_at is not None,
        "created_at": request.created_at,
    }


def _workspace_payload(db: Session) -> dict[str, Any]:
    stores = list(db.scalars(select(Store).order_by(Store.code).limit(100)))
    users = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(100)))
    return {
        "stores": [_store_payload(store) for store in stores],
        "users": [_user_payload(user) for user in users],
    }


def _business_rules_payload(db: Session) -> list[dict[str, Any]]:
    ensure_default_business_rules(db)
    return [
        {
            "id": rule.id,
            "code": rule.code,
            "name": rule.name,
            "description": rule.description,
            "value": rule.value,
            "is_active": rule.is_active,
        }
        for rule in db.scalars(select(BusinessRule).order_by(BusinessRule.code))
    ]


def _store_payload(store: Store) -> dict[str, Any]:
    return {
        "id": store.id,
        "code": store.code,
        "name": store.name,
        "contact_email": store.contact_email,
        "assigned_accountant": store.assigned_accountant,
    }


def _user_payload(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }


def _expense_payload(expense: Expense) -> dict[str, Any]:
    return {
        "id": expense.id,
        "merchant": expense.merchant,
        "amount": expense.amount,
        "currency": expense.currency,
        "spent_on": expense.spent_on,
        "category": expense.category,
        "status": expense.status.value,
        "has_receipt": _has_attachment_type(expense, AttachmentType.receipt),
        "has_cfdi_xml": _has_attachment_type(expense, AttachmentType.cfdi_xml),
        "receipt_attachment_id": _attachment_id(expense, AttachmentType.receipt),
        "cfdi_attachment_id": _attachment_id(expense, AttachmentType.cfdi_xml),
        "has_current_valid_cfdi": _has_current_valid_cfdi(expense),
        "requires_authorization": expense.requires_authorization,
        "is_authorized": expense.authorized_at is not None,
        "authorization_note": expense.authorization_note,
        "review_note": expense.review_note,
        "is_removed": expense.status == ExpenseStatus.removed or expense.removed_at is not None,
        "is_rejected": expense.status == ExpenseStatus.rejected,
        "removal_reason": expense.removal_reason,
    }


def _has_attachment_type(expense: Expense, attachment_type: AttachmentType) -> bool:
    return any(attachment.attachment_type == attachment_type for attachment in expense.attachments)


def _attachment_id(expense: Expense, attachment_type: AttachmentType) -> UUID | None:
    for attachment in expense.attachments:
        if attachment.attachment_type == attachment_type:
            return attachment.id
    return None


def _has_current_valid_cfdi(expense: Expense) -> bool:
    return any(
        validation.is_current and validation.is_valid
        for validation in expense.cfdi_validations
    )


def _actor_for_transition(
    db: Session,
    current_status: ReimbursementRequestStatus,
    target_status: ReimbursementRequestStatus,
) -> User:
    if target_status == ReimbursementRequestStatus.submitted:
        role = UserRole.store
    elif target_status in {
        ReimbursementRequestStatus.authorization_review,
        ReimbursementRequestStatus.authorized,
    }:
        role = UserRole.authorizer
    elif target_status in {
        ReimbursementRequestStatus.under_accounting_review,
        ReimbursementRequestStatus.accounting_reviewed,
        ReimbursementRequestStatus.accounting_approved,
    }:
        role = UserRole.accountant
    elif target_status in {
        ReimbursementRequestStatus.accounting_manager_review,
        ReimbursementRequestStatus.accounting_manager_approved,
    }:
        role = UserRole.accounting_manager
    elif target_status == ReimbursementRequestStatus.direction_approved:
        role = UserRole.director
    elif target_status in {
        ReimbursementRequestStatus.correction_required,
        ReimbursementRequestStatus.rejected,
    }:
        role = _review_role_for_status(current_status)
    else:
        role = UserRole.treasury

    return _hud_actor(db, role)


def _hud_actor(db: Session, role: UserRole) -> User:
    actor = db.scalar(select(User).where(User.email == DEMO_USERS[role][0]))
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "HUD_ACTOR_NOT_FOUND", "message": "Seed the HUD scenario first"},
        )
    return actor


def _review_role_for_status(status_value: ReimbursementRequestStatus) -> UserRole:
    if status_value == ReimbursementRequestStatus.authorization_review:
        return UserRole.authorizer
    if status_value == ReimbursementRequestStatus.accounting_manager_review:
        return UserRole.accounting_manager
    if status_value == ReimbursementRequestStatus.treasury_review:
        return UserRole.treasury
    if status_value == ReimbursementRequestStatus.direction_review:
        return UserRole.director
    return UserRole.accountant


def _delete_demo_dataset(db: Session, storage: StorageService) -> dict[str, int]:
    hud_user_ids = list(
        db.scalars(select(User.id).where(User.email.like(f"%@{HUD_EMAIL_DOMAIN}")))
    )
    hud_store_ids = list(db.scalars(select(Store.id).where(Store.code.like("HUD-%"))))
    hud_period_ids = list(db.scalars(select(Period.id).where(Period.name.like("HUD %"))))

    request_filters = []
    if hud_store_ids:
        request_filters.append(ReimbursementRequest.store_id.in_(hud_store_ids))
    if hud_period_ids:
        request_filters.append(ReimbursementRequest.period_id.in_(hud_period_ids))
    request_ids = list(
        db.scalars(
            select(ReimbursementRequest.id).where(or_(*request_filters))
            if request_filters
            else select(ReimbursementRequest.id).where(False)
        )
    )

    expense_filters = []
    if request_ids:
        expense_filters.append(Expense.reimbursement_request_id.in_(request_ids))
    if hud_period_ids:
        expense_filters.append(Expense.period_id.in_(hud_period_ids))
    expense_ids = list(
        db.scalars(
            select(Expense.id).where(or_(*expense_filters))
            if expense_filters
            else select(Expense.id).where(False)
        )
    )

    attachment_filters = []
    if request_ids:
        attachment_filters.append(Attachment.reimbursement_request_id.in_(request_ids))
    if expense_ids:
        attachment_filters.append(Attachment.expense_id.in_(expense_ids))
    attachments = list(
        db.scalars(
            select(Attachment).where(or_(*attachment_filters))
            if attachment_filters
            else select(Attachment).where(False)
        )
    )

    deleted = {
        "cfdi_validations": _delete_where(db, CfdiValidation, CfdiValidation.expense_id, expense_ids),
        "attachments": len(attachments),
        "audit_events": _delete_audit_events(db, request_ids, expense_ids, hud_user_ids),
        "store_user_assignments": _delete_store_user_assignments(
            db,
            hud_store_ids,
            hud_user_ids,
        ),
    }

    if attachments:
        db.execute(delete(Attachment).where(Attachment.id.in_([item.id for item in attachments])))
        for attachment in attachments:
            try:
                storage.delete(attachment.storage_path)
            except (OSError, ValueError):
                continue

    deleted.update(
        {
            "expenses": _delete_where(db, Expense, Expense.id, expense_ids),
            "reimbursement_requests": _delete_where(
                db,
                ReimbursementRequest,
                ReimbursementRequest.id,
                request_ids,
            ),
            "stores": _delete_where(db, Store, Store.id, hud_store_ids),
            "periods": _delete_where(db, Period, Period.id, hud_period_ids),
            "users": _delete_where(db, User, User.id, hud_user_ids),
        }
    )

    return deleted


def _delete_where(db: Session, model: type, column: Any, ids: list[UUID]) -> int:
    if not ids:
        return 0
    result = db.execute(delete(model).where(column.in_(ids)))
    return result.rowcount or 0


def _delete_audit_events(
    db: Session,
    request_ids: list[UUID],
    expense_ids: list[UUID],
    user_ids: list[UUID],
) -> int:
    filters = []
    if request_ids:
        filters.append(AuditLog.reimbursement_request_id.in_(request_ids))
    if expense_ids:
        filters.append(AuditLog.expense_id.in_(expense_ids))
    if user_ids:
        filters.append(AuditLog.actor_user_id.in_(user_ids))
    if not filters:
        return 0
    result = db.execute(delete(AuditLog).where(or_(*filters)))
    return result.rowcount or 0


def _delete_store_user_assignments(
    db: Session,
    store_ids: list[UUID],
    user_ids: list[UUID],
) -> int:
    filters = []
    if store_ids:
        filters.append(StoreUserAssignment.store_id.in_(store_ids))
    if user_ids:
        filters.append(StoreUserAssignment.user_id.in_(user_ids))
    if not filters:
        return 0
    result = db.execute(delete(StoreUserAssignment).where(or_(*filters)))
    return result.rowcount or 0

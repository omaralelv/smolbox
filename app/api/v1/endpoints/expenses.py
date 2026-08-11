from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest
from app.schemas.expense import ExpenseCreate, ExpenseRead

router = APIRouter()


@router.post("/", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    expense_in: ExpenseCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense_data = expense_in.model_dump()
    request_id = expense_data.get("reimbursement_request_id")

    if request_id is not None:
        reimbursement_request = db.get(ReimbursementRequest, request_id)
        if reimbursement_request is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reimbursement request not found",
            )
        if expense_data.get("period_id") is None:
            expense_data["period_id"] = reimbursement_request.period_id
        elif expense_data["period_id"] != reimbursement_request.period_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense period must match the reimbursement request period",
            )

    period = db.get(Period, expense_data["period_id"])
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERIOD_CLOSED", "message": "The reimbursement period is closed"},
        )
    if not period.starts_on <= expense_in.spent_on <= period.ends_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "EXPENSE_OUTSIDE_PERIOD",
                "message": "The expense date is outside the reimbursement period",
            },
        )

    expense = Expense(**expense_data)
    db.add(expense)
    db.flush()
    if expense.reimbursement_request_id is not None:
        db.add(
            AuditLog(
                reimbursement_request_id=expense.reimbursement_request_id,
                expense_id=expense.id,
                actor_type=AuditActorType.system,
                action="expense_created",
                message=f"Expense created for {expense.merchant}.",
                event_payload={
                    "amount": str(expense.amount),
                    "currency": expense.currency,
                    "category": expense.category,
                    "spent_on": expense.spent_on.isoformat(),
                },
            )
        )
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/", response_model=list[ExpenseRead])
def list_expenses(
    db: Annotated[Session, Depends(get_db)],
    period_id: UUID | None = None,
    reimbursement_request_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Expense]:
    statement = select(Expense).order_by(Expense.created_at.desc()).limit(limit).offset(offset)
    if period_id is not None:
        statement = statement.where(Expense.period_id == period_id)
    if reimbursement_request_id is not None:
        statement = statement.where(Expense.reimbursement_request_id == reimbursement_request_id)
    return list(db.scalars(statement))


@router.get("/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: UUID, db: Annotated[Session, Depends(get_db)]) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense

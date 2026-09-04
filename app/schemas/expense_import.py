from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.expense import ExpenseRead


class ExpenseImportErrorRead(BaseModel):
    row_number: int
    field: str
    message: str


class ExpenseImportResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: UUID
    imported_count: int
    dry_run: bool
    attachment_id: UUID | None = None
    expenses: list[ExpenseRead]
    errors: list[ExpenseImportErrorRead] = []

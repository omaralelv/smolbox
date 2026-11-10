from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.frontend import FrontendGastoCreate


class HistoricalExpenseCreate(FrontendGastoCreate):
    client_id: UUID = Field(alias="clientId")
    document_type: Literal["factura", "vale", "recibo"] = Field(alias="documentType")


class HistoricalEventCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    action: str = Field(min_length=1, max_length=80)
    field: str | None = Field(default=None, max_length=80)
    value: str | None = Field(default=None, max_length=2000)
    previous_value: str | None = Field(default=None, alias="previousValue", max_length=2000)
    label: str | None = Field(default=None, max_length=250)
    message: str | None = Field(default=None, max_length=4000)
    capture_id: UUID | None = Field(default=None, alias="captureId")


class HistoricalObservationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    note: str = Field(min_length=1, max_length=4000)


class HistoricalRegistration(BaseModel):
    expected_expense_ids: list[UUID] = Field(alias="expectedExpenseIds", min_length=1)

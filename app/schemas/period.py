from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.period import PeriodStatus


class PeriodBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def validate_dates(self) -> "PeriodBase":
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


class PeriodCreate(PeriodBase):
    pass


class PeriodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    starts_on: date | None = None
    ends_on: date | None = None
    status: PeriodStatus | None = None


class PeriodRead(PeriodBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: PeriodStatus
    created_at: datetime
    updated_at: datetime

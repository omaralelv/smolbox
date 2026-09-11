from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class AuthorizationAreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        name = " ".join(value.strip().split())
        if not name:
            raise ValueError("Authorization area name cannot be blank")
        return name


class AuthorizationAreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    normalized_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserAuthorizationAreaCreate(BaseModel):
    authorization_area_id: UUID | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "authorization_area_id",
            "authorizationAreaId",
            "area_id",
            "areaId",
        ),
    )
    authorization_area_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        validation_alias=AliasChoices(
            "authorization_area_name",
            "authorizationArea",
            "area_name",
            "areaName",
            "area",
        ),
    )
    is_active: bool = True

    @field_validator("authorization_area_name")
    @classmethod
    def clean_area_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = " ".join(value.strip().split())
        return name or None

    @model_validator(mode="after")
    def require_area(self) -> "UserAuthorizationAreaCreate":
        if self.authorization_area_id is None and not self.authorization_area_name:
            raise ValueError("authorization_area_id or authorization_area_name is required")
        return self


class UserAuthorizationAreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    authorization_area_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    authorization_area: AuthorizationAreaRead

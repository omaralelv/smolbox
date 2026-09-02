from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class FrontendStoreRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    code: str
    name: str
    gerente: str | None = None
    cuenta_bancaria: str | None = Field(default=None, alias="cuentaBancaria")
    estado_region: str | None = Field(default=None, alias="estadoRegion")


class FrontendUserRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    email: str
    nombre: str
    rol: str
    backend_role: str = Field(alias="backendRole")


class FrontendContextRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    current_role: str = Field(alias="currentRole")
    backend_role: str = Field(alias="backendRole")
    usuario: FrontendUserRead
    stores: list[FrontendStoreRead] = Field(default_factory=list)
    active_store: FrontendStoreRead | None = Field(default=None, alias="activeStore")
    current_period_id: UUID | None = Field(default=None, alias="currentPeriodId")
    tienda: str | None = None
    gerente: str | None = None
    cuenta_bancaria: str | None = Field(default=None, alias="cuentaBancaria")
    estado_region: str | None = Field(default=None, alias="estadoRegion")


class FrontendGastoRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    backend_id: UUID = Field(alias="backendId")
    nombre: str
    monto: float
    tipo: str
    type: str
    folio: str
    folio_fiscal: str | None = Field(default=None, alias="folioFiscal")
    observaciones: str | None = ""
    cfdi_subtotal: float | None = Field(default=None, alias="cfdiSubtotal")
    cfdi_total: float | None = Field(default=None, alias="cfdiTotal")
    cfdi_tax_amount: float | None = Field(default=None, alias="cfdiTaxAmount")
    cfdi_tax_rate: float | None = Field(default=None, alias="cfdiTaxRate")
    cfdi_currency: str | None = Field(default=None, alias="cfdiCurrency")
    facturas: int
    autorizacion: str
    status: str
    backend_status: str = Field(alias="backendStatus")
    requires_authorization: bool = Field(alias="requiresAuthorization")
    download_url: str | None = Field(default=None, alias="downloadUrl")


class FrontendSolicitudRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    backend_id: UUID = Field(alias="backendId")
    folio: str
    tienda: str
    fecha: str
    fecha_formateada: str = Field(alias="fechaFormateada")
    status: str
    backend_status: str = Field(alias="backendStatus")
    accounting_queue_status: str | None = Field(default=None, alias="accountingQueueStatus")
    gerente: str | None = None
    cuenta_bancaria: str | None = Field(default=None, alias="cuentaBancaria")
    estado_region: str | None = Field(default=None, alias="estadoRegion")
    gastos: list[FrontendGastoRead] = Field(default_factory=list)
    monto_total: float = Field(alias="montoTotal")
    reported_total: float | None = Field(default=None, alias="reportedTotal")
    calculated_total: float = Field(alias="calculatedTotal")
    expense_count: int = Field(alias="expenseCount")
    available_actions: list[str] = Field(default_factory=list, alias="availableActions")
    action_labels: dict[str, str] = Field(default_factory=dict, alias="actionLabels")


class FrontendObservationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    texto: str = Field(
        default="",
        validation_alias=AliasChoices("texto", "text", "message", "note"),
    )
    rol: str | None = None
    autor: str | None = None
    fecha_timestamp: int | float | None = Field(
        default=None,
        validation_alias=AliasChoices("fecha_timestamp", "fechaTimestamp", "timestamp"),
    )
    visibilidad: str | None = None


class FrontendGastoCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fecha: str | date | None = None
    categoria: str | None = None
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    folio: str | None = None
    observaciones: str | None = ""
    cfdi_uuid: str | None = Field(
        default=None,
        validation_alias=AliasChoices("cfdi_uuid", "cfdiUuid"),
    )
    cfdi_subtotal: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        validation_alias=AliasChoices("cfdi_subtotal", "cfdiSubtotal"),
    )
    cfdi_total: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        validation_alias=AliasChoices("cfdi_total", "cfdiTotal"),
    )
    cfdi_tax_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        validation_alias=AliasChoices("cfdi_tax_amount", "cfdiTaxAmount"),
    )
    cfdi_tax_rate: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=5,
        decimal_places=2,
        validation_alias=AliasChoices("cfdi_tax_rate", "cfdiTaxRate"),
    )
    cfdi_currency: str | None = Field(
        default=None,
        validation_alias=AliasChoices("cfdi_currency", "cfdiCurrency"),
    )
    proveedor: str | None = None
    merchant: str | None = None
    moneda: str = "MXN"
    requiere_autorizacion: bool = Field(
        default=False,
        validation_alias=AliasChoices("requiere_autorizacion", "requiresAuthorization"),
    )
    observaciones_historial: list[FrontendObservationCreate] = Field(
        default_factory=list,
        validation_alias=AliasChoices("observaciones_historial", "observacionesHistorial"),
    )


class FrontendSolicitudCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    store_id: UUID | None = None
    period_id: UUID | None = None
    tienda: str | None = None
    reported_total: Decimal | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("reported_total", "reportedTotal", "montoTotal"),
    )
    notes: str | None = None
    gastos: list[FrontendGastoCreate] = Field(default_factory=list)

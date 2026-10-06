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


class FrontendTreasuryDashboardStoreRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    code: str
    name: str


class FrontendTreasuryDashboardRowRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    store_id: UUID = Field(alias="storeId")
    store_code: str = Field(alias="storeCode")
    store_name: str = Field(alias="storeName")
    values: dict[int, float]


class FrontendTreasuryDashboardRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    years: list[int]
    stores: list[FrontendTreasuryDashboardStoreRead] = Field(default_factory=list)
    rows: list[FrontendTreasuryDashboardRowRead] = Field(default_factory=list)


class FrontendManagementProductivityRowRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accountant_id: UUID = Field(alias="accountantId")
    accountant_name: str = Field(alias="accountantName")
    values: dict[str, int]
    total: int


class FrontendManagementMonthlyProductivityRowRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accountant_id: UUID = Field(alias="accountantId")
    accountant_name: str = Field(alias="accountantName")
    total: int


class FrontendManagementProductivityDashboardRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    week_starts_on: date = Field(alias="weekStartsOn")
    week_ends_on: date = Field(alias="weekEndsOn")
    month: int
    year: int
    days: list[str]
    rows: list[FrontendManagementProductivityRowRead] = Field(default_factory=list)
    totals: dict[str, int]
    grand_total: int = Field(alias="grandTotal")
    monthly_rows: list[FrontendManagementMonthlyProductivityRowRead] = Field(
        default_factory=list,
        alias="monthlyRows",
    )
    monthly_grand_total: int = Field(alias="monthlyGrandTotal")


class FrontendProductivityActionRead(BaseModel):
    key: str
    label: str


class FrontendRoleProductivityRowRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    user_name: str = Field(alias="userName")
    action_key: str = Field(alias="actionKey")
    action_label: str = Field(alias="actionLabel")
    values: dict[str, int]
    total: int


class FrontendRoleMonthlyProductivityRowRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    user_name: str = Field(alias="userName")
    action_key: str = Field(alias="actionKey")
    action_label: str = Field(alias="actionLabel")
    total: int


class FrontendRoleProductivityDashboardRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    week_starts_on: date = Field(alias="weekStartsOn")
    week_ends_on: date = Field(alias="weekEndsOn")
    month: int
    year: int
    days: list[str]
    actions: list[FrontendProductivityActionRead] = Field(default_factory=list)
    rows: list[FrontendRoleProductivityRowRead] = Field(default_factory=list)
    totals: dict[str, int]
    totals_by_action: dict[str, dict[str, int]] = Field(alias="totalsByAction")
    grand_total: int = Field(alias="grandTotal")
    monthly_rows: list[FrontendRoleMonthlyProductivityRowRead] = Field(
        default_factory=list,
        alias="monthlyRows",
    )
    monthly_grand_total: int = Field(alias="monthlyGrandTotal")


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
    fecha: date
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
    sap_tax_index_override: str | None = Field(
        default=None,
        alias="sapTaxIndexOverride",
    )
    cfdi_currency: str | None = Field(default=None, alias="cfdiCurrency")
    facturas: int
    autorizacion: str
    status: str
    backend_status: str = Field(alias="backendStatus")
    requires_authorization: bool = Field(alias="requiresAuthorization")
    authorization_area_id: UUID | None = Field(default=None, alias="authorizationAreaId")
    authorization_area_name: str | None = Field(default=None, alias="authorizationArea")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    url_factura: str | None = Field(default=None, alias="urlFactura")
    url_vale: str | None = Field(default=None, alias="urlVale")
    url_recibo: str | None = Field(default=None, alias="urlRecibo")
    url_gasto: str | None = Field(default=None, alias="urlGasto")
    es_hijo_particion: bool = Field(default=False, alias="esHijoParticion")
    id_original: UUID | None = Field(default=None, alias="idOriginal")
    particion_index: int | None = Field(default=None, alias="particionIndex")
    total_particiones: int | None = Field(default=None, alias="totalParticiones")
    es_particionado: bool = Field(default=False, alias="esParticionado")
    inactivo: bool = False


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
    authorization_pending_count: int = Field(default=0, alias="authorizationPendingCount")
    ready_for_authorization_approval: bool = Field(
        default=False,
        alias="readyForAuthorizationApproval",
    )
    reembolso_attachment_id: UUID | None = Field(default=None, alias="reembolsoAttachmentId")
    reembolso_file_name: str | None = Field(default=None, alias="reembolsoFileName")
    reembolso_download_url: str | None = Field(default=None, alias="reembolsoDownloadUrl")
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


class FrontendClickAuditCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    button_label: str = Field(
        min_length=1,
        max_length=160,
        validation_alias=AliasChoices("button_label", "buttonLabel", "label"),
    )
    page_path: str | None = Field(
        default=None,
        max_length=240,
        validation_alias=AliasChoices("page_path", "pagePath"),
    )
    element_type: str | None = Field(
        default=None,
        max_length=40,
        validation_alias=AliasChoices("element_type", "elementType"),
    )
    action_key: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("action_key", "actionKey"),
    )
    expense_id: UUID | None = Field(
        default=None,
        validation_alias=AliasChoices("expense_id", "expenseId"),
    )


class FrontendExpensePartitionItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    categoria: str = Field(min_length=1, max_length=120)
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    impuesto: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=5,
        decimal_places=2,
        validation_alias=AliasChoices(
            "impuesto",
            "cfdi_tax_rate",
            "cfdiTaxRate",
            "taxRate",
        ),
    )


class FrontendExpensePartitionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    particiones: list[FrontendExpensePartitionItem] = Field(min_length=2)
    note: str | None = Field(default=None, max_length=1000)


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
    authorization_area_name: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices(
            "authorization_area_name",
            "authorizationArea",
            "area_autoriza",
            "areaAutoriza",
            "area",
        ),
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
        validation_alias=AliasChoices(
            "reported_total",
            "reportedTotal",
            "montoTotal",
        ),
    )

    notes: str | None = None

    gastos: list[FrontendGastoCreate] = Field(
        default_factory=list
    )

# Smolbox

Sistema inteligente de reembolsos de caja chica.

## Etapa 1 MVP

Esta primera base implementa un backend FastAPI con PostgreSQL para registrar tiendas,
periodos, solicitudes de caja chica, gastos, adjuntos y una lectura inicial de XML CFDI. La
intencion es tener una base pequena, local y verificable antes de agregar integraciones
empresariales.

Incluye:

- API REST versionada en `/api/v1`.
- Modelos de tienda, periodo, solicitud de caja chica, gasto y adjunto con SQLAlchemy.
- Persistencia en PostgreSQL usando Docker Compose.
- Carga local de formatos de caja chica XLSX, XLS y CSV, comprobantes y XML CFDI.
- Parser basico de CFDI para UUID, RFCs, total, moneda y fecha.
- Validacion inicial de CFDI contra importe, moneda y RFC receptor esperado.
- Persistencia del XML, campos fiscales, resultado de validacion e historial CFDI.
- Validacion de firmas reales de PDF, JPEG, PNG, XLS, XLSX y XML.
- Resumen de validacion por solicitud para comparar total reportado, suma de gastos,
  totales por categoria y comprobantes faltantes.
- Documentacion de alcance en `docs/etapa-1.md`.

## Etapa 2 backend

La segunda etapa agrega la base operativa del flujo interno sin conectores empresariales:

- Migraciones Alembic para evolucionar PostgreSQL sin borrar datos locales.
- Usuarios internos con rol `store`, `accountant`, `treasury` o `admin`.
- Flujo de estados de solicitud: borrador, enviada, revision contable, correccion,
  aprobacion contable, revision de tesoreria, autorizacion de pago, pagada, cerrada
  o rechazada.
- Endpoint de transicion de estado con validacion de rol y reglas minimas de negocio.
- Bitacora de auditoria para solicitudes, gastos, adjuntos, CFDI y cambios de estado.
- Validacion ampliada por solicitud: gastos fuera de periodo, CFDI duplicados, CFDI
  invalidos y readiness para envio/aprobacion contable.
- Descarga de adjuntos por ID.
- Edicion parcial de tiendas, periodos, solicitudes, gastos y usuarios.
- Importacion masiva de gastos desde CSV o XLSX con validacion previa.
- Documentacion de alcance en `docs/etapa-2-backend.md`.

Fuera de esta etapa:

- Integraciones SAP.
- Integraciones Azure, Active Directory o SSO empresarial.
- Validacion en linea contra SAT.
- Dispersion bancaria o contabilizacion final automatica.

## Ejecutar localmente

1. Copia la configuracion de ejemplo:

   ```bash
   cp .env.example .env
   ```

2. Levanta la API y PostgreSQL:

   ```bash
   docker compose up --build
   ```

3. Abre la documentacion interactiva:

   ```text
   http://localhost:8000/docs
   ```

Docker ejecuta `alembic upgrade head` antes de iniciar FastAPI. Si ya tenias una base local
de prueba de Etapa 1 y quieres empezar limpio:

```bash
docker compose down -v
docker compose up --build
```

## Desarrollo sin Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Para correr pruebas:

```bash
ruff check .
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

La suite usa SQLite de forma predeterminada. Para comprobarla contra PostgreSQL:

```bash
SMOLBOX_TEST_DATABASE_URL=postgresql+psycopg://usuario:password@localhost:5432/smolbox_test pytest
```

Cada push y pull request ejecuta automaticamente Ruff, las pruebas API y una cobertura
minima de 80 % contra PostgreSQL 16 mediante GitHub Actions.

## Flujo minimo de prueba

1. Crear una tienda en `POST /api/v1/stores`.
2. Crear un periodo en `POST /api/v1/periods`.
3. Crear una solicitud en `POST /api/v1/reimbursement-requests` con `store_id`,
   `period_id` y `reported_total`.
4. Subir el formato de caja chica en
   `POST /api/v1/reimbursement-requests/{request_id}/attachments`.
5. Crear gastos en `POST /api/v1/expenses` usando `reimbursement_request_id`.
6. Subir comprobantes por gasto en `POST /api/v1/expenses/{expense_id}/attachments`.
7. Cargar y validar el XML en
   `POST /api/v1/expenses/{expense_id}/cfdi/validate`; esta operacion guarda el XML y
   el resultado en una sola transaccion.
8. Revisar el cierre en
   `GET /api/v1/reimbursement-requests/{request_id}/validation-summary`.
9. Crear usuarios internos en `POST /api/v1/users`.
10. Cambiar estados con `POST /api/v1/reimbursement-requests/{request_id}/transition`.
11. Revisar auditoria con
   `GET /api/v1/reimbursement-requests/{request_id}/audit-events`.
12. Corregir datos con endpoints `PATCH`, por ejemplo `PATCH /api/v1/expenses/{expense_id}`.
13. Importar gastos desde Excel/CSV con
   `POST /api/v1/reimbursement-requests/{request_id}/expenses/import`.

## Importacion masiva de gastos

El archivo debe ser `.csv` o `.xlsx`. La primera fila debe tener encabezados. Se aceptan
nombres en espanol o ingles:

```text
proveedor, importe, fecha, categoria, descripcion, rfc_proveedor, moneda
```

Columnas obligatorias:

- `proveedor` o `merchant`
- `importe`, `monto`, `total` o `amount`
- `fecha` o `spent_on`

Formato recomendado de fecha:

```text
2026-08-10
```

El endpoint tambien acepta `dry_run=true` para revisar el archivo sin guardar gastos.

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
- Usuarios internos con rol `store`, `authorizer`, `accountant`,
  `accounting_manager`, `treasury`, `director` o `admin`.
- Login basico con contrasena y token Bearer local.
- Rutas autenticadas `/me` para que el frontend real ejecute transiciones y acciones
  usando el usuario del token, no un `actor_user_id` editable desde la pantalla.
- Asignacion formal usuario-tienda para roles que operan una tienda especifica.
- Flujo de estados de solicitud alineado al proceso empresarial: tienda, autorizacion,
  contabilidad, gerente de contabilidad, tesoreria, direccion, pago y cierre.
- Endpoint de transicion de estado con validacion de rol y reglas minimas de negocio.
- Cola de trabajo `/work-queue/me` para que cada rol vea las solicitudes que le tocan.
- Correcciones con regreso al punto que pidio la correccion, por ejemplo de tienda de vuelta
  a contabilidad.
- Acciones por gasto para autorizar, rechazar en autorizacion, observar, editar durante
  revision contable/gerencial y remover con motivo obligatorio sin borrar historial.
- Registro formal de pago en tabla `payments` cuando tesoreria confirma el reembolso.
- Reglas de negocio configurables en `business_rules`, editables por admin.
- Bitacora de auditoria para solicitudes, gastos, adjuntos, CFDI, pagos y cambios de estado.
- Validacion ampliada por solicitud: gastos fuera de periodo, CFDI duplicados, CFDI
  invalidos, autorizaciones pendientes y readiness para envio/autorizacion/aprobacion
  contable.
- Revision automatica de solicitud para CFDI, comprobantes, total, periodo, OCR pendiente,
  alertas y datos base de poliza SAP sin aprobar decisiones humanas.
- Descarga de adjuntos por ID y descarga protegida con token en `/download/me`.
- Edicion parcial de tiendas, periodos, solicitudes, gastos y usuarios; las solicitudes,
  gastos, adjuntos y CFDI quedan bloqueados despues de enviar, salvo que regresen a correccion.
- Importacion masiva de gastos desde CSV o XLSX con validacion previa.
- HUD local de pruebas en `/test-hud` para sembrar datos demo y recorrer el flujo con una
  vista guiada por rol cercana al usuario final.
- Herramientas del HUD para crear tiendas HUD, usuarios HUD, asignarlos de forma operativa
  y agregar gastos de prueba.
- Demo masivo del HUD para crear varias solicitudes en diferentes estados del flujo y probar
  bandejas de trabajo por rol sin datos reales.
- Panel de sesion en el HUD para iniciar como tienda, autorizacion, contabilidad, gerente,
  tesoreria, direccion o admin, y probar rutas autenticadas con token.
- Seccion de reglas de negocio en el HUD para revisar y editar configuracion tecnica
  usando sesion admin.
- Placeholder auditable de poliza SAP antes de enviar la solicitud a gerente de contabilidad.
- Documentacion de alcance en `docs/etapa-2-backend.md`.

Fuera de esta etapa:

- Integraciones SAP.
- Generacion real de poliza SAP; por ahora solo existe el punto de extension.
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

4. Abre el HUD local de pruebas:

   ```text
   http://localhost:8000/test-hud
   ```

Docker ejecuta `alembic upgrade head` antes de iniciar FastAPI. Si ya tenias una base local
de prueba de Etapa 1 y quieres empezar limpio:

```bash
docker compose down -v
docker compose up --build
```

## Datos de prueba

El repo incluye datos ficticios para pruebas manuales en `docs/test-data`:

- escenarios JSON para sembrar el HUD;
- CSV validos e invalidos para importacion masiva;
- XML CFDI ficticios para validacion;
- un PDF minimo para probar subida de comprobantes.

La guia de uso esta en `docs/test-data/README.md`.

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
10. Asignar usuarios a tienda con `POST /api/v1/stores/{store_id}/users`.
11. Cambiar estados con `POST /api/v1/reimbursement-requests/{request_id}/transition`.
12. Rechazar un gasto/producto individual de autorizacion, si no procede, con
   `POST /api/v1/expenses/{expense_id}/reject`.
13. Preparar la poliza SAP placeholder con
   `POST /api/v1/reimbursement-requests/{request_id}/sap-policy/prepare`.
14. Revisar auditoria con
   `GET /api/v1/reimbursement-requests/{request_id}/audit-events`.
15. Corregir datos con endpoints `PATCH`, por ejemplo `PATCH /api/v1/expenses/{expense_id}`.
16. Importar gastos desde Excel/CSV con
   `POST /api/v1/reimbursement-requests/{request_id}/expenses/import`.

Flujo de estados esperado:

```text
draft
-> submitted
-> authorization_review
-> authorized
-> under_accounting_review
-> accounting_reviewed
-> preparar poliza SAP placeholder
-> accounting_manager_review
-> accounting_manager_approved
-> treasury_review
-> direction_review
-> direction_approved
-> approved_for_payment
-> registrar pago formal (paid)
-> closed
```

Durante autorizacion, si un gasto/producto no procede, se rechaza solo ese gasto con
`POST /api/v1/expenses/{expense_id}/reject`; la solicitud puede seguir con los gastos
restantes si el total queda cuadrado. Los gastos que tienen `requires_authorization=true`
deben autorizarse o rechazarse antes de mover la solicitud a `authorized`.

Tambien puedes probar ese recorrido desde `http://localhost:8000/test-hud`. Primero usa
`Crear escenario` para una sola solicitud o `Crear demo masivo` para poblar varias bandejas.
Luego prueba `Completar CFDI`, `Enviar tienda`, `Revision autorizacion`,
`Autorizar gastos` o `Rechazar producto`, `Autorizar solicitud`, `Revision contable`,
`Cerrar contabilidad`, `Preparar poliza SAP`, `Enviar gerente`, `Aprobar gerente`,
`Revision tesoreria`, `Enviar direccion`, `Aprobar direccion`, `Aprobar pago`,
`Registrar pago` y `Cerrar`.

El HUD tambien permite crear tiendas y usuarios con prefijo/dominio `HUD`, asignar un
usuario tienda o contador a una tienda, crear un gasto dentro de la solicitud demo,
quitar gastos durante revision contable con motivo obligatorio, registrar pagos formales y
editar reglas de negocio como admin. Esa asignacion ya se respalda con el modelo formal
`store_user_assignments`.

## Importacion masiva de gastos

El archivo debe ser `.csv` o `.xlsx`. La primera fila debe tener encabezados. Se aceptan
nombres en espanol o ingles:

```text
proveedor, importe, fecha, categoria, descripcion, rfc_proveedor, moneda, requiere_autorizacion
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

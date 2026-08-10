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
- Carga local de formato de caja chica, comprobantes y XML CFDI.
- Parser basico de CFDI para UUID, RFCs, total, moneda y fecha.
- Validacion inicial de CFDI contra importe, moneda y RFC receptor esperado.
- Resumen de validacion por solicitud para comparar total reportado, suma de gastos,
  totales por categoria y comprobantes faltantes.
- Documentacion de alcance en `docs/etapa-1.md`.

Fuera de esta etapa:

- Integraciones SAP.
- Integraciones Azure o SSO empresarial.
- Validacion en linea contra SAT.
- Flujos avanzados de aprobacion, pagos o contabilidad.

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

La API crea las tablas automaticamente al iniciar para facilitar la Etapa 1. En una etapa posterior se deberian agregar migraciones formales con Alembic.

## Desarrollo sin Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Para correr pruebas:

```bash
pytest
```

## Flujo minimo de prueba

1. Crear una tienda en `POST /api/v1/stores`.
2. Crear un periodo en `POST /api/v1/periods`.
3. Crear una solicitud en `POST /api/v1/reimbursement-requests` con `store_id`,
   `period_id` y `reported_total`.
4. Subir el formato de caja chica en
   `POST /api/v1/reimbursement-requests/{request_id}/attachments`.
5. Crear gastos en `POST /api/v1/expenses` usando `reimbursement_request_id`.
6. Subir comprobantes y XML por gasto en `POST /api/v1/expenses/{expense_id}/attachments`.
7. Revisar el cierre en
   `GET /api/v1/reimbursement-requests/{request_id}/validation-summary`.

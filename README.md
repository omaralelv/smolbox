# Smolbox

Sistema inteligente de reembolsos de caja chica.

## Etapa 1 MVP

Esta primera base implementa un backend FastAPI con PostgreSQL para registrar periodos, gastos, adjuntos y una lectura inicial de XML CFDI. La intencion es tener una base pequena, local y verificable antes de agregar integraciones empresariales.

Incluye:

- API REST versionada en `/api/v1`.
- Modelos de periodo, gasto y adjunto con SQLAlchemy.
- Persistencia en PostgreSQL usando Docker Compose.
- Carga local de comprobantes y XML CFDI.
- Parser basico de CFDI para UUID, RFCs, total, moneda y fecha.
- Validacion inicial de CFDI contra importe, moneda y RFC receptor esperado.
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

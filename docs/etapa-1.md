# Smolbox Etapa 1 MVP

## Objetivo

Construir una base backend pequena para manejar reembolsos de caja chica: periodos, gastos, comprobantes adjuntos y una validacion inicial de CFDI. La prioridad es tener un nucleo simple que se pueda correr localmente y extender despues.

## Alcance incluido

- Crear y listar periodos de reembolso.
- Crear y listar gastos asociados a un periodo.
- Cargar adjuntos por gasto en almacenamiento local.
- Leer datos esenciales de XML CFDI:
  - UUID fiscal.
  - RFC emisor.
  - RFC receptor.
  - Total.
  - Moneda.
  - Fecha de emision.
- Validar CFDI contra un gasto ya registrado:
  - UUID presente.
  - Total igual al monto del gasto.
  - Moneda igual a la moneda del gasto.
  - RFC receptor igual a `CFDI_RECEIVER_RFC` cuando este configurado.

## Fuera de alcance

- SAP, Azure, Active Directory, SSO o conectores empresariales.
- Validacion en linea contra SAT.
- Motor avanzado de aprobaciones.
- Pagos, dispersion bancaria o contabilidad final.
- Almacenamiento en nube de adjuntos.

## Modelo de dominio

`Period` representa una ventana de reembolso con fecha inicial, fecha final y estado.

`Expense` representa un gasto capturado dentro de un periodo. Guarda importe, moneda, proveedor, fecha, categoria y campos CFDI opcionales para evolucionar la validacion.

`Attachment` representa un archivo cargado contra un gasto. En esta etapa se guarda en disco local y registra ruta, tipo MIME, tamano y hash SHA-256.

## Endpoints iniciales

- `GET /api/v1/health`
- `POST /api/v1/periods`
- `GET /api/v1/periods`
- `GET /api/v1/periods/{period_id}`
- `POST /api/v1/expenses`
- `GET /api/v1/expenses`
- `GET /api/v1/expenses/{expense_id}`
- `POST /api/v1/expenses/{expense_id}/attachments`
- `POST /api/v1/cfdi/parse`
- `POST /api/v1/expenses/{expense_id}/cfdi/validate`

## Decisiones tecnicas

- FastAPI para exponer la API y documentacion OpenAPI.
- SQLAlchemy 2 para modelos y persistencia.
- PostgreSQL como base de datos desde el inicio.
- Docker Compose para levantar API y base de datos localmente.
- `Base.metadata.create_all` al iniciar, solo para acelerar Etapa 1. Migraciones formales deben agregarse antes de produccion.

## Siguientes pasos sugeridos

1. Agregar autenticacion basica de usuarios internos.
2. Agregar migraciones Alembic.
3. Persistir el resultado de validacion CFDI en una tabla dedicada.
4. Agregar estado de revision por gasto.
5. Agregar UI minima para captura y revision.

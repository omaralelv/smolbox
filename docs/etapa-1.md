# Smolbox Etapa 1 MVP

## Objetivo

Construir una base backend pequena para manejar reembolsos de caja chica: tiendas,
periodos, solicitudes de caja chica, gastos, comprobantes adjuntos y una validacion inicial
de CFDI. La prioridad es tener un nucleo simple que refleje el proceso real de tienda y
contabilidad, se pueda correr localmente y se pueda extender despues.

## Alcance incluido

- Crear y listar periodos de reembolso.
- Crear y listar tiendas.
- Crear y listar solicitudes de caja chica asociadas a tienda y periodo.
- Crear y listar gastos asociados a un periodo y, opcionalmente, a una solicitud de caja chica.
- Cargar adjuntos por solicitud y por gasto en almacenamiento local.
- Distinguir el formato de caja chica enviado por tienda de comprobantes y XML CFDI.
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
- Validar una solicitud de caja chica contra sus gastos:
  - Total reportado por tienda contra suma de gastos.
  - Suma por categoria.
  - Gastos sin comprobante.
  - Gastos sin XML CFDI como advertencia inicial.

## Fuera de alcance

- SAP, Azure, Active Directory, SSO o conectores empresariales.
- Validacion en linea contra SAT.
- Motor avanzado de aprobaciones.
- Pagos, dispersion bancaria o contabilidad final.
- Almacenamiento en nube de adjuntos.

## Modelo de dominio

`Period` representa una ventana de reembolso con fecha inicial, fecha final y estado.

`Store` representa la tienda que solicita el reembolso de caja chica. Guarda codigo, nombre,
correo de contacto y contador asignado cuando este dato exista.

`ReimbursementRequest` representa la solicitud que una tienda envia para un periodo. Guarda
tienda, periodo, total reportado, datos del reembolso anterior y notas. En Etapa 2 esta
entidad debe convertirse en el centro del flujo de aprobacion.

`Expense` representa un gasto capturado dentro de un periodo y opcionalmente dentro de una
solicitud de caja chica. Guarda importe, moneda, proveedor, fecha, categoria y campos CFDI
opcionales para evolucionar la validacion.

`Attachment` representa un archivo cargado contra una solicitud o un gasto. En esta etapa se
guarda en disco local y registra ruta, tipo MIME, tamano y hash SHA-256.

## Endpoints iniciales

- `GET /api/v1/health`
- `POST /api/v1/stores`
- `GET /api/v1/stores`
- `GET /api/v1/stores/{store_id}`
- `POST /api/v1/periods`
- `GET /api/v1/periods`
- `GET /api/v1/periods/{period_id}`
- `POST /api/v1/reimbursement-requests`
- `GET /api/v1/reimbursement-requests`
- `GET /api/v1/reimbursement-requests/{request_id}`
- `GET /api/v1/reimbursement-requests/{request_id}/validation-summary`
- `POST /api/v1/reimbursement-requests/{request_id}/attachments`
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
- `Base.metadata.create_all` al iniciar, solo para acelerar Etapa 1. Migraciones formales
  deben agregarse antes de produccion.

## Siguientes pasos sugeridos

1. Agregar autenticacion basica de usuarios internos.
2. Agregar migraciones Alembic.
3. Persistir el resultado de validacion CFDI en una tabla dedicada.
4. Convertir `ReimbursementRequest` en el centro del flujo de revision y aprobacion.
5. Agregar UI minima para tienda, contador, supervisora, tesoreria y direccion.
6. Agregar exportacion CSV/XLSX compatible con el proceso manual previo a SAP.

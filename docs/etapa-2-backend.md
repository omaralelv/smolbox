# Smolbox Etapa 2 Backend

## Objetivo

Convertir la base de Etapa 1 en un flujo backend controlado para tienda, contabilidad y
tesoreria. Esta etapa sigue siendo local y verificable; no incluye SAP, Azure, SSO ni
validacion en linea contra SAT.

## Alcance incluido

- Migraciones Alembic para versionar la base de datos.
- Usuarios internos con roles operativos:
  - `store`: captura y envia solicitudes.
  - `accountant`: revisa, pide correcciones y aprueba contablemente.
  - `treasury`: revisa tesoreria, autoriza pago, marca pagado y cierra.
  - `admin`: puede ejecutar cualquier transicion soportada.
- Flujo de estados de solicitud:
  - `draft`
  - `submitted`
  - `under_accounting_review`
  - `correction_required`
  - `accounting_approved`
  - `treasury_review`
  - `approved_for_payment`
  - `paid`
  - `closed`
  - `rejected`
- Bitacora de auditoria para reconstruir acciones importantes.
- Validacion ampliada de solicitudes.
- Descarga de adjuntos por identificador.
- Edicion parcial de registros operativos mediante `PATCH`.
- Importacion masiva de gastos desde CSV o XLSX.
- HUD local de pruebas para recorrer el flujo desde el navegador.

## Migraciones de base de datos

PostgreSQL sigue siendo la base real. Alembic agrega una tabla llamada `alembic_version`
para saber que cambios ya fueron aplicados.

En Docker, las migraciones corren automaticamente antes de levantar FastAPI:

```bash
docker compose up --build
```

En desarrollo local sin Docker:

```bash
alembic upgrade head
```

La primera migracion de Etapa 2 crea la estructura actual en una base vacia y tambien agrega
columnas nuevas si detecta una base local que venia de Etapa 1.

## Reglas de flujo

Las transiciones se hacen con:

```text
POST /api/v1/reimbursement-requests/{request_id}/transition
```

El cuerpo necesita:

```json
{
  "target_status": "submitted",
  "actor_user_id": "00000000-0000-0000-0000-000000000000",
  "note": "Solicitud enviada por tienda"
}
```

Reglas principales:

- La tienda puede mover `draft` o `correction_required` a `submitted`.
- Contabilidad puede mover `submitted` a `under_accounting_review`.
- Contabilidad puede pedir correccion o aprobar contablemente desde
  `under_accounting_review`.
- Tesoreria puede mover `accounting_approved` a `treasury_review`.
- Tesoreria puede autorizar pago, marcar pagado y cerrar.
- `admin` puede ejecutar las transiciones soportadas.

Para enviar una solicitud, el resumen debe estar listo para envio:

- total reportado presente;
- al menos un gasto;
- suma de gastos igual al total reportado;
- comprobantes obligatorios presentes;
- gastos dentro del periodo.

Para aprobacion contable, ademas se requiere que no falten XML CFDI y que no existan errores
de CFDI persistidos. Si se edita monto, moneda o RFC de proveedor despues de validar un CFDI,
la validacion CFDI se marca como no vigente y debe repetirse.

## Edicion de datos

La API permite corregir datos antes de enviar o cuando la solicitud esta en correccion:

- `PATCH /api/v1/stores/{store_id}`
- `PATCH /api/v1/periods/{period_id}`
- `PATCH /api/v1/reimbursement-requests/{request_id}`
- `PATCH /api/v1/expenses/{expense_id}`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/users/{user_id}/deactivate`

Las solicitudes y gastos se bloquean despues de `submitted` para evitar cambios silenciosos
mientras contabilidad o tesoreria revisan.

## Importacion masiva

Endpoint:

```text
POST /api/v1/reimbursement-requests/{request_id}/expenses/import
```

Acepta archivos `.csv` y `.xlsx`. XLS binario queda fuera por ahora; se debe guardar como
XLSX o CSV antes de importar.

Columnas aceptadas:

- `proveedor`, `merchant`, `comercio` o `establecimiento`
- `importe`, `monto`, `total` o `amount`
- `fecha` o `spent_on`
- `categoria` o `category`
- `descripcion`, `concepto`, `detalle` o `description`
- `rfc_proveedor`, `rfc_emisor`, `rfc`, `supplier_rfc` o `supplier_tax_id`
- `moneda` o `currency`

Columnas obligatorias:

- proveedor/merchant
- importe/amount
- fecha/spent_on

Se puede mandar `dry_run=true` para validar el archivo sin guardar datos ni adjuntos.
Si una fila falla, no se guarda ninguna fila del archivo.

## Auditoria

Se registran eventos en `audit_logs` para:

- solicitud creada;
- gasto creado;
- adjunto subido;
- CFDI validado;
- cambio de estado.
- gastos importados masivamente;
- solicitud o gasto actualizado.

Consulta:

```text
GET /api/v1/reimbursement-requests/{request_id}/audit-events
```

## HUD local de pruebas

La ruta local:

```text
http://localhost:8000/test-hud
```

sirve una pantalla interna de desarrollo. No es el frontend final. Permite:

- revisar salud de API y base de datos;
- sembrar un escenario demo con tienda, periodo, usuarios, solicitud, gastos y tickets;
- intentar transiciones de estado;
- ver que contabilidad queda bloqueada si faltan CFDI vigentes;
- completar CFDI sinteticos de prueba;
- probar importacion CSV con `dry_run` o guardado real;
- crear tiendas HUD, usuarios HUD y asignarlos de forma operativa;
- crear pagos/gastos de prueba en la solicitud HUD;
- limpiar solo los datos con prefijo HUD.

Los endpoints auxiliares viven bajo:

```text
/api/v1/dev-hud
```

Si `ENVIRONMENT=production`, el HUD responde como no encontrado.

## Nuevos endpoints

- `GET /api/v1/dev-hud/status`
- `POST /api/v1/dev-hud/seed-demo`
- `POST /api/v1/dev-hud/stores`
- `POST /api/v1/dev-hud/users`
- `POST /api/v1/dev-hud/assign-user`
- `POST /api/v1/dev-hud/payments`
- `POST /api/v1/dev-hud/complete-cfdi`
- `POST /api/v1/dev-hud/transition/{target_status}`
- `POST /api/v1/dev-hud/reset-demo`
- `POST /api/v1/users`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/users/{user_id}/deactivate`
- `PATCH /api/v1/stores/{store_id}`
- `PATCH /api/v1/periods/{period_id}`
- `PATCH /api/v1/reimbursement-requests/{request_id}`
- `POST /api/v1/reimbursement-requests/{request_id}/transition`
- `GET /api/v1/reimbursement-requests/{request_id}/audit-events`
- `POST /api/v1/reimbursement-requests/{request_id}/expenses/import`
- `PATCH /api/v1/expenses/{expense_id}`
- `GET /api/v1/attachments/{attachment_id}`
- `GET /api/v1/attachments/{attachment_id}/download`

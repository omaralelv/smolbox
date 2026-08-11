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
de CFDI persistidos.

## Auditoria

Se registran eventos en `audit_logs` para:

- solicitud creada;
- gasto creado;
- adjunto subido;
- CFDI validado;
- cambio de estado.

Consulta:

```text
GET /api/v1/reimbursement-requests/{request_id}/audit-events
```

## Nuevos endpoints

- `POST /api/v1/users`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `POST /api/v1/reimbursement-requests/{request_id}/transition`
- `GET /api/v1/reimbursement-requests/{request_id}/audit-events`
- `GET /api/v1/attachments/{attachment_id}`
- `GET /api/v1/attachments/{attachment_id}/download`

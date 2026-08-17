# Smolbox Etapa 2 Backend

## Objetivo

Convertir la base de Etapa 1 en un flujo backend controlado para tienda, autorizacion,
contabilidad, gerente de contabilidad, tesoreria y direccion. Esta etapa sigue siendo local
y verificable; no incluye integracion real SAP, Azure, SSO ni validacion en linea contra SAT.
Si incluye un placeholder auditable para preparar la poliza SAP antes de enviar a gerente.

## Alcance incluido

- Migraciones Alembic para versionar la base de datos.
- Usuarios internos con roles operativos:
  - `store`: captura y envia solicitudes.
  - `authorizer`: revisa gastos que requieren autorizacion y los autoriza o rechaza a
    nivel gasto/producto.
  - `accountant`: revisa facturas, CFDI y formato base; puede observar, editar o remover gastos.
  - `accounting_manager`: valida la revision contable antes de tesoreria.
  - `treasury`: revisa tesoreria, envia a direccion, libera pago, registra el pago formal y cierra.
  - `director`: aprueba la solicitud revisada por tesoreria para liberar pago.
  - `admin`: puede ejecutar cualquier transicion soportada.
- Flujo de estados de solicitud:
  - `draft`
  - `submitted`
  - `authorization_review` si hay gastos pendientes con `requires_authorization=true`
  - `authorized` despues de resolver esos gastos
  - `under_accounting_review`
  - `correction_required`
  - `accounting_reviewed`
  - `accounting_approved`
  - `accounting_manager_review`
  - `accounting_manager_approved`
  - `treasury_review`
  - `direction_review`
  - `direction_approved`
  - `approved_for_payment`
  - `paid`
  - `closed`
  - `rejected`
- Bitacora de auditoria para reconstruir acciones importantes.
- Login basico con contrasena y token Bearer local.
- Asignacion formal usuario-tienda mediante `store_user_assignments`.
- Cola de trabajo autenticada para que cada rol consulte solo las solicitudes que le tocan.
- Validacion ampliada de solicitudes.
- Flujo de revision automatica para CFDI, comprobantes, total, periodo, OCR pendiente,
  alertas y datos base de poliza SAP.
- Revision por gasto: autorizar, rechazar en autorizacion, observar, editar durante
  revision contable/gerencial y remover con motivo obligatorio sin borrar historial.
- Placeholder de poliza SAP despues de revision contable y antes de gerente.
- Registro formal de pagos por tesoreria en la tabla `payments`.
- Reglas de negocio configurables en la tabla `business_rules`.
- Descarga de adjuntos por identificador y descarga protegida con token.
- Edicion parcial de registros operativos mediante `PATCH`.
- Importacion masiva de gastos desde CSV o XLSX.
- HUD local de pruebas para recorrer el flujo desde el navegador, incluyendo una vista
  guiada por rol parecida al uso final.

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

La migracion `20260812_0004_expense_authorization_rejection` asegura que PostgreSQL acepte
`rejected` como estado de gasto para rechazar un producto individual durante autorizacion.

La migracion `20260813_0005_queues_payments_rules` agrega:

- metadatos de correccion en `reimbursement_requests`;
- tabla `payments` para registrar pagos de tesoreria;
- tabla `business_rules` para reglas configurables;
- enum `payment_status` para distinguir pagos pagados o cancelados.

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

- La tienda puede mover `draft` a `submitted`; `correction_required` se conserva solo como
  compatibilidad para datos locales anteriores.
- Autorizacion mueve `submitted` a `authorization_review` solo cuando existen gastos pendientes
  con `requires_authorization=true`.
- Autorizacion puede autorizar o rechazar gastos individuales y luego mover la solicitud a
  `authorized`. Si algo no procede en esta etapa, se rechaza el gasto/producto, no toda la
  solicitud.
- Si no hay gastos pendientes de autorizacion, la solicitud enviada pasa directo a la cola de
  contabilidad y contabilidad puede mover `submitted` a `under_accounting_review`.
- Contabilidad mueve `authorized` o `submitted` sin autorizaciones pendientes a
  `under_accounting_review`.
- Autorizacion y contabilidad no pueden regresar la solicitud a tienda para correccion.
- Contabilidad puede observar, editar durante revision, quitar gastos con motivo o mover a
  `accounting_reviewed`.
- Si un revisor posterior necesita ajuste, regresa la solicitud un paso:
  gerente a `under_accounting_review`, tesoreria a `accounting_manager_review` y direccion a
  `treasury_review`.
- Despues de `accounting_reviewed`, contabilidad debe preparar la poliza SAP placeholder.
- Gerente de contabilidad recibe la solicitud en `accounting_manager_review` solo si la
  poliza SAP placeholder ya fue preparada, y despues puede mover a
  `accounting_manager_approved`.
- Tesoreria mueve `accounting_manager_approved` a `treasury_review` y luego a
  `direction_review`.
- Direccion mueve `direction_review` a `direction_approved`.
- Tesoreria puede mover `direction_approved` a `approved_for_payment`, registrar pago formal
  y cerrar.
- `paid` no se alcanza con `transition`; solo se marca cuando tesoreria registra un pago en
  `/payments/me`.
- `admin` puede ejecutar las transiciones soportadas.

Para enviar una solicitud, el resumen debe estar listo para envio:

- total reportado presente;
- al menos un gasto;
- suma de gastos igual al total reportado;
- comprobante/ticket presente en cada gasto activo;
- XML CFDI vigente y valido en cada gasto activo;
- gastos dentro del periodo.

Si falta ticket, falta CFDI o el CFDI vigente es invalido, la transicion de tienda a
`submitted` responde `409 INVALID_WORKFLOW_TRANSITION` y la solicitud permanece en tienda.
Si se edita monto, moneda o RFC de proveedor despues de validar un CFDI, la validacion CFDI
se marca como no vigente y debe repetirse antes de enviar.

Para autorizacion, los gastos con `requires_authorization=true` deben estar autorizados o
rechazados. Los gastos rechazados quedan fuera del total activo de reembolso, conservan
historial y no bloquean que la solicitud avance. Los gastos que no requieren autorizacion no
bloquean ese paso.

## Flujo automatico y humano

La automatizacion se ejecuta con:

```text
POST /api/v1/reimbursement-requests/{request_id}/automated-review
```

Este paso no aprueba ni rechaza la solicitud. Solo revisa y registra auditoria de:

- CFDI faltante, invalido o duplicado;
- comprobantes faltantes;
- total reportado descuadrado;
- gastos fuera de periodo;
- OCR pendiente de integracion real;
- alertas automaticas;
- datos base para preparar la poliza SAP.

Las decisiones humanas siguen separadas:

- autorizacion decide autorizar o rechazar productos;
- gerente de contabilidad aprueba despues de contabilidad;
- direccion aprueba antes de liberar pago;
- tesoreria confirma pago.

## Login y permisos por tienda

Los usuarios pueden crearse con contrasena opcional:

```json
{
  "email": "contador@example.com",
  "full_name": "Contador Demo",
  "role": "accountant",
  "password": "secret-password"
}
```

Login:

```text
POST /api/v1/auth/login
```

```json
{
  "email": "contador@example.com",
  "password": "secret-password"
}
```

La respuesta devuelve `access_token` y puede probarse con:

```text
GET /api/v1/auth/me
Authorization: Bearer <token>
```

Para el frontend real, las acciones humanas deben usar las rutas autenticadas con sufijo
`/me`. En esas rutas el backend toma el usuario desde el token Bearer y no acepta que la
pantalla decida el `actor_user_id`.

Ejemplos:

```text
POST /api/v1/reimbursement-requests/{request_id}/transition/me
POST /api/v1/reimbursement-requests/{request_id}/sap-policy/prepare/me
POST /api/v1/reimbursement-requests/{request_id}/payments/me
POST /api/v1/expenses/{expense_id}/authorize/me
POST /api/v1/expenses/{expense_id}/reject/me
POST /api/v1/expenses/{expense_id}/observation/me
PATCH /api/v1/expenses/{expense_id}/review/me
POST /api/v1/expenses/{expense_id}/remove/me
GET /api/v1/attachments/{attachment_id}/download/me
```

Las rutas antiguas que reciben `actor_user_id` se conservan para pruebas tecnicas y
compatibilidad temporal del HUD.

Para que tienda, autorizacion, contabilidad o gerente puedan mover una solicitud, el usuario
debe estar asignado a la tienda:

```text
POST /api/v1/stores/{store_id}/users
```

```json
{
  "user_id": "00000000-0000-0000-0000-000000000000",
  "role": "accountant"
}
```

Tesoreria, direccion y admin siguen siendo roles transversales por ahora.

## Cola de trabajo

El frontend puede consultar la bandeja de trabajo del usuario con:

```text
GET /api/v1/work-queue/me
Authorization: Bearer <token>
```

La respuesta devuelve solicitudes filtradas por rol y estado:

- tienda ve borradores y, por compatibilidad con datos viejos, solicitudes en correccion de sus
  tiendas asignadas;
- autorizacion ve solicitudes enviadas o en revision de autorizacion de sus tiendas;
- contabilidad ve solicitudes enviadas sin autorizaciones pendientes, autorizadas o en revision
  contable de sus tiendas;
- gerente contable ve solicitudes revisadas por contabilidad o en revision gerencial;
- tesoreria ve solicitudes aprobadas por gerente, en revision de tesoreria o listas para pago;
- direccion ve solicitudes en revision de direccion;
- admin ve todo.

## Puente para frontend actual

Para conectar las pantallas actuales sin cambiar su diseno ni nombres de campos, el backend
expone una capa de compatibilidad bajo:

```text
/api/v1/frontend
```

Estos endpoints no reemplazan la API formal; solamente traducen el modelo tecnico a la forma
que hoy espera la UI, por ejemplo `tienda`, `fecha`, `status`, `gastos`, `montoTotal`,
`fechaFormateada`, `cuentaBancaria` y `backendId`.

Endpoints:

```text
GET  /api/v1/frontend/context/me
GET  /api/v1/frontend/bandeja/me
GET  /api/v1/frontend/solicitudes/{request_id_o_folio}/me
POST /api/v1/frontend/solicitudes/me
POST /api/v1/frontend/solicitudes/{request_id_o_folio}/gastos/me
```

Reglas:

- todos requieren `Authorization: Bearer <token>`;
- el rol se toma del token y se devuelve tambien en formato UI: `tienda`, `supervisor`,
  `contabilidad`, `gerencia`, `tesoreria`, `direccion` o `admin`;
- cada solicitud devuelve `id` como folio visible y `backendId` como UUID real;
- cada gasto devuelve `id` para la UI y `backendId` para acciones reales;
- la bandeja ya viene filtrada por rol y tienda asignada;
- `availableActions` contiene las acciones tecnicas disponibles;
- `actionLabels` contiene el texto listo para pintar botones sin inventar reglas en frontend.

## Pagos de tesoreria

Cuando la solicitud esta en `approved_for_payment`, tesoreria o admin registra el pago:

```text
POST /api/v1/reimbursement-requests/{request_id}/payments/me
Authorization: Bearer <token>
```

```json
{
  "reference": "PAGO-0001",
  "payment_method": "transfer",
  "note": "Pago confirmado por tesoreria"
}
```

Si no se manda `amount`, el backend usa el total calculado vigente. Si se manda `amount`, debe
coincidir exactamente con ese total aprobado. La moneda del pago tambien debe coincidir con la
moneda activa de la solicitud. La accion:

- crea una fila en `payments`;
- marca `paid_at` y `paid_by_user_id` en la solicitud;
- cambia la solicitud a `paid`;
- registra auditoria `payment_recorded`.

Los pagos de una solicitud se consultan con:

```text
GET /api/v1/reimbursement-requests/{request_id}/payments
```

## Reglas de negocio

Las reglas configurables se listan con:

```text
GET /api/v1/business-rules/
```

Se crean automaticamente las reglas iniciales:

- `authorization_threshold`: monto a partir del cual un gasto requiere autorizacion.
- `require_cfdi_for_accounting`: bandera para CFDI obligatorio en revision contable.
- `block_out_of_period_expenses`: bandera para bloquear gastos fuera del periodo.
- `auto_adjust_total_on_removed_expense`: bandera para ajustar total al quitar gastos.

Admin puede actualizar una regla:

```text
PATCH /api/v1/business-rules/{rule_code}
Authorization: Bearer <token admin>
```

```json
{
  "value": {"amount": "1500.00", "currency": "MXN"},
  "is_active": true,
  "description": "Monto minimo para mandar un gasto a autorizacion."
}
```

En esta entrega las reglas quedan persistidas y editables. El siguiente paso es conectar
cada regla a su validador especifico para que el comportamiento cambie sin tocar codigo.

## Placeholder de poliza SAP

Este punto esta listo para recibir despues el codigo real que genere la poliza para SAP.
Por ahora no llama a SAP ni genera polizas reales; solamente deja una marca auditable en la
solicitud:

```text
POST /api/v1/reimbursement-requests/{request_id}/sap-policy/prepare
```

```json
{
  "actor_user_id": "00000000-0000-0000-0000-000000000000",
  "reference": "SAP-POL-0001",
  "note": "Poliza preparada por contabilidad"
}
```

Reglas:

- solo funciona cuando la solicitud esta en `accounting_reviewed`;
- solo puede ejecutarlo `accountant` o `admin`;
- el usuario debe estar asignado a la tienda, salvo `admin`;
- guarda `sap_policy_generated_at`, `sap_policy_generated_by_user_id`,
  `sap_policy_reference` y `sap_policy_payload`;
- bloquea `accounting_manager_review` hasta que este paso exista.

## Acciones por gasto

Endpoints:

```text
POST /api/v1/expenses/{expense_id}/authorize
POST /api/v1/expenses/{expense_id}/reject
POST /api/v1/expenses/{expense_id}/observation
PATCH /api/v1/expenses/{expense_id}/review
POST /api/v1/expenses/{expense_id}/remove
```

Reglas:

- `authorize` solo funciona durante `authorization_review` y con rol `authorizer`.
- `reject` solo funciona durante `authorization_review` y con rol `authorizer`; marca el
  gasto como `rejected`, guarda el motivo y puede ajustar el total reportado para que la
  solicitud siga con los gastos restantes.
- Si todos los gastos quedan rechazados/removidos y `expense_count` queda en `0`, el resumen
  genera `no_payable_expenses`. En ese caso la solicitud se bloquea para contabilidad, SAP y
  pago, y el rol revisor activo puede cerrar la solicitud completa como `rejected`.
- En contabilidad, gerencia, tesoreria y direccion el boton/API de rechazar solicitud completa
  solo procede si ya no queda monto pagable; primero se remueven o rechazan los gastos que no
  proceden.
- `observation` funciona en la etapa activa del rol revisor: autorizacion, contabilidad,
  gerente contable, tesoreria o direccion.
- `review` permite editar gastos durante `under_accounting_review` o
  `accounting_manager_review`.
- `remove` exige `reason` y marca el gasto como `removed` sin borrarlo fisicamente. Durante
  `authorization_review`, autorizacion solo puede remover gastos con `requires_authorization=true`;
  durante revision contable o gerencial se puede remover cualquier gasto activo.
- Cuando un gasto se remueve o se edita durante revision, el total reportado se recalcula para
  mantener la solicitud balanceada y la accion queda en auditoria.

## Edicion de datos

La API permite corregir datos antes de enviar. El estado `correction_required` queda como
compatibilidad para datos locales anteriores, pero el flujo nuevo no lo usa para regresar a
tienda:

- `PATCH /api/v1/stores/{store_id}`
- `PATCH /api/v1/periods/{period_id}`
- `PATCH /api/v1/reimbursement-requests/{request_id}`
- `PATCH /api/v1/expenses/{expense_id}`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/users/{user_id}/deactivate`

Las solicitudes, gastos, importaciones, adjuntos y validaciones CFDI se bloquean despues de
`submitted` para evitar cambios silenciosos mientras contabilidad o tesoreria revisan. Si una
revision posterior necesita ajuste, la solicitud baja solo un nivel: gerente la regresa a
contabilidad, tesoreria a gerente y direccion a tesoreria.

Las acciones especiales de revision siguen controladas por rol: contabilidad y gerente pueden
observar, editar durante revision y quitar gastos con motivo sin borrar el historial.

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
- `requiere_autorizacion`, `autorizacion` o `requires_authorization`

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
- gasto removido con motivo, usuario, monto original y proveedor original;
- pago registrado por tesoreria;
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
- sembrar un demo masivo con varias solicitudes en distintos estados para probar bandejas;
- intentar transiciones de estado;
- ver que tienda queda bloqueada si faltan tickets o CFDI vigentes;
- completar CFDI sinteticos de prueba solo antes de enviar;
- probar importacion CSV con `dry_run` o guardado real;
- recorrer la seccion `Flujo usuario final`, agrupada por tienda, sistema, autorizacion,
  contabilidad, gerente, tesoreria y direccion;
- iniciar sesion como rol HUD con token local y ejecutar acciones autenticadas similares a
  las que usara el frontend final;
- probar errores controlados como gasto fuera de periodo y archivo inexistente;
- descargar recibos demo por medio del endpoint protegido de adjuntos;
- ejecutar acciones por gasto desde la vista por rol: autorizar, rechazar, observar,
  quitar y descargar recibo cuando aplique;
- crear tiendas HUD, usuarios HUD y asignarlos de forma operativa;
- crear gastos de prueba en la solicitud HUD;
- quitar gastos durante revision contable usando token;
- registrar pagos formales desde sesion de tesoreria;
- autorizar gastos HUD que requieren aprobacion previa;
- revisar y editar reglas de negocio desde sesion admin;
- preparar la poliza SAP placeholder antes de mandar a gerente;
- limpiar solo los datos con prefijo HUD.

Para una demostracion mas cercana a producto final, sin las herramientas tecnicas de
sembrado avanzado, reglas y consola del HUD, usa la ventana independiente:

```text
http://localhost:8000/product-view
```

Esa vista reutiliza los mismos datos demo y endpoints locales, pero organiza la pantalla por
rol: tienda, validacion automatica, autorizacion, contabilidad, gerente, tesoreria y
direccion. Desde ahi se pueden seleccionar solicitudes demo, seleccionar gastos especificos,
autorizar o rechazar productos, quitar gastos permitidos, regresar revisiones posteriores a
contabilidad, preparar el placeholder de poliza SAP y registrar pagos.

Los endpoints auxiliares viven bajo:

```text
/api/v1/dev-hud
```

Si `ENVIRONMENT=production`, el HUD responde como no encontrado.

## Nuevos endpoints

- `GET /api/v1/dev-hud/status`
- `POST /api/v1/dev-hud/seed-demo`
- `POST /api/v1/dev-hud/seed-bulk-demo`
- `POST /api/v1/dev-hud/stores`
- `POST /api/v1/dev-hud/users`
- `POST /api/v1/dev-hud/assign-user`
- `POST /api/v1/dev-hud/payments`
- `POST /api/v1/dev-hud/automated-review`
- `POST /api/v1/dev-hud/authorize-expenses`
- `POST /api/v1/dev-hud/reject-authorization-expense`
- `POST /api/v1/dev-hud/complete-cfdi`
- `POST /api/v1/dev-hud/prepare-sap-policy`
- `POST /api/v1/dev-hud/transition/{target_status}`
- `POST /api/v1/dev-hud/reset-demo`
- `GET /api/v1/business-rules`
- `PATCH /api/v1/business-rules/{rule_code}`
- `GET /api/v1/work-queue/me`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/users`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/users/{user_id}/deactivate`
- `PATCH /api/v1/stores/{store_id}`
- `POST /api/v1/stores/{store_id}/users`
- `GET /api/v1/stores/{store_id}/users`
- `PATCH /api/v1/periods/{period_id}`
- `PATCH /api/v1/reimbursement-requests/{request_id}`
- `POST /api/v1/reimbursement-requests/{request_id}/automated-review`
- `POST /api/v1/reimbursement-requests/{request_id}/transition`
- `POST /api/v1/reimbursement-requests/{request_id}/transition/me`
- `POST /api/v1/reimbursement-requests/{request_id}/sap-policy/prepare`
- `POST /api/v1/reimbursement-requests/{request_id}/sap-policy/prepare/me`
- `GET /api/v1/reimbursement-requests/{request_id}/payments`
- `POST /api/v1/reimbursement-requests/{request_id}/payments/me`
- `GET /api/v1/reimbursement-requests/{request_id}/audit-events`
- `POST /api/v1/reimbursement-requests/{request_id}/expenses/import`
- `PATCH /api/v1/expenses/{expense_id}`
- `POST /api/v1/expenses/{expense_id}/authorize`
- `POST /api/v1/expenses/{expense_id}/authorize/me`
- `POST /api/v1/expenses/{expense_id}/reject`
- `POST /api/v1/expenses/{expense_id}/reject/me`
- `POST /api/v1/expenses/{expense_id}/observation`
- `POST /api/v1/expenses/{expense_id}/observation/me`
- `PATCH /api/v1/expenses/{expense_id}/review`
- `PATCH /api/v1/expenses/{expense_id}/review/me`
- `POST /api/v1/expenses/{expense_id}/remove`
- `POST /api/v1/expenses/{expense_id}/remove/me`
- `GET /api/v1/attachments/{attachment_id}`
- `GET /api/v1/attachments/{attachment_id}/download`
- `GET /api/v1/attachments/{attachment_id}/download/me`

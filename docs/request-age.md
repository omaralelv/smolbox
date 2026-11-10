# Dias de una solicitud

## Reglas

- Bandeja muestra una columna DIAS por solicitud. Historico conserva el total
  final de las solicitudes pagadas, cerradas o rechazadas.
- El inicio es el primer envio de la tienda. Crear un borrador, abrirlo como
  admin o revisar la fecha del comprobante no inicia ni reinicia el contador.
- Se cuentan dias naturales por fecha de America/Mexico_City. El dia del envio
  es 0; fines de semana cuentan. No son bloques de 24 horas.
- Cambios de etapa, responsable, devoluciones, correcciones y particiones no
  reinician ni pausan el contador.
- Se detiene al pagarse o al rechazarse definitivamente la solicitud. Rechazar
  un gasto individual no lo detiene. Cerrar despues de pagar no agrega dias.
- Sin evidencia suficiente se muestra `Sin fecha`, nunca un cero inventado.
  Los borradores se muestran como `Sin enviar` si una vista los incluye.

El servidor calcula el total, sin consultas adicionales a la bitacora por fila.
El frontend solo presenta ese valor y vuelve a consultar la lista al regresar
a Bandeja o al cambiar el dia de Mexico. Esto no cambia etapas ni responsables.

## Datos y solicitudes anteriores

La migracion `20261028_0026`, posterior a `20261016_0025`, agrega dos fechas
opcionales a `reimbursement_requests`: `first_submitted_at` y `rejected_at`.
No reemplaza `submitted_at`, que conserva su uso actual.

Para solicitudes anteriores se recuperan las primeras fechas comprobables de
envio y rechazo desde transiciones reales de solicitud en `audit_logs`.
Los clics y rechazos de gastos individuales no sirven como evidencia. No se
sobrescriben fechas ya conocidas ni se usan fechas de creacion o facturas para
adivinar un primer envio. Si falta el historial, el valor queda vacio.

Los datos enviados al frontend son `firstSubmittedAt`, `ageStoppedAt`,
`ageCalculatedAt` y `elapsedDays`. Las fechas se transmiten con zona horaria.
Una solicitud terminal sin fecha comprobable de pago o rechazo queda sin
contador calculable, en lugar de seguir creciendo.

## Actualizacion en la VM

Respaldar la base antes de migrar. Desde la carpeta del proyecto:

```powershell
git pull --ff-only origin agent/etapa1-mvp
docker compose up -d --build api
docker compose exec api alembic current
```

El arranque del contenedor ya ejecuta `alembic upgrade head`. La ultima orden
debe mostrar `20261028_0026 (head)`. Revisar los registros del contenedor si no
arranca: no iniciar la aplicacion con un esquema anterior a esta migracion.
La recuperacion historica recorre solicitudes y eventos una sola vez, por lo
que conviene desplegar en una ventana de menor actividad.

Actualizar tambien el frontend. Si se sirve el resultado compilado mediante
IIS, ejecutar en `frontend`:

```powershell
npm ci
npm run build
```

Si se utiliza un servidor de desarrollo, reiniciarlo con la configuracion que
ya usa la VM. Un `git pull` sin reconstruir/reiniciar no actualiza el backend.

## Verificacion

- Pruebas unitarias de calendario, primer envio, reenvios y detencion.
- Pruebas de API con base temporal: lectura sin cambios de etapa o responsable,
  solicitudes independientes, pago, cierre, rechazo y datos historicos ausentes.
- Migracion aislada: recuperacion de eventos, conservacion de datos y reversa.
- Pruebas de navegador con API simulada: seis perfiles, filtros, dias 0,
  falta de fechas, refresco al cambiar el dia y columna en escritorio/movil.
- Regresion de la revision neutral de admin y compilacion del frontend.

Estas comprobaciones no utilizan la VM ni AWS. No se verifico la migracion en
PostgreSQL local, que no esta disponible en este entorno. El intento de ejecutar
toda la cadena sobre SQLite se detuvo en la migracion antigua `20260828_0009`,
que modifica restricciones sin el modo compatible con SQLite; la migracion
nueva si aprobo su prueba aislada.

# Consulta y revision de solicitudes por admin

## Comportamiento

- Abrir una solicitud como admin, consultar sus gastos, volver o actualizar no
  inicia revisiones ni toma la solicitud.
- El administrador conserva la vista neutral de bandeja incorporada en
  `3492012`: no se clasifica como propio o ajeno. La asignacion real del contador
  no se cambia para lograr esa presentacion.
- En Acumulado aparece `Iniciar revision` cuando el backend permite iniciar una
  revision. Solo pulsar ese boton ejecuta el cambio y refresca la solicitud.
- Admin tampoco completa autorizaciones automaticamente al cargar su lista.
  Autorizar un gasto mediante una accion explicita conserva el flujo existente.
- Iniciar revision contable como admin cambia la etapa, pero no toma la
  solicitud: conserva el responsable existente o la deja disponible si no tenia
  responsable. Consultas, ediciones y comentarios de admin no se apropian de ella.
- Los contadores conservan sus reglas de toma, propio y ajeno. Las devoluciones
  de Gerencia a Contabilidad siguen liberando la solicitud y las salidas de la
  cola contable siguen limpiando la clasificacion conforme al flujo existente.
- Los cambios explicitos siguen validando permisos, autorizaciones y requisitos
  de etapa. Se conservan los eventos de botones y cambios de estado de bitacora;
  una consulta de admin no genera `accounting_request_taken`.

No se modifican solicitudes historicas ni se reparan tomas antiguas de manera
automatica. No hay migracion de base de datos. Para desplegar se deben actualizar
tanto el frontend como el backend.

## Verificacion

Las pruebas de backend cubren consultas repetidas en ambos endpoints de detalle,
solicitudes libres y tomadas, conservacion de responsable al iniciar revision,
edicion y comentario de admin, reglas de devolucion y salida de la cola,
autorizaciones pendientes y registro de acciones explicitas.

Las 49 pruebas unitarias del frontend aprobaron. La prueba de navegador
`frontend/tests/adminRequestReview.browser.mjs`, con API simulada, verifica
apertura, detalle, regreso, recarga, cinco inicios manuales, reintento despues de
un conflicto, registro de clics, y controles nuevos en escritorio y movil. Las
pruebas con API real de test usan bases SQLite temporales, no la VM ni AWS.

La revision ampliada de backend registro 161 pruebas aprobadas, tres fallas y una
omitida. Las tres fallas se reprodujeron en una exportacion limpia de `3492012`,
antes de este cambio:

- `test_frontend_add_rejects_expense_before_previous_close`: la prueba espera que
  el mensaje de fecha no contenga el anio.
- `test_removing_every_partition_does_not_restore_the_original_amount`: la
  restauracion del original al eliminar todas las particiones difiere de lo
  esperado por la prueba.
- `test_partition_edit_invalidates_an_already_prepared_sap_policy`: la prueba
  espera bloquear el avance por poliza previa despues de editar particiones.

No se modificaron esos comportamientos como parte de este ajuste.

# Revisión del flujo de particiones

Fecha: 15 de octubre de 2026. Código revisado: `9a9d7a9`, rama `agent/etapa1-mvp`.

Actualización posterior: se implementaron las correcciones de comentarios y
recarga detalladas en [Corrección de comentarios](correccion-comentarios-2026-10-15.md).
Este documento conserva los resultados de la revisión inicial; los dos hallazgos
financieros de monto original y póliza siguen pendientes.

## Alcance

Se dejó pendiente la corrección del chat de Contabilidad. En esta revisión solamente
se añadieron pruebas y este reporte: no se modificaron reglas, pantallas, servicios,
migraciones ni datos de la aplicación. No se hizo commit ni push.

Las pruebas usaron bases SQLite temporales, documentos XML sintéticos, usuarios de
prueba y servidores locales en puertos libres. Textract, Cognito y el envío de
correos estuvieron desactivados. El pago mencionado abajo es un registro de prueba,
no un movimiento bancario.

## Hallazgos Confirmados

### P1. Eliminar todas las partes reactiva el gasto original

Reproducción: gasto de $1,500.00, particiones de $1,160.00 y $340.00, eliminación
individual de ambas partes con ajuste de total. El resultado vuelve a ser
**$1,500.00 y un gasto activo**, sin utilizar «Anular partición».

La selección de gastos pagables oculta al padre únicamente mientras existe algún
hijo activo. Al eliminar el último hijo, vuelve a incluirlo automáticamente.
Esto puede reincorporar un importe que Contabilidad acababa de excluir.

Código: `app/services/reimbursement_validation.py:324` y
`app/api/v1/endpoints/frontend.py:1822`.

Prueba: `test_removing_every_partition_does_not_restore_the_original_amount`.

Corrección pendiente: distinguir explícitamente la anulación del grupo de la
eliminación de sus partes. Restaurar el original solamente al anular la partición.

### P1. Una partición editada puede avanzar con una póliza anterior

Reproducción: crear partición, finalizar revisión contable, preparar póliza, cambiar
una categoría de la partición e intentar enviar a revisión de gerencia. El servidor
acepta el avance con **200**, sin exigir preparar otra póliza.

La edición conserva `sap_policy_generated_at`. El control de avance comprueba
únicamente que esa marca exista, no que corresponda a los datos actuales.

Código: `app/api/v1/endpoints/frontend.py:1144` y `app/services/workflow.py:258`.

Prueba: `test_partition_edit_invalidates_an_already_prepared_sap_policy`.

Corrección pendiente: invalidar o versionar la preparación y los archivos derivados
cuando cambian datos contables, y exigir que correspondan a la revisión actual.

### P2. Los comentarios anteriores dejan de verse al editar la partición

Reproducción: comentar la primera parte y después editar su impuesto. La nota sigue
en la bitácora, pero no aparece al abrir las observaciones de la parte editada.

Cada guardado elimina lógicamente los hijos activos y crea otros con IDs nuevos.
Las observaciones siguen vinculadas al ID anterior; el filtro visual solamente
considera el hijo actual y su gasto padre. **No se pierde la información guardada,
pero sí su acceso desde la parte vigente.**

Código: `app/api/v1/endpoints/frontend.py:1058`,
`app/api/v1/endpoints/frontend.py:1098` y
`frontend/src/lib/observationHistory.js:78`.

Pruebas: `test_partition_edit_keeps_previous_child_note_visible_on_current_child`
y recorrido de navegador `child-note-after-replacement`.

Corrección pendiente: conservar la identidad de las partes que se editan o
persistir una relación de reemplazo que permita recuperar su historial sin mezclar
notas de otras partes.

### P2. Recargar Detalle puede mostrar particiones antiguas

Reproducción en navegador: abrir desde el acumulado, editar/anular/recrear una
partición y recargar Detalle sin regresar primero. Se muestran IDs de partes
anteriores, aunque el servidor devuelve correctamente las partes actuales.
Volver al acumulado y entrar de nuevo recupera los datos vigentes.

Detalle inicializa su lista con `location.state.desglose` y no consulta la solicitud
al recargar. Las operaciones actualizan el estado del componente, no esa copia de
navegación.

Código: `frontend/src/pages/Detalle.jsx:112` y
`frontend/src/pages/Detalle.jsx:631`.

Prueba de navegador: `detail-reload-stale-partitions`.

Corrección pendiente: cargar el detalle vigente desde el servidor al entrar o
recargar, usando la información de navegación solo como estado inicial provisional.

### Pendiente Previo. Chat y fecha de creación en Contabilidad

Se reprodujo el problema que el usuario pidió dejar pendiente:
`Acumulado -> Detalle` pierde `canAddObservation` y `createdAt` al reconstruir los
gastos. Se oculta el editor de comentarios y aparece «Fecha no disponible» en la
descripción automática de las partes. El servidor sí envía ambos campos.

Código: `frontend/src/pages/Acumulado.jsx:137` y
`frontend/src/lib/observationHistory.js:91`.

Pruebas de navegador: `known-accounting-chat-mapping` y
`known-missing-partition-created-at`.

No se corrigió durante esta revisión.

## Verificaciones Satisfactorias

| Caso | Resultado |
| --- | --- |
| Captura en tienda y envío | Gasto y observación inicial persistidos. |
| Autorización requerida con monto positivo | No permite entrar a Contabilidad antes de autorizar. |
| Supervisor de la tienda | Autoriza el gasto dirigido a Supervisores. |
| Partición inicial | Padre oculto, dos partes activas, total sin duplicarse. |
| Impuestos manuales 0%, 8% y 16% | Importes, subtotales e índices W0/W6/W1 conservados. |
| Comprobante de las partes | Heredan el folio y la descarga del archivo original; lectura 200. |
| Editar desde una parte | Abre el modal de partición, no el de gasto normal. |
| Volver al acumulado y al detalle | Mantiene color, conteo y herramientas de las partes vigentes. |
| Anular explícitamente | Restaura el original y oculta las partes anuladas. |
| Volver a particionar | No precarga ni muestra las partes anuladas anteriores. |
| Conservación en base de datos | Permanecen las partes anteriores como eliminadas, para auditoría. |
| Bitácora y observaciones de movimientos | Registra creación, edición y anulación, con categorías, montos, impuestos y valores anteriores/nuevos. |
| Entradas inválidas | Rechaza monto cero, negativo, suma incorrecta, categoría vacía, impuesto negativo y menos de dos partes; sin escrituras parciales. |
| Particionar una parte | Rechazado por backend y deshabilitado en la pantalla probada. |
| Permisos de particiones | Matriz de 7 roles y 17 estados, para crear/editar y anular: 238 comprobaciones. Solo Contabilidad/Admin en las dos etapas contables permitidas. |
| Etapas posteriores | Revisión de gerencia, tesorería, autorización de pago y pago de prueba conservan conteo y total. |
| Solicitud pagada | Bloquea particionar, anular y añadir observaciones. |
| Macro | ZIP y Excel reales: solo las dos partes activas, folio compartido, impuestos elegidos y contrapartida de -$1,500.00. |
| Carga y descarga del reembolso | El Excel generado se carga y se recupera sin modificar sus bytes. |

La suma válida se probó a centavos exactos. No se modificó la tolerancia existente
de un centavo ni las reglas fiscales iniciales de categoría/tienda.

## Resultados de Ejecución

- Casos nuevos de API: **11 aprobados, 3 fallidos y 1 omitido**. El omitido es el
  navegador, que se ejecutó por separado. Las tres fallas reproducen los problemas
  de monto original, comentarios y póliza descritos arriba.
- Navegador con frontend y backend reales: recorrido completo terminado; la prueba
  queda fallida por cuatro comprobaciones: chat, fecha de creación, comentarios
  anteriores y datos viejos al recargar. No se simularon las respuestas de la API.
- Pruebas unitarias del frontend: **40 aprobadas**.
- Compilación del frontend: correcta; permanece el aviso de paquete mayor de 500 KB.
- Revisión estática del archivo nuevo de Python: correcta.
- Suite general final: **399 aprobadas, 12 fallidas y 1 omitida**. De las fallas,
  tres corresponden a los casos nuevos de particiones y nueve a pruebas existentes.

Las pruebas nuevas fallidas se dejaron activas: no se ocultaron ni se marcaron
como aprobadas. Servirán para verificar las correcciones posteriores.

## Otras Fallas de la Suite Existente

La primera ejecución general encontró nueve fallas en pruebas ya existentes,
separadas de las tres regresiones nuevas de particiones:

- Cuatro pruebas exigen que el mensaje de periodo no contenga «2026», aunque el
  mensaje actual incluye la fecha del cierre anterior. Archivos:
  `test_api_integrity.py`, `test_expense_import_api.py`,
  `test_frontend_adapter_api.py`, `test_reimbursement_validation.py`.
- Automated review espera `blocked`, pero recibe `attention`.
- Dev HUD espera `ready_for_submission = false`, pero recibe `true`.
- CORS: el origen local probado recibe 400 con la configuración actual.
- Macro: una prueba espera el color `00FFFF00`, pero la celda utiliza `00FFFADD`.
- Los datos de prueba intentan insertar un segundo corte inicial para la misma
  tienda y violan la restricción de unicidad.

No se corrigieron estas fallas ni se cambiaron sus expectativas.

## Evidencia y Repetición

Pruebas añadidas:

- `tests/test_partition_flow_api.py`
- `frontend/tests/partitionFlow.browser.mjs`
- `frontend/tests/partitionFlow.vite.mjs` (configuración exclusiva de pruebas)

API y suite general, siempre sin una conexión externa de pruebas:

```sh
env -u SMOLBOX_TEST_DATABASE_URL .venv/bin/pytest tests/test_partition_flow_api.py -q
env -u SMOLBOX_TEST_DATABASE_URL .venv/bin/pytest -q --disable-warnings --tb=short
```

Para ejecutar navegador, definir `NODE_EXECUTABLE`, `PLAYWRIGHT_MODULE` y
`CHROME_EXECUTABLE` con sus rutas locales y activar `SMOLBOX_PARTITION_BROWSER=1`:

```sh
env -u SMOLBOX_TEST_DATABASE_URL SMOLBOX_PARTITION_BROWSER=1 \
  .venv/bin/pytest tests/test_partition_flow_api.py::test_real_browser_partition_navigation \
  -q -s --basetemp=/tmp/smolbox-partition-audit-browser
```

El recorrido guarda su lista de peticiones, hallazgos y capturas en
`/tmp/smolbox-partition-audit-browser/test_real_browser_partition_na0/`:
`partition-browser-results.json`, `partition-created.png`,
`partition-recreated.png`, `partition-history.png`, `partition-mobile.png`.
Es evidencia temporal, no contiene tokens de sesión.

## Límites

No se probó la máquina virtual ni su base PostgreSQL. Para probar el generador real
de Excel con SQLite se utilizó una adaptación de tipos exclusivamente en las
pruebas; la selección SQL y la generación de archivos no fueron simuladas. No se
certifica aquí la importación final a SAP, AWS, Cognito, correos, concurrencia de
varios usuarios ni recuperación ante cortes de red.

Se capturó también la vista de 390 px: la tabla y las observaciones se comprimen y
hay herramientas fuera del área visible. No se hicieron cambios de diseño ni se
consideró aprobada una revisión completa de uso móvil.

# Solicitudes extemporaneas informativas

## Comportamiento

Admin y Contabilidad capturan desde el boton de Historico. El selector consulta
tiendas con una asignacion activa de Tienda y un usuario activo, sin asignar
tiendas artificialmente al contador ni abrir los permisos del borrador normal.

Cada usuario tiene su propio borrador extemporaneo por tienda, recuperable
desde el servidor al regresar, recargar o entrar desde otra computadora.
Anadir, eliminar y comentar gastos durante la captura se registra en bitacora.
Los movimientos anteriores a Anadir tambien se envian al servidor.

La fecha del comprobante no depende de periodos de reembolso. Se mantienen
formato y limites de archivos, OCR de PDF, receptor esperado, validacion exacta
del RFC del XML y control de folios fiscales duplicados. Las diferencias
permitidas entre datos capturados y comprobante mantienen la confirmacion
adicional existente. Las reglas de autorizacion del flujo normal no se ejecutan
para estos registros informativos.

Al enviar se verifica que la lista de gastos no haya cambiado y que todos
tengan evidencia validada. El servidor asigna un folio unico de tienda, fecha
de registro (zona de Mexico) y consecutivo: `E-FE003-031120261`,
`E-FE003-031120262`, etc. El contador es por tienda y dia, separado del normal;
al reintentar una solicitud ya registrada se conserva su folio. Se guarda
el archivo historico con estado `paid`, presentado como **Pagada** y con la
columna **Extemporaneo**. DIAS muestra `-`. No es un pago procesado por Smolbox.
No se crean registros Payment ni correos de pago.

Historico combina ambas fuentes sin convertir registros extemporaneos en
solicitudes de reembolso. Al abrir uno se consultan gastos, observaciones y
comprobantes; tambien se puede descargar un ZIP. Una vez registrado es de
solo lectura. Los permisos de consulta siguen el alcance de cada perfil;
los comentarios internos no se entregan a Tienda o Autorizacion.

La creacion de gastos y las observaciones tienen identificadores estables
para reintentos. La confirmacion final es repetible sin generar otro folio ni
duplicar el gasto en los dashboards. Las eliminaciones conservan los datos y
la bitacora, pero no se muestran ni se suman en el registro vigente.

## Aislamiento y dashboards

Las tablas nuevas son `historical_requests`, `historical_expenses` y
`historical_attachments`. No tienen relacion con periodos, solicitudes normales,
pagos, polizas ni autorizaciones. Los comprobantes originales se almacenan
bajo `UPLOAD_DIR/extemporaneos/`, conservando la configuracion de almacenamiento.
Las lecturas OCR reutilizadas se guardan en `historical_attachments.ocr_data`.

Los eventos usan `audit_logs` con sus referencias normales vacias y el campo
`payload.historical_request_id`. Se muestran con tienda, usuario, rol y folio.
No representan transiciones ni actividad productiva de una solicitud normal.

El dashboard de gastos/presupuestos agrega los gastos no eliminados de los
archivos registrados, por tienda y anio de la fecha del comprobante. No suma
borradores. Los indicadores de productividad de Contabilidad, Gerencia y
Tesoreria mantienen sus consultas y no cuentan estas capturas como revisiones,
autorizaciones o pagos realizados dentro del flujo.

El filtro Tipo de solicitud del dashboard permite Todas, Normales y Extemporaneas,
combinado con el de tienda. Cambia indicadores, grafica y tabla usando un mismo
desglose recibido del backend, sin recargar los catalogos al cambiar el filtro.
Normales incluye los acumulados importados sin marca individual; Extemporaneas
solo suma gastos del archivo extemporaneo registrado. La API conserva `values`
con el total y agrega `normalValues` y `extemporaneousValues` por tienda/anio.

La tabla solo muestra tiendas con registros compatibles con el tipo y la tienda
seleccionados, dentro de los tres anios visibles. Todas combina ambas fuentes;
una tienda sin registros no aparece, aunque siga disponible en el selector.
La API incluye `hasNormalData` y `hasExtemporaneousData`, calculados con las
mismas consultas de importes. Un gasto o acumulado valido de cero cuenta como
dato: no se descarta una tienda por su importe. No cuentan borradores, gastos
excluidos ni registros fuera de esos anios. Indicadores y grafica se calculan
con las mismas filas filtradas de la tabla. Una seleccion sin coincidencias
muestra el aviso de tabla vacia, importes cero y variacion N/A.

Este ajuste no agrega columnas de base de datos ni migraciones. Es necesario
actualizar backend y frontend. Si el backend anterior no envia esas marcas,
el frontend conserva las filas y deshabilita el filtro de tipo para evitar
deducir ausencia de registros a partir de ceros. El filtro de tienda sigue
funcionando; no hay consultas extra al cambiar los filtros.

La verificacion de este ajuste aprobo 98 pruebas de backend y 62 de frontend,
ademas de compilacion y navegador de escritorio/movil. Se excluyo la prueba de
CORS local ya documentada. Se probaron los siete roles, tiendas con una o ambas
fuentes, registros validos de cero, ausencia de datos, anios fuera de rango y
compatibilidad con respuestas anteriores. No se actualizo la VM desde aqui.

Los acumulados historicos importados previamente son cantidades agregadas,
sin folios individuales para conciliarlos. Si un comprobante ya estaba incluido
en uno de esos acumulados, debe conciliarse antes de volver a sumarlo como
extemporaneo. No se restan ni modifican automaticamente esos acumulados.

No se modifican cortes, periodos, solicitud anterior, consecutivos normales,
montos anteriores, responsables ni la macro SAP. El unico control compartido
adicional es detectar un Folio Fiscal ya guardado en un extemporaneo.

## Actualizacion de la VM

Respaldar la base de datos y los archivos antes de actualizar. La migracion
`20261103_0027`, posterior a `20261028_0026`, crea solo las tres tablas nuevas.
No modifica registros anteriores. Su reversa elimina las tablas del archivo
extemporaneo; no debe ejecutarse despues de capturar datos sin respaldo.

La siguiente migracion `20261103_0028` transforma los folios extemporaneos antiguos
con UUID al nuevo formato. Asigna los consecutivos por orden de registro,
conserva la tienda y fecha del folio anterior, respeta los numeros ya existentes,
y registra el folio anterior y nuevo en
bitacora sin borrar eventos previos. No cambia folios normales, gastos, estados,
comprobantes ni totales. Su reversa restaura solo los folios transformados y
conserva el registro de auditoria. Detener el backend anterior al migrar.

Desde la carpeta del proyecto:

```powershell
git pull --ff-only origin agent/etapa1-mvp
docker compose up -d --build api
docker compose exec api alembic current
```

El contenedor ya ejecuta las migraciones al iniciar. La revision esperada es
`20261103_0028 (head)`. Para backend sin Docker, detener el proceso anterior,
ejecutar `alembic upgrade head` y volver a iniciarlo.

Actualizar tambien el frontend. Si se publica con IIS, ejecutar en `frontend`:

```powershell
npm ci
npm run build
```

Si se utiliza Vite en la VM, reiniciar ese proceso con su configuracion actual.
Actualizar solo el frontend o solo el backend deja incompleta esta conexion.

Las entradas falsas de Historico guardadas por la pantalla anterior en un
navegador no se convierten automaticamente en archivos reales. Tampoco se
reclasifican solicitudes normales creadas antes de este ajuste. Esos casos
requieren revision para evitar duplicar sus comprobantes o totales.

## Verificacion

Las pruebas de API usan bases temporales, archivos XML reales y OCR simulado
para PDF, sin llamadas a AWS ni acceso a la VM. Cubren permisos, borradores por
usuario, confirmacion repetida, archivos originales y ZIP, observaciones,
privacidad, evidencias invalidas, folios duplicados, sumas por anio y aislamiento
del reembolso normal. La migracion se prueba aisladamente en SQLite.

La prueba de navegador `frontend/tests/historicalRequests.browser.mjs` usa una
API simulada para verificar Admin y Contabilidad, captura, OCR, regreso correcto,
recarga, comentarios, consulta historica y disposicion escritorio/movil. La
compilacion no sustituye estas pruebas ni confirma un despliegue en la VM.

La regresion ampliada aprobo 113 pruebas y encontro una falla de CORS local en
`test_frontend_origin_is_allowed_by_main_app`. La misma falla se reprodujo en
una exportacion limpia de `97c8293`, antes de este ajuste, con la configuracion
local de origenes. No se modifico CORS. Una prueba antigua que espera otro texto
del periodo se excluyo del recorrido ampliado. PostgreSQL y la VM no se probaron
en este entorno; la verificacion de migracion fue aislada en SQLite.
El recorrido final de aislamiento, CFDI, contador, autorizaciones, correo de
pago y workflow aprobo 110 pruebas. Las 54 pruebas unitarias del frontend,
compilacion y pruebas de navegador de extemporaneos y revision neutral de Admin
tambien aprobaron. El navegador verifico adicionalmente la captura normal con
el formulario compartido, sin llamadas al archivo extemporaneo.

La actualizacion del consecutivo y filtro incluye pruebas de secuencia con
varios usuarios, tiendas, cambio de dia en Mexico, numeros de dos digitos y
recuperacion ante folio duplicado. La migracion se verifica con folios anteriores,
numeros ya reservados, reversa y auditoria conservada. El navegador prueba ambos
filtros combinados, indicadores, grafica, tabla, compatibilidad con el backend
anterior y vistas de escritorio/movil. No se migro la VM desde este entorno.
Resultado: 114 pruebas de backend, 57 unitarias de frontend, compilacion y
recorridos de navegador de captura y filtros aprobados. Permanece la regla de
lint preexistente sobre setState dentro del efecto de productividad; no se
modifico ese flujo. La migracion de datos se probo en SQLite, no en PostgreSQL.

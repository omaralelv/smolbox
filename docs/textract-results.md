# Lecturas OCR guardadas

## Que se conserva

Las lecturas nuevas se guardan en la tabla `ocr_extractions` de la base de datos:

| Campo | Contenido |
| --- | --- |
| `raw_text` | Texto reconocido, sin limitarlo al folio, fecha o total sugeridos. |
| `raw_response` | JSON devuelto por AWS, incluidos bloques, geometria, confianza y metadatos que AWS haya entregado. |
| `extracted_total`, `extracted_date`, `extracted_supplier`, `suggested_cfdi_uuid`, `confidence` | Campos interpretados por la aplicacion. |
| `document_checksum_sha256`, `source_filename` | Huella del archivo original y nombre del comprobante. |
| `status`, `error_message`, `created_at` | Resultado, error cuando corresponda y momento del guardado. |
| `receiver_validation` | Comparacion del RFC y razon social del receptor: valores detectados, esperados y tolerancia aplicada. |

El guardado ocurre desde `POST /api/v1/cfdi/ocr-preview`: no depende de presionar
Anadir ni de crear un gasto. Si el documento se lee pero no cumple la validacion
del receptor, se conserva lo leido y se mantiene la alerta existente. Una lectura
vacia conserva la respuesta recibida cuando este disponible. Si AWS falla sin
entregar una lectura, se registra el error tecnico, no un resultado inventado.

Los PDF digitales pueden leerse localmente sin llamar a AWS. En esos casos se
guarda el texto extraido y `raw_response` permanece vacio: no hay respuesta de
Textract. Las respuestas combinadas de AnalyzeExpense y DetectDocumentText se
conservan en `sources`; las lecturas de paginas renderizadas se agrupan en `pages`.

## Al anadir el comprobante

El token de validacion firmado identifica la lectura guardada. Se comprueban la
firma y la huella del archivo original antes de reutilizarla. El adjunto recibe
una copia del texto, campos y JSON completos; no se vuelve a llamar a AWS.
La lectura previa permanece independiente, aunque luego se elimine el gasto.
El archivo original no se reconvierte ni reemplaza para almacenarlo.

Los tokens anteriores siguen funcionando, pero contienen solo un resumen y no
permiten recuperar texto o JSON que nunca se guardaron. Los comprobantes antiguos
que perdieron esos datos requieren una nueva lectura.

## Consultar una lectura

Para un comprobante ya adjunto existe:

```text
GET /api/v1/attachments/{attachment_id}/ocr/me
Authorization: Bearer <token de sesion>
```

Requiere sesion y los mismos permisos de tienda, area y etapa que descargar ese
comprobante. Devuelve el texto, JSON y campos extraidos. Un adjunto sin lectura
guardada devuelve 404. No se agregaron pantallas ni se incluyeron los datos crudos
en los listados, tokens del formulario o mensajes de la bitacora.

Las lecturas previas, todavia sin adjunto, se consultan internamente en la base de
datos. Por ejemplo, en una conexion autorizada y usando parametros:

```sql
SELECT id, source_filename, created_at, status, raw_text, raw_response,
       extracted_total, extracted_date, suggested_cfdi_uuid, error_message
FROM ocr_extractions
WHERE document_checksum_sha256 = :checksum_sha256
ORDER BY created_at DESC;
```

No hay un endpoint publico que exponga las lecturas previas.

## Activar en una instalacion existente

1. Respaldar la base de datos y actualizar el backend.
2. Ejecutar `alembic upgrade head` en el entorno del backend. La migracion
   `20261016_0024` conserva los registros existentes y permite guardar lecturas
   sin adjunto; `20261016_0025` agrega el resultado de comparacion del receptor.
   Ejecutarlas antes de iniciar la API actualizada.
3. Verificar `TEXTRACT_STORE_RAW_RESPONSE=true` en las variables del backend y
   reiniciarlo. El nuevo valor predeterminado es `true`, pero un `false` explicito
   en el entorno o en `.env` tiene prioridad. No hace falta cambiar credenciales.
4. Validar de nuevo un comprobante para generar una lectura nueva.

Con `TEXTRACT_STORE_RAW_RESPONSE=false` se mantiene el texto y los campos
extraidos, pero no el JSON completo. Las alertas y validaciones no cambian.

El JSON contiene informacion de facturas y aumenta el uso de base de datos.
Proteger accesos y respaldos, y definir una politica de retencion antes de purgar
lecturas. No hay borrado automatico. Una validacion seguida de un adjunto conserva
dos registros para no perder la evidencia previa. La migracion inversa se bloquea
si existen lecturas sin adjunto, evitando eliminarlas silenciosamente.

## Tolerancia del receptor en OCR

Solo la razon social y el RFC del receptor de una factura leida por OCR admiten
hasta tres cambios, caracteres adicionales o caracteres faltantes por campo.
Primero se eliminan diferencias de mayusculas, acentos, espacios y signos; estas
no consumen tolerancia. Ambos campos deben estar presentes y cumplir su limite.
La fecha, monto, folio fiscal y validacion XML no usan esta tolerancia.

Se separan los bloques de emisor y receptor cuando aparecen identificados. Si hay
varios receptores, no se combinan sus campos. Encabezados ambiguos o multiples
identidades sin identificar no se aprueban usando datos de otro bloque. Se
conserva compatibilidad con textos simples sin encabezados. Si no se consigue
identificar ambos campos o alguno supera tres diferencias, se mantiene el rechazo
y la alerta actual. No se agregaron controles ni mensajes al formulario.

La extraccion separa el nombre y RFC de una direccion que comienza en otro
renglon o una columna delimitada, usando indicadores de calle/avenida y numero
o S/N. Conserva nombres en varios renglones; no recorta un nombre solo porque
empiece a coincidir con el esperado. Etiquetas como `DOMICILIO RECEPTOR`,
`REGIMEN FISCAL RECEPTOR` y `USO DEL CFDI POR EL RECEPTOR` no crean otro receptor.
Esta correccion no requiere otra migracion: usa `20261016_0025` y se aplica al
validar nuevamente el archivo, sin alterar lecturas anteriores guardadas.

En `receiver_validation`, `fields.rfc` y `fields.razon_social` guardan `expected`,
`detected`, `normalized_detected`, `accepted`, `match_type` y `edit_distance`.
`match_type` indica `exact`, `tolerated`, `mismatch`, `missing` o `not_required`.
La distancia se guarda cuando esta entre 0 y 3; fuera del limite queda vacia, no
se presenta como si fuera una distancia exacta de cuatro. Tambien se guarda el
limite, el contexto y los campos rechazados. Esta evidencia se copia al adjunto
al reutilizar la validacion y se consulta en el mismo endpoint protegido de OCR.

`raw_text` y `raw_response` no se corrigen ni sustituyen por los valores esperados.
Las lecturas anteriores no se recalculan; su `receiver_validation` queda vacio.
Esta tolerancia es una regla de lectura, no una comprobacion de identidad: un RFC
distinto que este dentro de tres cambios puede aceptarse conforme a esta regla.

`status=succeeded` indica que el OCR leyo el documento, no que el receptor fue
aceptado. Para comprobar esto ultimo, consultar `receiver_validation.accepted`.

### Verificacion del cambio (2026-10-16)

Las pruebas cubren coincidencia exacta, normalizacion, de uno a tres cambios por
campo (sustituciones, inserciones y eliminaciones), cuatro cambios rechazados,
campos ausentes, emisor/receptor separados, bloques ambiguos, conservacion de
texto/JSON, reutilizacion del OCR, permisos y migracion. Los XML con RFC distinto
siguen rechazandose. No se hicieron llamadas reales a AWS en estas pruebas.

La revision general registro 496 pruebas aprobadas, 14 fallas y una omitida.
Once fallas ya estaban identificadas en otras areas; las tres adicionales son
pruebas de macro SAP que esperan datos sin `expense_content_revision`. Estas
ultimas se reprodujeron en una exportacion limpia de `eda962e`, sin este cambio.
No se corrigieron fallas ajenas al alcance del OCR.

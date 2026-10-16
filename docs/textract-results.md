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
   sin adjunto. Ejecutarla antes de iniciar la API actualizada.
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

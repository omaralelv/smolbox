# Corrección de comentarios

Fecha: 15 de octubre de 2026.

## Resultado

Se corrigió el flujo de comentarios manteniendo los permisos por etapa que confirmó
el usuario. No se abrieron permisos nuevos ni se cambió la separación entre
comentarios públicos e internos.

- El chat y la fecha de creación llegan completos desde Acumulado a Detalle.
- Detalle consulta los gastos vigentes al entrar y recargar; no reutiliza una
  partición antigua como si fuera la actual.
- Editar una partición conserva el identificador de sus partes existentes y sus
  comentarios. Si se reduce el número de partes, las retiradas conservan su historial.
- Las notas de partes anuladas, eliminadas o reemplazadas anteriormente se recuperan
  desde los registros existentes y aparecen como «Partición anterior X/Y».
- Se conserva la exclusión de comentarios de otras partes activas y de otras
  solicitudes. Los comentarios internos no se muestran a Tienda ni Supervisor.
- Cada envío tiene un identificador. El doble clic o el reintento del mismo envío
  no agrega otro comentario; dos envíos intencionales con igual texto se conservan.
- La comprobación también cubre dos envíos concurrentes. La unicidad se apoya en
  la clave primaria existente de la bitácora, sin una migración nueva.
- Reintentar un envío ya guardado reconoce el guardado anterior aunque haya
  cambiado la etapa. No permite crear comentarios nuevos en solicitudes pagadas
  o cerradas ni modificar el comentario original.
- Se conserva el historial paginado y su deduplicación por identificador, no por
  texto; se verifica con más de 200 comentarios.

## Verificación

- Suite general: **405 aprobadas, 11 fallidas, 1 omitida**. La omitida es el
  navegador, ejecutado por separado.
- Frontend: **44 pruebas unitarias aprobadas** y compilación correcta.
- Navegador: recorrido completo con frontend/backend reales y base temporal,
  incluyendo respuesta perdida después del guardado, reintento sin duplicación,
  edición, anulación, nueva partición, recarga e historial. Sin hallazgos pendientes
  en ese recorrido.
- También pasaron los recorridos de historial de los siete perfiles, estados de
  solo lectura, fallos de consulta, doble clic y navegación de autorización.
- Revisión estática de Python: correcta.

La suite general no quedó completamente aprobada: conserva nueve fallas de las
pruebas existentes documentadas en la revisión anterior, más los dos casos de
particiones que reactivan el monto original al eliminar todas las partes y que
permiten avanzar con una póliza anterior. No se corrigieron esos dos casos
financieros ni se ocultaron sus pruebas.

ESLint también señala tres problemas ya existentes en los archivos revisados:
el manejo de `cause` en el reintento de sesión de `api.js` y dos declaraciones
dentro de un `case` en `Acumulado.jsx`. No se modificaron esas líneas.

## Aplicación y Límites

Las pruebas se ejecutaron localmente; no se hizo despliegue en la máquina virtual.
Para activar el cambio deben actualizarse frontend y backend juntos. No requieren migración ni
reescritura de comentarios existentes. Las relaciones históricas se obtienen de
los gastos y la bitácora conservados.

Las pruebas no usaron solicitudes reales, AWS, correos ni pagos bancarios. Se
probaron con SQLite temporal; no certifican PostgreSQL ni servicios de la máquina
virtual. No se cambiaron las reglas de impuestos, autorizaciones o pólizas.

La evidencia temporal del recorrido está en
`/tmp/smolbox-comments-flow-browser/test_real_browser_partition_na0/`.
La revisión inicial queda en [QA de particiones](qa-particiones-2026-10-15.md).

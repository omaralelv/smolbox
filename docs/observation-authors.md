# Autor de las observaciones

El visor compartido presenta nombre, rol y fecha de cada observacion del flujo
normal. El rol sigue siendo un campo separado; no se utiliza el nombre para
permisos, visibilidad, alineacion de mensajes ni reglas de etapa.

## Identidad y compatibilidad

- Los comentarios, notas iniciales y movimientos visibles en observaciones
  guardan `actor_name` en el JSON de auditoria con el nombre del usuario
  autenticado en el servidor. No se acepta el autor indicado por el navegador.
- Las consultas del historial y la bitacora prefieren ese nombre guardado. Si
  falta en eventos anteriores, consultan al usuario vinculado por `actor_user_id`.
- Un cambio posterior de nombre o la eliminacion del usuario no altera el
  nombre ya guardado. Un evento antiguo sin copia ni usuario recuperable se
  muestra como `Usuario no disponible`, conservando el rol cuando se conoce.
- Las descripciones automaticas de particion y eventos de sistema mantienen
  `SISTEMA`. No se atribuyen al usuario que abre la pantalla.
- Las notas heredadas de un gasto original o particion anulada conservan su
  autor. No se copian comentarios ni se cambian sus identificadores o fechas.

No hay cambios de tablas ni migracion nueva. Los datos anteriores no se
reescriben para inventar nombres. Se mantienen permisos por etapa, comentarios
publicos/internos, paginacion, reintentos y bloqueo de solicitudes pagadas.

## Actualizacion y pruebas

Actualizar backend y frontend juntos. Reiniciar/reconstruir el backend y
publicar o reiniciar el frontend segun el procedimiento habitual de la VM.

Las pruebas cubren dos usuarios del mismo rol, nombres falsos enviados desde
el navegador, renombrado/eliminacion de usuario, notas iniciales y antiguas,
privacidad, reintentos y ciclo de particiones. El navegador verifica los siete
perfiles, nombres largos, escritorio/movil y recuperacion ante fallos de lectura.

Resultado de la verificacion local: 143 pruebas de backend aprobadas, con las
tres fallas anteriores documentadas abajo excluidas y una prueba optativa
omitida en esa corrida. La prueba optativa de navegador con API y base temporal
reales se ejecuto por separado y aprobo. Tambien aprobaron las 60 pruebas
unitarias del frontend, su compilacion y el navegador simulado de observaciones.
No se desplego ni se modifico la base de datos de la VM.

## Fallos anteriores detectados

La regresion se contrasto con una exportacion limpia de `498454c`, sin este
cambio, y reprodujo estos problemas existentes:

- Al eliminar todos los hijos de una particion se restaura el importe original.
- Una poliza invalidada por editar una particion todavia permite un avance que
  la prueba espera bloquear.
- La comprobacion de CORS local rechaza el origen usado por la prueba.

No se modificaron esos procesos en este ajuste. Tambien se actualizo la prueba
de atomicidad para no comparar `ageCalculatedAt`, que cambia en cada consulta;
el resto de los datos y los eventos siguen comparandose completos.
El lint de Drawer conserva dos errores anteriores: setState dentro de un efecto
y una clave padding repetida. Ninguno corresponde a las lineas modificadas.

// Niveles de visibilidad de los comentarios
export const VISIBILIDAD = {
    PUBLIC: 'PUBLIC',             // Tienda, Supervisor y Administradores/Dirección
    INTERNO: 'INTERNO'            // Solo Contabilidad, Gerencia, Tesorería y Dirección
};

// Matriz de permisos de lectura para Observaciones
export const PUEDE_LEER_OBSERVACION = (rolUsuario, visibilidadComentario) => {
    const rol = String(rolUsuario).toLowerCase().trim();

    if (visibilidadComentario === VISIBILIDAD.PUBLIC) {
        return true; // Lo ven TODOS los roles
    }

    if (visibilidadComentario === VISIBILIDAD.INTERNO) {
        // Excluye explícitamente a Tienda y Supervisor
        return ['contabilidad', 'gerencia', 'tesoreria', 'direccion', 'admin'].includes(rol);
    }

    return false;
};
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
    apiErrorMessage,
    assignAuthorizationAreaToUser,
    assignUserToStore,
    createUser,
    currentToken,
    deleteUser,
    listAuthorizationAreas,
    listAuthorizationAreasForUser,
    listAllStores,
    listAllUsers,
    listStoreUserAssignments,
    updateUser,
} from '../../lib/api';

const ROLE_OPTIONS = [
    { value: 'store', label: 'Tienda' },
    { value: 'authorizer', label: 'Supervisor' },
    { value: 'accountant', label: 'Contabilidad' },
    { value: 'accounting_manager', label: 'Gerencia' },
    { value: 'treasury', label: 'Tesoreria' },
    { value: 'director', label: 'Direccion' },
    { value: 'admin', label: 'Admin' },
];

const STORE_SCOPED_ROLES = new Set(['store']);

const DEFAULT_AUTHORIZATION_AREAS = [
    'Auditoria Interna',
    'Gestoria',
    'Insumos',
    'Mantenimiento',
    'Operaciones',
    'Pago de Luz',
    'Recursos Humanos',
    'Servicio de Agua',
    'Sistemas',
    'Supervisores',
    'Trafico',
];

const EMPTY_FORM = {
    fullName: '',
    email: '',
    password: '',
    role: 'store',
    isActive: true,
    storeId: '',
    supervisorId: '',
    authorizationArea: '',
};

async function cargarAsignacionesPorUsuario(usuarios, tiendas) {
    const usuariosPorId = Object.fromEntries(usuarios.map((usuario) => [usuario.id, usuario]));
    const asignaciones = Object.fromEntries(
        usuarios.map((usuario) => [usuario.id, { areas: [], storeIds: [], storeId: '', tiendas: [] }])
    );

    const areasPorUsuario = await Promise.all(
        usuarios
            .filter((usuario) => usuario.role === 'authorizer')
            .map(async (usuario) => {
                try {
                    const data = await listAuthorizationAreasForUser(usuario.id);
                    return [usuario.id, Array.isArray(data) ? data : []];
                } catch {
                    return [usuario.id, []];
                }
            })
    );

    areasPorUsuario.forEach(([usuarioId, areas]) => {
        if (!asignaciones[usuarioId]) return;
        asignaciones[usuarioId].areas = areas
            .filter((area) => area.is_active !== false)
            .map((area) => area.authorization_area?.name)
            .filter(Boolean);
    });

    const asignacionesTiendas = await Promise.all(
        tiendas.map(async (tienda) => {
            try {
                const data = await listStoreUserAssignments(tienda.id);
                return [tienda, Array.isArray(data) ? data : []];
            } catch {
                return [tienda, []];
            }
        })
    );

    asignacionesTiendas.forEach(([tienda, usuariosTienda]) => {
        usuariosTienda
            .filter((asignacion) => asignacion.is_active !== false)
            .forEach((asignacion) => {
                const usuario = usuariosPorId[asignacion.user_id];
                if (!usuario || !asignaciones[asignacion.user_id]) return;
                if (asignacion.role && asignacion.role !== usuario.role) return;
                asignaciones[asignacion.user_id].storeIds.push(tienda.id);
                asignaciones[asignacion.user_id].storeId ||= tienda.id;
                asignaciones[asignacion.user_id].tiendas.push(`${tienda.code} - ${tienda.name}`);
            });
    });

    return asignaciones;
}

function mostrarListaAsignada(valores, textoVacio = 'Sin asignar') {
    if (!Array.isArray(valores) || valores.length === 0) return textoVacio;
    return valores.join(', ');
}

function Usuarios() {
    const navigate = useNavigate();
    const [usuarios, setUsuarios] = useState([]);
    const [tiendas, setTiendas] = useState([]);
    const [areas, setAreas] = useState(DEFAULT_AUTHORIZATION_AREAS);
    const [asignacionesPorUsuario, setAsignacionesPorUsuario] = useState({});

    // Estados para Formulario y Edición
    const [form, setForm] = useState(EMPTY_FORM);
    const [usuarioEditarId, setUsuarioEditarId] = useState(null);
    const [mostrarUsuario, setMostrarUsuario] = useState(false);
    
    // Estados para Eliminación
    const [usuarioAEliminar, setUsuarioAEliminar] = useState(null);
    const [justificacion, setJustificacion] = useState('');
    const [mostrarEliminar, setMostrarEliminar] = useState(false);

    const [cargando, setCargando] = useState(true);
    const [guardando, setGuardando] = useState(false);
    const [error, setError] = useState('');
    const [mensaje, setMensaje] = useState('');

    const requiereTienda = STORE_SCOPED_ROLES.has(form.role);
    const requiereArea = form.role === 'authorizer';

    const rolesPorValor = useMemo(
        () => Object.fromEntries(ROLE_OPTIONS.map((role) => [role.value, role.label])),
        []
    );

    const supervisoresActivos = useMemo(
        () => usuarios.filter((usuario) => usuario.role === 'authorizer' && usuario.is_active),
        [usuarios]
    );

    const supervisoresPorTienda = useMemo(() => {
        const resultado = {};
        supervisoresActivos.forEach((supervisor) => {
            const asignaciones = asignacionesPorUsuario[supervisor.id] || {};
            (asignaciones.storeIds || []).forEach((storeId) => {
                resultado[storeId] ||= [];
                resultado[storeId].push(supervisor);
            });
        });
        return resultado;
    }, [asignacionesPorUsuario, supervisoresActivos]);

    const supervisorInicialParaTienda = (storeId) => {
        if (!storeId) return '';
        return supervisoresPorTienda[storeId]?.[0]?.id || '';
    };

    const reloadData = async () => {
        const [usuariosData, tiendasData] = await Promise.all([listAllUsers(), listAllStores()]);
        const areasData = await listAuthorizationAreas().catch(() => []);

        const usuariosLista = Array.isArray(usuariosData) ? usuariosData : [];
        const tiendasLista = Array.isArray(tiendasData) ? tiendasData : [];
        const asignaciones = await cargarAsignacionesPorUsuario(usuariosLista, tiendasLista);

        setUsuarios(usuariosLista);
        setTiendas(tiendasLista);
        setAsignacionesPorUsuario(asignaciones);

        const nombresAreas = Array.isArray(areasData)
            ? areasData.filter((area) => area.is_active !== false).map((area) => area.name)
            : [];
        setAreas(nombresAreas.length ? nombresAreas : DEFAULT_AUTHORIZATION_AREAS);
    };



    useEffect(() => {
        let activo = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                activo = false;
            };
        }

        async function cargarDatos() {
            setCargando(true);
            setError('');

            try {
                const [usuariosData, tiendasData] = await Promise.all([
                    listAllUsers(),
                    listAllStores(),
                ]);
                let areasData = [];

                try {
                    areasData = await listAuthorizationAreas();
                } catch {
                    areasData = [];
                }

                if (!activo) return;

                const usuariosLista = Array.isArray(usuariosData) ? usuariosData : [];
                const tiendasLista = Array.isArray(tiendasData) ? tiendasData : [];
                const asignaciones = await cargarAsignacionesPorUsuario(usuariosLista, tiendasLista);

                if (!activo) return;
                setUsuarios(usuariosLista);
                setTiendas(tiendasLista);
                setAsignacionesPorUsuario(asignaciones);
                const nombresAreas = Array.isArray(areasData)
                    ? areasData
                        .filter((area) => area.is_active !== false)
                        .map((area) => area.name)
                    : [];
                setAreas(nombresAreas.length ? nombresAreas : DEFAULT_AUTHORIZATION_AREAS);
            } catch (err) {
                if (!activo) return;
                setError(apiErrorMessage(err));
            } finally {
                if (activo) setCargando(false);
            }
        }

        cargarDatos();

        return () => {
            activo = false;
        };
    }, [navigate]);

    const actualizarCampo = (campo, valor) => {
        setForm((actual) => {
            const siguiente = {
                ...actual,
                [campo]: valor,
                ...(campo === 'role' && valor !== 'authorizer' ? { authorizationArea: '' } : {}),
                ...(campo === 'role' && !STORE_SCOPED_ROLES.has(valor)
                    ? { storeId: '', supervisorId: '' }
                    : {}),
                ...(campo === 'role' && valor !== 'store' ? { supervisorId: '' } : {}),
            };

            if (campo === 'storeId' && siguiente.role === 'store') {
                siguiente.supervisorId = supervisorInicialParaTienda(valor);
            }

            if (campo === 'role' && valor === 'store' && siguiente.storeId) {
                siguiente.supervisorId = supervisorInicialParaTienda(siguiente.storeId);
            }

            return siguiente;
        });
    };

    const abrirVentanaUsuario = () => {
        setUsuarioEditarId(null);
        setForm(EMPTY_FORM);
        setError('');
        setMensaje('');
        setMostrarUsuario(true);
    };



    const abrirVentanaEditarUsuario = (usuario) => {
        const asignaciones = asignacionesPorUsuario[usuario.id] || {};
        const storeId = asignaciones.storeId || '';
        setUsuarioEditarId(usuario.id);
        setForm({
            fullName: usuario.full_name || '',
            email: usuario.email || '',
            password: '', // Se deja vacío a menos que se quiera actualizar
            role: usuario.role || 'store',
            isActive: usuario.is_active !== false,
            storeId,
            supervisorId: usuario.role === 'store' ? supervisorInicialParaTienda(storeId) : '',
            authorizationArea: asignaciones.areas?.[0] || '',
        });
        setError('');
        setMensaje('');
        setMostrarUsuario(true);
    };



    const cerrarVentanaUsuario = () => {
        if (guardando) return;
        setMostrarUsuario(false);
    };

    const handleGuardarUsuario = async (event) => {
        event.preventDefault();
        setError('');
        setMensaje('');

        if (form.isActive && requiereArea && !form.authorizationArea) {
            setError('Selecciona el area que autoriza este supervisor.');
            return;
        }

        setGuardando(true);

        try {
            if (usuarioEditarId) {
                // Modo EDICIÓN
                await updateUser(usuarioEditarId, {
                    email: form.email.trim(),
                    full_name: form.fullName.trim(),
                    role: form.role,
                    is_active: form.isActive,
                    ...(form.password ? { password: form.password } : {}),
                });

                if (form.isActive && requiereTienda && form.storeId) {
                    await assignUserToStore(form.storeId, usuarioEditarId, form.role);
                }

                if (form.isActive && requiereArea) {
                    await assignAuthorizationAreaToUser(usuarioEditarId, form.authorizationArea);
                }

                if (form.storeId && form.supervisorId) {
                    await assignUserToStore(form.storeId, form.supervisorId, 'authorizer');
                }

                setMensaje('Usuario actualizado correctamente.');
            } else {
                // Modo CREACIÓN
                const usuario = await createUser({
                    email: form.email.trim(),
                    full_name: form.fullName.trim(),
                    role: form.role,
                    is_active: form.isActive,
                    password: form.password || undefined,
                });

                if (form.isActive && requiereTienda && form.storeId) {
                    await assignUserToStore(form.storeId, usuario.id, form.role);
                }

                if (form.isActive && requiereArea) {
                    await assignAuthorizationAreaToUser(usuario.id, form.authorizationArea);
                }

                if (form.storeId && form.supervisorId) {
                    await assignUserToStore(form.storeId, form.supervisorId, 'authorizer');
                }

                setMensaje('Usuario guardado correctamente.');
            }

            const [usuariosActualizados, tiendasActualizadas] = await Promise.all([
                listAllUsers(),
                listAllStores(),
            ]);
            const usuariosLista = Array.isArray(usuariosActualizados) ? usuariosActualizados : [];
            const tiendasLista = Array.isArray(tiendasActualizadas) ? tiendasActualizadas : [];
            const asignaciones = await cargarAsignacionesPorUsuario(usuariosLista, tiendasLista);

            setUsuarios(usuariosLista);
            setTiendas(tiendasLista);
            setAsignacionesPorUsuario(asignaciones);
            setMensaje('Usuario guardado correctamente.');
            setMostrarUsuario(false);
            setForm(EMPTY_FORM);
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setGuardando(false);
        }
    };

    // Funciones del Modal de Eliminación
    const abrirVentanaEliminar = (usuario) => {
        setUsuarioAEliminar(usuario);
        setJustificacion('');
        setError('');
        setMostrarEliminar(true);
    };

    const cerrarVentanaEliminar = () => {
        if (guardando) return;
        setMostrarEliminar(false);
        setUsuarioAEliminar(null);
        setJustificacion('');
    };

    const handleConfirmarEliminar = async (event) => {
        event.preventDefault();
        if (!justificacion.trim()) {
            setError('Debes ingresar una justificación para eliminar el usuario.');
            return;
        }

        setGuardando(true);
        setError('');

        try {
            await deleteUser(usuarioAEliminar.id, { reason: justificacion.trim() });
            setMensaje(`Usuario "${usuarioAEliminar.full_name}" eliminado correctamente.`);
            await reloadData();
            cerrarVentanaEliminar();
        } catch (err) {
            setError(apiErrorMessage(err));
        } finally {
            setGuardando(false);
        }
    };




    return (
        <div style={styles.container}>
            <div style={styles.headerRow}>
                <div>
                    <h1 style={styles.title}>Administración de Usuarios</h1>
                </div>
                <button type="button" style={styles.primaryButton} onClick={abrirVentanaUsuario}>
                    Crear Usuario
                </button>
            </div>

            {error && <div style={styles.error}>{error}</div>}
            {mensaje && <div style={styles.success}>{mensaje}</div>}

            <div style={styles.table}>
                <div style={styles.tableHeader}>
                    <span>Nombre</span>
                    <span>Correo</span>
                    <span>Rol</span>
                    <span>Área</span>
                    <span>Tienda</span>
                    <span>Estado</span>
                    <span>Herramientas</span>
                </div>

                {cargando ? (
                    <div style={styles.emptyState}>Cargando usuarios...</div>
                ) : usuarios.length === 0 ? (
                    <div style={styles.emptyState}>No hay usuarios registrados.</div>
                ) : (
                    usuarios.map((usuario) => {
                        const asignaciones = asignacionesPorUsuario[usuario.id] || {};
                        const areaAsignada = usuario.role === 'authorizer'
                            ? mostrarListaAsignada(asignaciones.areas, 'Sin área')
                            : 'No aplica';
                        const tiendaAsignada = usuario.role === 'store'
                            ? mostrarListaAsignada(asignaciones.tiendas, 'Sin tienda')
                            : 'No aplica';

                        return (
                            <div key={usuario.id} style={styles.row}>
                                <span>{usuario.full_name}</span>
                                <span>{usuario.email}</span>
                                <span>{rolesPorValor[usuario.role] || usuario.role}</span>
                                <span>{areaAsignada}</span>
                                <span>{tiendaAsignada}</span>
                                <span>{usuario.is_active ? 'Activo' : 'Inactivo'}</span>
                                <div style={styles.toolsCell}>
                                    <button
                                        type="button"
                                        style={styles.iconBtn}
                                        onClick={() => abrirVentanaEditarUsuario(usuario)}
                                        title="Editar Usuario"
                                    >
                                        <img src="/Editar.png" alt="Editar" style={styles.iconImg} />
                                    </button>
                                    <button
                                        type="button"
                                        style={{ ...styles.iconBtn }}
                                        onClick={() => abrirVentanaEliminar(usuario)}
                                        title="Eliminar Usuario"
                                    >
                                        <img src="/Eliminar.png" alt="Eliminar" style={styles.iconImg} />
                                    </button>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            {/* Modal Crear / Editar Usuario */}
            {mostrarUsuario && (
                <div style={styles.modalBackdrop}>
                    <form style={styles.modal} onSubmit={handleGuardarUsuario}>
                        <div style={styles.modalHeader}>
                            <h2 style={styles.modalTitle}>
                                {usuarioEditarId ? 'Editar Usuario' : 'Nuevo Usuario'}
                            </h2>
                        </div>

                        <label style={styles.inputGroup}>
                            Nombre
                            <input
                                type="text"
                                value={form.fullName}
                                onChange={(event) => actualizarCampo('fullName', event.target.value)}
                                style={styles.input}
                                placeholder='Nombre Completo'
                                required
                            />
                        </label>

                        <label style={styles.inputGroup}>
                            Correo
                            <input
                                type="email"
                                value={form.email}
                                onChange={(event) => actualizarCampo('email', event.target.value)}
                                style={styles.input}
                                placeholder='nombre@vertiche.com.mx'
                                required
                            />
                        </label>

                        <label style={styles.inputGroup}>
                            Contraseña
                            <input
                                type="password"
                                value={form.password}
                                onChange={(event) => actualizarCampo('password', event.target.value)}
                                style={styles.input}
                                minLength={usuarioEditarId ? undefined : 8}
                                required={!usuarioEditarId}
                                placeholder={usuarioEditarId ? 'Insertar Contraseña' : 'Inserte Contraseña'}
                            />
                        </label>

                        <label style={styles.inputGroup}>
                            Rol
                            <select
                                value={form.role}
                                onChange={(event) => actualizarCampo('role', event.target.value)}
                                style={styles.input}
                            >
                                {ROLE_OPTIONS.map((role) => (
                                    <option key={role.value} value={role.value}>
                                        {role.label}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label style={styles.switchGroup}>
                            <span>Estado</span>
                            <button
                                type="button"
                                role="switch"
                                aria-checked={form.isActive}
                                style={{
                                    ...styles.switchButton,
                                    ...(form.isActive ? styles.switchButtonOn : {}),
                                }}
                                onClick={() => actualizarCampo('isActive', !form.isActive)}
                            >
                                <span
                                    style={{
                                        ...styles.switchKnob,
                                        ...(form.isActive ? styles.switchKnobOn : {}),
                                    }}
                                />
                            </button>
                            <strong style={styles.switchText}>
                                {form.isActive ? 'Activo' : 'Inactivo'}
                            </strong>
                        </label>

                        {requiereTienda && (
                            <label style={styles.inputGroup}>
                                Tienda
                                <select
                                    value={form.storeId}
                                    onChange={(event) => actualizarCampo('storeId', event.target.value)}
                                    style={styles.input}
                                >
                                    <option value="">Sin tienda asignada</option>
                                    {tiendas.map((tienda) => (
                                        <option key={tienda.id} value={tienda.id}>
                                            {tienda.code} - {tienda.name}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        )}

                        {form.role === 'store' && (
                            <label style={styles.inputGroup}>
                                Supervisor
                                <select
                                    value={form.supervisorId}
                                    onChange={(event) => actualizarCampo('supervisorId', event.target.value)}
                                    style={styles.input}
                                    disabled={!form.storeId || supervisoresActivos.length === 0}
                                >
                                    <option value="">
                                        {form.storeId ? 'Sin supervisor asignado' : 'Selecciona una tienda primero'}
                                    </option>
                                    {supervisoresActivos.map((supervisor) => (
                                        <option key={supervisor.id} value={supervisor.id}>
                                            {supervisor.full_name} - {supervisor.email}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        )}

                        {requiereArea && (
                            <label style={styles.inputGroup}>
                                Área
                                <select
                                    value={form.authorizationArea}
                                    onChange={(event) => actualizarCampo(
                                        'authorizationArea',
                                        event.target.value
                                    )}
                                    style={styles.input}
                                    required={form.isActive}
                                >
                                    <option value="">Seleccionar área...</option>
                                    {areas.map((area) => (
                                        <option key={area} value={area}>
                                            {area}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        )}

                        <div style={styles.actions}>
                            <button
                                type="button"
                                style={styles.secondaryButton}
                                onClick={cerrarVentanaUsuario}
                                disabled={guardando}
                            >
                                Cancelar
                            </button>
                            <button type="submit" style={styles.saveButton} disabled={guardando}>
                                {guardando ? 'Guardando...' : 'Guardar'}
                            </button>
                        </div>
                    </form>
                </div>
            )}


            {/* Modal Eliminar Usuario */}
            {mostrarEliminar && usuarioAEliminar && (
                <div style={styles.modalBackdrop}>
                    <form style={styles.modal} onSubmit={handleConfirmarEliminar}>
                        <div style={styles.modalHeader}>
                            <h2 style={styles.modalTitle}>Eliminar Usuario</h2>
                        </div>

                        <p style={{ margin: 0, fontSize: '13px', color: '#333' }}>
                            ¿Estás seguro de que deseas eliminar al usuario{' '}
                            <strong>{usuarioAEliminar.full_name}</strong>?
                        </p>

                        <label style={styles.inputGroup}>
                            <textarea
                                value={justificacion}
                                onChange={(e) => setJustificacion(e.target.value)}
                                style={{ ...styles.input, minHeight: '80px', resize: 'vertical' }}
                                placeholder="Escribe el motivo de la baja..."
                                required
                            />
                        </label>

                        <div style={styles.actions}>
                            <button
                                type="button"
                                style={styles.secondaryButton}
                                onClick={cerrarVentanaEliminar}
                                disabled={guardando}
                            >
                                Cancelar
                            </button>
                            <button
                                type="submit"
                                style={{ ...styles.saveButton }}
                                disabled={guardando}
                            >
                                {guardando ? 'Eliminando...' : 'Eliminar'}
                            </button>
                        </div>
                    </form>
                </div>
            )}
        </div>
    );
}

const styles = {
    container: {
        maxWidth: '1450px',
        margin: '0 auto',
        padding: '10px 10px',
        textAlign: 'left',
        fontFamily: 'var(--sans)',
    },
    headerRow: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        marginBottom: '20px',
    },
    title: {
        margin: 0,
        fontSize: '24px',
        //fontWeight: 600,
    },
    subtitle: {
        color: '#666',
        fontSize: '14px',
    },

    primaryButton: {
        background: 'var(--sb-sendBtnBg)',
        color: 'var(--text-CBtn)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '20px',
        padding: '8px 20px',
        fontSize: '13px',
        fontWeight: '600',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
        transition: 'transform 0.1s',
    },
    saveButton: {
        background: 'var(--gradient)',
        color: 'var(--text-CBtn)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '20px',
        padding: '8px 20px',
        fontSize: '14px',
        fontWeight: '700',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
        transition: 'transform 0.1s',
    },
    secondaryButton: {
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text-WBtn)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '20px',
        padding: '8px 15px',
        fontSize: '14px',
        fontWeight: '700',
        cursor: 'pointer',
        transition: 'transform 0.1s',
    },
    table: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        overflow: 'hidden',
        backgroundColor: '#fff',
    },
    tableHeader: {
        display: 'grid',
        gridTemplateColumns: '1.3fr 1.8fr 0.6fr 0.5fr 1fr 0.5fr 0.5fr',
        gap: '12px',
        padding: '12px 16px',
        backgroundColor: '#ffb9b9',
        color: '#ffffff',
        fontSize: '14px',
        fontWeight: '700',
        textTransform: 'uppercase',
    },
    row: {
        display: 'grid',
        gridTemplateColumns: '1.3fr 1.8fr 0.6fr 0.5fr 1fr 0.5fr 0.5fr',
        gap: '12px',
        padding: '13px 16px',
        borderTop: '1px solid var(--border)',
        color: '#333',
        fontSize: '12px',
        alignItems: 'center',
    },


    toolsCell: {
        display: 'flex',
        gap: '20px',
        alignItems: 'center',
    },
    iconBtn: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: 0,
        display: 'flex',
        alignItems: 'center',
        paddingRight: '5px',
    },
    iconImg: {
        width: '16px',
        height: '16px',
        objectFit: 'contain'
    },



    emptyState: {
        padding: '22px 16px',
        color: '#989898',
        fontSize: '13px',
        textAlign: 'center',
    },
    error: {
        marginBottom: '14px',
        padding: '10px 12px',
        border: '1px solid #d31c00',
        borderRadius: '6px',
        backgroundColor: '#ff383821',
        color: '#d31c00',
        fontSize: '14px',
    },
    success: {
        marginBottom: '14px',
        padding: '10px 12px',
        border: '1px solid #339900',
        borderRadius: '6px',
        backgroundColor: 'var(--sb-pagadaBg)',
        color: 'var(--text-pagada)',
        fontSize: '14px',
    },
    modalBackdrop: {
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.35)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        zIndex: 1000,
    },
    modal: {
        width: 'min(520px, 100%)',
        backgroundColor: '#fff',
        borderRadius: '8px',
        border: '1px solid var(--border)',
        boxShadow: 'var(--shadow)',
        padding: '22px',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
    },
    modalHeader: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '4px',
    },
    modalTitle: {
        margin: 0,
        fontSize: '22px',
        fontWeight: 700,
    },
    closeButton: {
        border: '1px solid #ffffff',
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text)',
        borderRadius: '20px',
        width: '28px',
        height: '28px',
        cursor: 'pointer',
        fontWeight: '700',
        fontSize: '16px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        color: '#000000',
        fontSize: '14px',
        fontWeight: '600',
    },
    input: {
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '10px 12px',
        color: '#323232',
        backgroundColor: '#fff',
        fontSize: '13px',
    },
    switchGroup: {
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        color: '#000000',
        fontSize: '14px',
        fontWeight: '600',
    },
    switchButton: {
        width: '42px',
        height: '24px',
        border: '1px solid var(--border)',
        borderRadius: '999px',
        backgroundColor: '#d7d7d7',
        padding: '2px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        transition: 'background-color 0.15s ease',
    },
    switchButtonOn: {
        backgroundColor: '#64b96a',
    },
    switchKnob: {
        width: '18px',
        height: '18px',
        borderRadius: '999px',
        backgroundColor: '#ffffff',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.25)',
        transform: 'translateX(0)',
        transition: 'transform 0.15s ease',
    },
    switchKnobOn: {
        transform: 'translateX(18px)',
    },
    switchText: {
        fontSize: '13px',
        color: '#323232',
    },
    actions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '10px',
        marginTop: '8px',
    },
};

export default Usuarios;

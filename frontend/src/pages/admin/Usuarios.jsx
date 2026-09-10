import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
    apiErrorMessage,
    assignAuthorizationAreaToUser,
    assignUserToStore,
    createUser,
    currentToken,
    listAuthorizationAreas,
    listAuthorizationAreasForUser,
    listStores,
    listStoreUserAssignments,
    listUsers,
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

const STORE_SCOPED_ROLES = new Set(['store', 'authorizer', 'accountant', 'accounting_manager']);

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
    password: 'secret-password',
    role: 'store',
    storeId: '',
    authorizationArea: '',
};

async function cargarAsignacionesPorUsuario(usuarios, tiendas) {
    const asignaciones = Object.fromEntries(
        usuarios.map((usuario) => [usuario.id, { areas: [], tiendas: [] }])
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
                if (!asignaciones[asignacion.user_id]) return;
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
    const [form, setForm] = useState(EMPTY_FORM);
    const [mostrarUsuario, setMostrarUsuario] = useState(false);
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
                    listUsers(),
                    listStores(),
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
        setForm((actual) => ({
            ...actual,
            [campo]: valor,
            ...(campo === 'role' && valor !== 'authorizer' ? { authorizationArea: '' } : {}),
            ...(campo === 'role' && !STORE_SCOPED_ROLES.has(valor) ? { storeId: '' } : {}),
        }));
    };

    const abrirVentanaUsuario = () => {
        setForm(EMPTY_FORM);
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

        if (requiereArea && !form.authorizationArea) {
            setError('Selecciona el area que autoriza este supervisor.');
            return;
        }

        setGuardando(true);

        try {
            const usuario = await createUser({
                email: form.email.trim(),
                full_name: form.fullName.trim(),
                role: form.role,
                password: form.password || undefined,
            });

            if (requiereTienda && form.storeId) {
                await assignUserToStore(form.storeId, usuario.id, form.role);
            }

            if (requiereArea) {
                await assignAuthorizationAreaToUser(usuario.id, form.authorizationArea);
            }

            const [usuariosActualizados, tiendasActualizadas] = await Promise.all([
                listUsers(),
                listStores(),
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

    return (
        <div style={styles.container}>
            <div style={styles.headerRow}>
                <div>
                    <h1 style={styles.title}>Usuarios</h1>
                    <p style={styles.subtitle}>Administra cuentas internas y areas de autorizacion.</p>
                </div>
                <button type="button" style={styles.primaryButton} onClick={abrirVentanaUsuario}>
                    Nuevo usuario
                </button>
            </div>

            {error && <div style={styles.error}>{error}</div>}
            {mensaje && <div style={styles.success}>{mensaje}</div>}

            <div style={styles.table}>
                <div style={styles.tableHeader}>
                    <span>Nombre</span>
                    <span>Correo</span>
                    <span>Perfil</span>
                    <span>Area</span>
                    <span>Tienda</span>
                    <span>Estado</span>
                </div>

                {cargando ? (
                    <div style={styles.emptyState}>Cargando usuarios...</div>
                ) : usuarios.length === 0 ? (
                    <div style={styles.emptyState}>No hay usuarios registrados.</div>
                ) : (
                    usuarios.map((usuario) => {
                        const asignaciones = asignacionesPorUsuario[usuario.id] || {};
                        const areaAsignada = usuario.role === 'authorizer'
                            ? mostrarListaAsignada(asignaciones.areas, 'Sin area')
                            : 'No aplica';

                        return (
                            <div key={usuario.id} style={styles.row}>
                                <span>{usuario.full_name}</span>
                                <span>{usuario.email}</span>
                                <span>{rolesPorValor[usuario.role] || usuario.role}</span>
                                <span>{areaAsignada}</span>
                                <span>{mostrarListaAsignada(asignaciones.tiendas, 'Sin tienda')}</span>
                                <span>{usuario.is_active ? 'Activo' : 'Inactivo'}</span>
                            </div>
                        );
                    })
                )}
            </div>

            {mostrarUsuario && (
                <div style={styles.modalBackdrop}>
                    <form style={styles.modal} onSubmit={handleGuardarUsuario}>
                        <div style={styles.modalHeader}>
                            <h2 style={styles.modalTitle}>Usuario</h2>
                            <button
                                type="button"
                                style={styles.closeButton}
                                onClick={cerrarVentanaUsuario}
                            >
                                x
                            </button>
                        </div>

                        <label style={styles.inputGroup}>
                            Nombre
                            <input
                                type="text"
                                value={form.fullName}
                                onChange={(event) => actualizarCampo('fullName', event.target.value)}
                                style={styles.input}
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
                                required
                            />
                        </label>

                        <label style={styles.inputGroup}>
                            Contrasena
                            <input
                                type="text"
                                value={form.password}
                                onChange={(event) => actualizarCampo('password', event.target.value)}
                                style={styles.input}
                                minLength={8}
                            />
                        </label>

                        <label style={styles.inputGroup}>
                            Perfil
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

                        {requiereTienda && (
                            <label style={styles.inputGroup}>
                                Tienda asignada
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

                        {requiereArea && (
                            <label style={styles.inputGroup}>
                                Area que autoriza
                                <select
                                    value={form.authorizationArea}
                                    onChange={(event) => actualizarCampo(
                                        'authorizationArea',
                                        event.target.value
                                    )}
                                    style={styles.input}
                                    required
                                >
                                    <option value="">Seleccionar area...</option>
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
                            <button type="submit" style={styles.primaryButton} disabled={guardando}>
                                {guardando ? 'Guardando...' : 'Guardar'}
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
        maxWidth: '1300px',
        margin: '0 auto',
        padding: '30px 20px',
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
        margin: '0 0 4px',
        fontSize: '30px',
        fontWeight: 600,
    },
    subtitle: {
        color: '#666',
        fontSize: '14px',
    },
    primaryButton: {
        backgroundColor: 'var(--sb-sendBtnBg)',
        border: '1px solid var(--sb-btnBorder)',
        color: 'var(--text-CBtn)',
        padding: '10px 22px',
        borderRadius: '6px',
        cursor: 'pointer',
        fontWeight: '700',
        fontSize: '14px',
    },
    secondaryButton: {
        backgroundColor: 'var(--sb-WBtnBg)',
        border: '1px solid var(--sb-btnBorder)',
        color: 'var(--text-WBtn)',
        padding: '10px 22px',
        borderRadius: '6px',
        cursor: 'pointer',
        fontWeight: '700',
        fontSize: '14px',
    },
    table: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        overflow: 'hidden',
        backgroundColor: '#fff',
    },
    tableHeader: {
        display: 'grid',
        gridTemplateColumns: '1.2fr 1.6fr 0.9fr 1fr 1.3fr 0.7fr',
        gap: '12px',
        padding: '12px 16px',
        backgroundColor: 'var(--sb-subhead)',
        color: '#555',
        fontSize: '12px',
        fontWeight: '700',
        textTransform: 'uppercase',
    },
    row: {
        display: 'grid',
        gridTemplateColumns: '1.2fr 1.6fr 0.9fr 1fr 1.3fr 0.7fr',
        gap: '12px',
        padding: '14px 16px',
        borderTop: '1px solid #f1dede',
        color: '#333',
        fontSize: '14px',
        alignItems: 'center',
    },
    emptyState: {
        padding: '22px 16px',
        color: '#777',
        fontSize: '14px',
        textAlign: 'center',
    },
    error: {
        marginBottom: '14px',
        padding: '10px 12px',
        border: '1px solid #eb6a00',
        borderRadius: '6px',
        backgroundColor: 'var(--sb-denegadaBg)',
        color: 'var(--text-denegada)',
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
        border: '1px solid var(--sb-btnBorder)',
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text-WBtn)',
        borderRadius: '6px',
        width: '32px',
        height: '32px',
        cursor: 'pointer',
        fontWeight: '700',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        color: '#444',
        fontSize: '13px',
        fontWeight: '600',
    },
    input: {
        border: '1px solid #e5c7c7',
        borderRadius: '6px',
        padding: '10px 12px',
        color: '#333',
        backgroundColor: '#fff',
        fontSize: '14px',
    },
    actions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '10px',
        marginTop: '8px',
    },
};

export default Usuarios;

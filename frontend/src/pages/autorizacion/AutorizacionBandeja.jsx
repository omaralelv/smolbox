import { useEffect, useState } from 'react';

import Drawer from '../../components/shared/Drawer';
import { VISIBILIDAD, PUEDE_LEER_OBSERVACION } from '../../components/shared/roles';

import {
    addExpenseObservation,
    apiErrorMessage,
    getRequestAuditEvents,
} from '../../lib/api';


// Datos de prueba maquetados (Mock Data)
const GASTOS_MOCK = [
    { id: 1, nombre: 'Gasto 1', tienda: 'T001', tipo: 'Sistemas', estado: 'Pendiente' },
    { id: 2, nombre: 'Gasto 2', tienda: 'T006', tipo: 'Sistemas', estado: 'Pendiente' },
    { id: 3, nombre: 'Gasto 3', tienda: 'T212', tipo: 'Papelería', estado: 'Autorizada' },
    { id: 4, nombre: 'Gasto 4', tienda: 'T124', tipo: 'Alimentos', estado: 'No Autorizada' },
];


const HISTORIAL_MOCK = [
    {
        id: 1,
        gastoId: 1,
        autor: 'Tienda Toluca',
        rol: 'tienda',
        texto: 'Compra de insumos de papelería urgentes.',
        fecha: '10/08/2026 - 09:00 AM',
        visibilidad: VISIBILIDAD.PUBLIC
    },
    {
        id: 2,
        gastoId: 2,
        autor: 'Contabilidad',
        rol: 'contabilidad',
        texto: 'Nota interna: Se detectó duplicidad de folio fiscal, procedemos a descartar.',
        fecha: '11/08/2026 - 10:15 AM',
        visibilidad: VISIBILIDAD.INTERNO
    }
];

// Función helper para convertir la observación inicial de un gasto en formato de evento
    function observacionInicialDesdeGasto(gasto) {
        // Busca el texto en las propiedades típicas donde la tienda guarda la nota al crear el gasto
        const textoInicial = gasto.observaciones || gasto.observacion;
    
        if (!textoInicial || !textoInicial.trim()) return null;
    
        const gastoId = gastoHistorialId(gasto);
        const fechaRaw = gasto.created_at || gasto.createdAt || gasto.fecha || new Date();
        let timestamp = Date.parse(fechaRaw);
        if (Number.isNaN(timestamp) || !timestamp) {
            timestamp = Date.now();
        }
    
    
        return {
            id: `init-obs-${gastoId}`,
            gastoId: gastoId,
            autor: 'TIENDA',
            rol: 'tienda',
            texto: textoInicial.trim(),
            fecha: fechaLegible(fechaRaw),
            fechaTimestamp: timestamp,
            visibilidad: VISIBILIDAD.PUBLIC, // Visibilidad pública para que todos la vean
        };
    }


function AutorizacionBandeja( { currentRole } ) {
    //const navigate = useNavigate();
    
    const [gastos, setGastos] = useState(GASTOS_MOCK);
    const solicitudBackendId = location.state?.solicitudBackendId || null;


    // 1. ESTADOS PARA CONTROLAR LOS PANELES Y OBSERVACIONES
    const [documentoActivo, setDocumentoActivo] = useState(null); // 'factura' | 'vale' | null
    const [observacionesAbiertas, setObservacionesAbiertas] = useState(false);
    const [gastoSeleccionado, setGastoSeleccionado] = useState(null);

    // Estado del chat de observaciones
    const [comentario, setComentario] = useState('');
    const [historial, setHistorial] = useState(() => (solicitudBackendId ? [] : HISTORIAL_MOCK));

    // 2. NORMALIZAR EL ROL
    const rol = String(currentRole || localStorage.getItem('currentRole') || 'admin').toLowerCase().trim();

    // Mock por si ingresas directo sin state
    const [gastosDesglosados, setGastosDesglosados] = useState(() => (
        location.state?.desglose?.length > 0
            ? location.state.desglose
            : [
            { 
                id: 1, 
                nombre: 'Gasto 1', 
                monto: 150.00, 
                folioFiscal: '5FB2822E-396D-4725-8521-CDC4BDD20CCF', 
                autorizacion: 'autorizado' // 'autorizado', 'no_autorizado', o ''
            },
            { 
                id: 2, 
                nombre: 'Gasto 2', 
                monto: 118.01, 
                folioFiscal: '467FE2EF-99E8-45CD-8E2F-F7C63D13847B', 
                autorizacion: '' 
            },
            { 
                id: 3, 
                nombre: 'Gasto 3', 
                monto: 118.01, 
                folioFiscal: 'EF953B9E-8835-2EE7-L8R7-C94OQ8358JKI', 
                estatus: 'no_autorizado', // 👈 Gasto deshabilitado de prueba
                autorizacion: 'no_autorizado'
            }
        ]
    ));


    const abrirArchivo = (_gasto, tipo) => {
        alert(`Este gasto de prueba no tiene ${tipo} cargado.`);
    };

    // Función pura de UI para cambiar el estatus al dar clic en los botones
    const handleCambiarEstado = (id, nuevoEstado) => {
        setGastos(prevGastos =>
            prevGastos.map(gasto =>
                gasto.id === id ? { ...gasto, estado: nuevoEstado } : gasto
            )
        );
    };

    // Helper para pintar el pill/tag de estado según su valor
    const renderEstadoBadge = (estado) => {
        switch (estado) {
            case 'Autorizada':
                return <span style={{ ...styles.badge, ...styles.badgeAutorizada }}>Autorizada</span>;
            case 'No Autorizada':
                return <span style={{ ...styles.badge, ...styles.badgeNoAutorizada }}>No Autorizada</span>;
            case 'Pendiente':
            default:
                return <span style={{ ...styles.badge, ...styles.badgePendiente }}>Pendiente</span>;
        }
    };


    useEffect(() => {
            let activo = true;
    
            // 1. Extraemos las notas iniciales ingresadas por la tienda en cada gasto
                    const obsIniciales = (gastosDesglosados || [])
                        .map(observacionInicialDesdeGasto)
                        .filter(Boolean);
    
    
            if (!solicitudBackendId) return undefined;
    
    
            getRequestAuditEvents(solicitudBackendId)
                .then((eventos) => {
    
                    if (activo) {
                        // 1. Mapeamos las observaciones que vienen del backend o eventos
                        const obsEventos = historialDesdeEventos(eventos || []);
    
                        // 3. Unificamos descartando posibles duplicados y ordenamos por fecha
                        const historialCompleto = [...obsIniciales, ...obsEventos].sort(
                            (a, b) => a.fechaTimestamp - b.fechaTimestamp
                        );
    
                        setHistorial(historialCompleto);
                        //setHistorial(historialDesdeEventos(eventos));
                    }
                })
                .catch((error) => {
                    console.error('No se pudieron cargar las observaciones', error);
                });
    
            return () => {
                activo = false;
            };
        }, [solicitudBackendId, gastosDesglosados]);


    // HANDLERS PARA ABRIR Y CERRAR PANELES
        const handleVerVale = (gasto) => {
            setGastoSeleccionado(gasto);
            setDocumentoActivo('vale'); // Si había factura, se cambia a vale automáticamente
        };
    
        const handleVerFactura = (gasto) => {
            setGastoSeleccionado(gasto);
            setDocumentoActivo('factura'); // Si había vale, se cambia a factura automáticamente
        };
    
        const handleToggleObservaciones = (gasto) => {
            setGastoSeleccionado(gasto);
            setObservacionesAbiertas(!observacionesAbiertas);
        };
    
        const handleEnviarObservacion = async (e) => {
            e.preventDefault();
            const textoObservacion = comentario.trim();
            if (!textoObservacion || !gastoSeleccionado) return;
    
            // REGLA 2: Asignación automática de visibilidad según el rol
            let visibilidadAsignada = VISIBILIDAD.INTERNO;
            if (['tienda', 'supervisor'].includes(rol)) {
                visibilidadAsignada = VISIBILIDAD.PUBLIC;
            }
    
            const expenseId = gastoSeleccionado.backendId || gastoSeleccionado.id;
            if (solicitudBackendId && (!expenseId || typeof expenseId !== 'string')) {
                alert('Este gasto no tiene ID de backend para guardar la observación.');
                return;
            }
    
            const nueva = {
                id: `local-${gastoHistorialId(gastoSeleccionado) || 'gasto'}-${historial.length + 1}`,
                gastoId: gastoHistorialId(gastoSeleccionado),
                autor: rol.toUpperCase(),
                rol,
                texto: textoObservacion,
                fecha: new Date().toLocaleString(),
                visibilidad: visibilidadAsignada
            };
    
            try {
                if (solicitudBackendId) {
                    await addExpenseObservation(expenseId, textoObservacion);
                    await refrescarHistorialBackend();
                } else {
                    setHistorial([...historial, nueva]);
                }
                setComentario('');
            } catch (error) {
                alert(apiErrorMessage(error));
            }
        };


    // Evaluamos si ambos están abiertos para ocultar FOLIO FISCAL
    const ocultarTienda = documentoActivo && observacionesAbiertas;


    return (
        
        <div style={styles.mainLayout}>
            <div style={styles.container}>
                {/* ENCABEZADOS DE LA TABLA */}
                <div style={styles.tableHeader}>
                    <span style={{ flex: 1.5 }}></span>

                    {/* OCULTAR ENCABEZADO DE TIENDA SI AMBOS PANELES ESTÁN ABIERTOS */}
                    {!ocultarTienda && (
                        <span style={{ flex: 1, textAlign: 'center', fontWeight: 'bold' }}>TIENDA</span>
                    )}

                    <span style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>TIPO DE GASTO</span>
                    <span style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>¿AUTORIZADO?</span>
                    <span style={{ flex: 2.5, textAlign: 'center', fontWeight: 'bold' }}>HERRAMIENTAS</span>
                </div>

                {/* LISTA DE FILAS DE GASTOS */}
                <div style={styles.listContainer}>
                    {gastos.map((gasto) => (
                        <div key={gasto.id} style={styles.rowCard}>
                            {/* NOMBRE DEL GASTO */}
                            <div style={{ flex: 1.5, paddingLeft: '20px', fontWeight: '500', color: '#333' }}>
                                {gasto.nombre}
                            </div>

                            {/* TIENDA */}
                            {/* OCULTAR CELDA DE FOLIO SI AMBOS PANELES ESTÁN ABIERTOS */}
                            {!ocultarTienda && (
                                <div style={{ flex: 1, textAlign: 'center', color: '#444' }}>
                                    {gasto.tienda}
                                </div>
                            )}
                            

                            {/* TIPO DE GASTO */}
                            <div style={{ flex: 1.5, textAlign: 'center', color: '#444' }}>
                                {gasto.tipo}
                            </div>

                            {/* ESTATUS VISUAL */}
                            <div style={{ flex: 1.5, display: 'flex', justifyContent: 'center' }}>
                                {renderEstadoBadge(gasto.estado)}
                            </div>

                            {/* ACCIONES / BOTONES DE CAMBIO DE ESTATUS Y HERRAMIENTAS */}
                            <div style={styles.actionsContainer}>
                                {gasto.estado === 'Pendiente' ? (
                                    <>
                                        <button
                                            style={styles.btnAutorizar}
                                            onClick={() => handleCambiarEstado(gasto.id, 'Autorizada')}
                                        >
                                            {ocultarTienda ? '✓' : 'AUTORIZAR'}
                                        </button>
                                        <button
                                            style={styles.btnNoAutorizar}
                                            onClick={() => handleCambiarEstado(gasto.id, 'No Autorizada')}
                                        >
                                            {ocultarTienda ? '✕' : 'NO AUTORIZAR'}
                                        </button>
                                    </>
                                ) : (
                                        /* 👈 AQUÍ EL CAMBIO: si ocultarTienda es true, el espaciador debe ser pequeño */
                                        <div style={{ minWidth: ocultarTienda ? '70px' : '220px' }}></div>
                                    )}

                                {/* ICONO DE DOCUMENTO / COMPROBANTE */}
                                <button style={styles.iconBtn} title="Ver Vale" onClick={() => handleVerVale(gasto)}>
                                    <img src="/Vale.png" alt="Vale" style={styles.iconImg} />
                                </button>

                                <button style={styles.iconBtn} title="Ver Factura" onClick={() => handleVerFactura(gasto)}>
                                    <img src="/Factura.png" alt="Factura" style={styles.iconImg} />
                                </button>

                                <button style={styles.iconBtn} title="Observaciones" onClick={() => handleToggleObservaciones(gasto)}>
                                    <img src="/Observacion.png" alt="Observaciones" style={styles.iconImg} />
                                </button>
                            </div>
                            
                        </div>
                        
                    ))}
                </div>
            </div>

            {/* PANEL DERECHO (DRAWER INTEGRADOR) */}
            <Drawer 
                documentoActivo={documentoActivo}
                observacionesAbiertas={observacionesAbiertas}
                gasto={gastoSeleccionado}
                onCloseDocumento={() => setDocumentoActivo(null)}
                onCloseObservaciones={() => setObservacionesAbiertas(false)}
                comentario={comentario}
                setComentario={setComentario}

                // REGLA 2: Filtramos el historial según los permisos del ROL ACTUAL
                historial={historial.filter(obs => 
                    idsIguales(obs.gastoId, gastoHistorialId(gastoSeleccionado)) &&
                    PUEDE_LEER_OBSERVACION(rol, obs.visibilidad)
                )}
                onEnviarObservacion={handleEnviarObservacion}
                currentRole={rol}
            />

        </div>
    );
}

// ESTILOS EN OBJETO CSS-IN-JS
const styles = {
    mainLayout: {
        display: 'flex',
        width: '100%',
        height: 'calc(100vh - 160px)', 
        overflow: 'hidden',
    },

    container: {
        flex: 1,
        maxWidth: '1130px',
        margin: '0 auto',
        padding: '20px',
        fontFamily: 'sans-serif',
        overflowY: 'auto',
    },

    tableHeader: {
        display: 'flex',
        alignItems: 'center',
        padding: '12px 16px',
        marginBottom: '10px',
        fontSize: '14px',
        color: '#111',
    },
    listContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '5px',
    },
    rowCard: {
        display: 'flex',
        alignItems: 'center',
        backgroundColor: 'var(--bg)',
        border: '1px solid var(--border)', // Borde rosa idéntico a la imagen
        borderRadius: '10px',
        padding: '2px 10px',
        fontSize: '13px',
        boxShadow: '0 2px 4px var(--shadow)',
    },
    // BADGES DE ESTATUS
    badge: {
        padding: '4px 16px',
        borderRadius: '6px',
        fontSize: '13px',
        fontWeight: '500',
        display: 'inline-block',
        textAlign: 'center',
    },
    badgePendiente: {
        backgroundColor: 'var(--sb-revisionBg)',
        color: 'var(--text-revision)',
    },
    badgeAutorizada: {
        backgroundColor: 'var(--sb-pagadaBg)',
        color: 'var(--text-pagada)',
    },
    badgeNoAutorizada: {
        backgroundColor: 'var(--sb-denegadaBg)',
        color: 'var(--text-denegada)',
    },
    // ACCIONES
    actionsContainer: {
        flex: 2.5,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: '10px',
        paddingRight: '15px',
    },
    btnAutorizar: {
        backgroundColor: 'var(--text-pagada)', // Verde
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '6px',
        padding: '6px 14px',
        fontSize: '11px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
    btnNoAutorizar: {
        backgroundColor: 'var(--text-denegada)', // Naranja
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '6px',
        padding: '6px 14px',
        fontSize: '11px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
    herramientasContainer: {
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginLeft: '8px',
    },
    iconBtn: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: '2px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    iconImg: {
        width: '18px',
        height: '18px',
        objectFit: 'contain',
    },
};

export default AutorizacionBandeja;



function gastoHistorialId(gasto) {
    return gasto?.backendId ?? gasto?.backend_id ?? gasto?.id ?? null;
}

function idsIguales(uno, dos) {
    if (uno === null || uno === undefined || dos === null || dos === undefined) return false;
    return String(uno) === String(dos);
}

function historialDesdeEventos(eventos = []) {
    return eventos
        .map(observacionDesdeEvento)
        .filter(Boolean)
        .sort((a, b) => a.fechaTimestamp - b.fechaTimestamp);
}

function observacionDesdeEvento(evento) {
    const action = evento.action;
    const expenseId = evento.expense_id || evento.expenseId;
    const textoBase = evento.message || '';

    if (!expenseId || !textoBase) return null;
    if (![
        'expense_observation_added',
        'expense_removed_from_request',
        'expense_review_updated',
        'expense_authorization_rejected',
    ].includes(action)) {
        return null;
    }

    const rol = rolDesdeEvento(evento);
    const autor = autorDesdeRol(rol);
    const texto = textoDesdeEvento(action, textoBase, autor);
    const fechaTimestamp = Date.parse(evento.created_at || evento.createdAt || '');

    return {
        id: evento.id,
        gastoId: expenseId,
        autor,
        rol,
        texto,
        fecha: fechaLegible(evento.created_at || evento.createdAt),
        fechaTimestamp: Number.isNaN(fechaTimestamp) ? 0 : fechaTimestamp,
        visibilidad: visibilidadDesdeEvento(action, rol),
    };
}

function rolDesdeEvento(evento) {
    const payload = evento.event_payload || evento.payload || {};
    const rolBackend = String(payload.actor_role || '').toLowerCase().trim();
    const roles = {
        store: 'tienda',
        authorizer: 'supervisor',
        accountant: 'contabilidad',
        accounting_manager: 'gerencia',
        treasury: 'tesoreria',
        director: 'direccion',
        admin: 'admin',
    };
    return roles[rolBackend] || rolBackend || 'sistema';
}

function autorDesdeRol(rol) {
    const autores = {
        tienda: 'TIENDA',
        supervisor: 'SUPERVISOR',
        contabilidad: 'CONTABILIDAD',
        gerencia: 'GERENCIA',
        tesoreria: 'TESORERIA',
        direccion: 'DIRECCION',
        admin: 'ADMIN',
        sistema: 'SISTEMA',
    };
    return autores[rol] || String(rol || 'sistema').toUpperCase();
}

function textoDesdeEvento(action, textoBase, autor) {
    if (action === 'expense_removed_from_request') {
        return `Gasto eliminado por ${autor}. Motivo: ${textoBase}`;
    }
    if (action === 'expense_authorization_rejected') {
        return `Gasto no autorizado. Motivo: ${textoBase}`;
    }
    return textoBase;
}

function visibilidadDesdeEvento(action, rol) {
    if (['expense_removed_from_request', 'expense_authorization_rejected'].includes(action)) {
        return VISIBILIDAD.PUBLIC;
    }
    if (['tienda', 'supervisor'].includes(rol)) {
        return VISIBILIDAD.PUBLIC;
    }
    return VISIBILIDAD.INTERNO;
}

function fechaLegible(fecha) {
    if (!fecha) return new Date().toLocaleString();
    const parsed = new Date(fecha);
    if (Number.isNaN(parsed.getTime())) return String(fecha);
    return parsed.toLocaleString();
}
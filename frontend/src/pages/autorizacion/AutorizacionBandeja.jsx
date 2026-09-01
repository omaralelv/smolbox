import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import Drawer from '../../components/shared/Drawer';
import { VISIBILIDAD, PUEDE_LEER_OBSERVACION } from '../../components/shared/roles';

import {
    addExpenseObservation,
    apiErrorMessage,
    authorizeExpense,
    currentToken,
    executeRequestAction,
    getFrontendBandeja,
    getFrontendSolicitud,
    getRequestAuditEvents,
    rejectAuthorizationExpense,
} from '../../lib/api';


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
    const navigate = useNavigate();
    const location = useLocation();
    
    const solicitudInicialBackendId = location.state?.solicitudBackendId || null;
    const [gastos, setGastos] = useState(() => gastosDesdeState(location.state));


    // 1. ESTADOS PARA CONTROLAR LOS PANELES Y OBSERVACIONES
    const [documentoActivo, setDocumentoActivo] = useState(null); // 'factura' | 'vale' | null
    const [observacionesAbiertas, setObservacionesAbiertas] = useState(false);
    const [gastoSeleccionado, setGastoSeleccionado] = useState(null);
    const solicitudBackendId = gastoSeleccionado?.solicitudBackendId || solicitudInicialBackendId;

    // Estado del chat de observaciones
    const [comentario, setComentario] = useState('');
    const [historial, setHistorial] = useState(() => (solicitudInicialBackendId ? [] : HISTORIAL_MOCK));
    const [confirmacionAutorizacion, setConfirmacionAutorizacion] = useState(null);
    const [justificacionRechazo, setJustificacionRechazo] = useState('');
    const [errorJustificacion, setErrorJustificacion] = useState('');
    const [guardandoDecision, setGuardandoDecision] = useState(false);

    // 2. NORMALIZAR EL ROL
    const rol = String(
        currentRole || localStorage.getItem('smolboxFrontendRole') || localStorage.getItem('currentRole') || 'admin'
    ).toLowerCase().trim();

    const gastosDesglosados = gastos;

    const cargarGastosAutorizacion = async () => {
        const solicitudes = solicitudInicialBackendId
            ? [await getFrontendSolicitud(solicitudInicialBackendId)]
            : await getFrontendBandeja();

        const nuevosGastos = solicitudes.flatMap(gastosAutorizacionDesdeSolicitud);
        setGastos(nuevosGastos);
        setGastoSeleccionado((actual) => {
            if (!actual) return actual;
            return nuevosGastos.find((gasto) => idsIguales(gastoHistorialId(gasto), gastoHistorialId(actual))) || actual;
        });
    };

    useEffect(() => {
        let activo = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                activo = false;
            };
        }

        const cargar = async () => {
            try {
                const solicitudes = solicitudInicialBackendId
                    ? [await getFrontendSolicitud(solicitudInicialBackendId)]
                    : await getFrontendBandeja();

                if (!activo) return;
                setGastos(solicitudes.flatMap(gastosAutorizacionDesdeSolicitud));
            } catch (error) {
                if (activo) alert(apiErrorMessage(error));
            }
        };

        cargar();

        return () => {
            activo = false;
        };
    }, [navigate, solicitudInicialBackendId]);


    // Función para cambiar el estatus al dar clic en los botones
    const handleCambiarEstado = async (gasto, nuevoEstado, decision) => {
        const expenseId = gasto.backendId || gasto.id;
        const requestId = gasto.solicitudBackendId;

        if (!requestId || !expenseId) {
            setGastos(prevGastos =>
                prevGastos.map(item =>
                    item.id === gasto.id ? { ...item, estado: nuevoEstado } : item
                )
            );
            return true;
        }

        try {
            await asegurarSolicitudEnRevisionAutorizacion(requestId);

            if (nuevoEstado === 'Autorizada') {
                await authorizeExpense(expenseId, decision.note);
            } else {
                await rejectAuthorizationExpense(expenseId, decision.reason);
            }

            await avanzarSolicitudSiAutorizacionCompleta(requestId);
            await cargarGastosAutorizacion();
            return true;
        } catch (error) {
            alert(apiErrorMessage(error));
            return false;
        }
    };

    const abrirConfirmacionCambio = (gasto, nuevoEstado) => {
        setGastoSeleccionado(gasto);
        setConfirmacionAutorizacion({ gasto, nuevoEstado });
        setJustificacionRechazo('');
        setErrorJustificacion('');
    };

    const cerrarConfirmacionCambio = () => {
        if (guardandoDecision) return;
        setConfirmacionAutorizacion(null);
        setJustificacionRechazo('');
        setErrorJustificacion('');
    };

    const confirmarDecisionAutorizacion = async () => {
        if (!confirmacionAutorizacion) return;

        const { gasto, nuevoEstado } = confirmacionAutorizacion;
        const decision = decisionDesdeConfirmacion(nuevoEstado, justificacionRechazo);

        if (!decision) {
            setErrorJustificacion('La justificación es obligatoria para no autorizar el gasto.');
            return;
        }

        setGuardandoDecision(true);
        const actualizado = await handleCambiarEstado(gasto, nuevoEstado, decision);
        setGuardandoDecision(false);

        if (actualizado) {
            setConfirmacionAutorizacion(null);
            setJustificacionRechazo('');
            setErrorJustificacion('');
        }
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


    const refrescarHistorialBackend = async () => {
        if (!solicitudBackendId) return;

        const eventos = await getRequestAuditEvents(solicitudBackendId);
        const obsIniciales = (gastosDesglosados || [])
            .map(observacionInicialDesdeGasto)
            .filter(Boolean);
        const obsEventos = historialDesdeEventos(eventos || []);

        setHistorial(
            [...obsIniciales, ...obsEventos].sort(
                (a, b) => a.fechaTimestamp - b.fechaTimestamp
            )
        );
    };


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
                                            onClick={() => abrirConfirmacionCambio(gasto, 'Autorizada')}
                                        >
                                            {ocultarTienda ? '✓' : 'AUTORIZAR'}
                                        </button>
                                        <button
                                            style={styles.btnNoAutorizar}
                                            onClick={() => abrirConfirmacionCambio(gasto, 'No Autorizada')}
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

            {confirmacionAutorizacion && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modal}>
                        <h3 style={styles.modalTitle}>
                            {confirmacionAutorizacion.nuevoEstado === 'Autorizada'
                                ? 'Confirmar autorización'
                                : 'No autorizar gasto'}
                        </h3>
                        <p style={styles.modalText}>
                            {confirmacionAutorizacion.nuevoEstado === 'Autorizada'
                                ? `¿Confirmas autorizar ${confirmacionAutorizacion.gasto?.nombre || 'este gasto'}?`
                                : `Escribe la justificación para no autorizar ${confirmacionAutorizacion.gasto?.nombre || 'este gasto'}.`}
                        </p>
                        {confirmacionAutorizacion.nuevoEstado === 'No Autorizada' && (
                            <>
                                <textarea
                                    style={styles.modalTextarea}
                                    value={justificacionRechazo}
                                    onChange={(event) => {
                                        setJustificacionRechazo(event.target.value);
                                        if (errorJustificacion) setErrorJustificacion('');
                                    }}
                                    placeholder="Justificación"
                                    disabled={guardandoDecision}
                                />
                                {errorJustificacion && (
                                    <p style={styles.modalError}>{errorJustificacion}</p>
                                )}
                            </>
                        )}
                        <div style={styles.modalActions}>
                            <button
                                type="button"
                                style={styles.btnCancelarModal}
                                onClick={cerrarConfirmacionCambio}
                                disabled={guardandoDecision}
                            >
                                Cancelar
                            </button>
                            <button
                                type="button"
                                style={
                                    confirmacionAutorizacion.nuevoEstado === 'Autorizada'
                                        ? styles.btnConfirmarModal
                                        : styles.btnRechazarModal
                                }
                                onClick={confirmarDecisionAutorizacion}
                                disabled={guardandoDecision}
                            >
                                {guardandoDecision
                                    ? 'Guardando...'
                                    : confirmacionAutorizacion.nuevoEstado === 'Autorizada'
                                        ? 'Autorizar'
                                        : 'No autorizar'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
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
    modalOverlay: {
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.35)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
    },
    modal: {
        width: 'min(420px, calc(100vw - 32px))',
        backgroundColor: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        boxShadow: '0 12px 30px rgba(0, 0, 0, 0.2)',
        padding: '22px',
        fontFamily: 'sans-serif',
    },
    modalTitle: {
        margin: '0 0 10px',
        fontSize: '18px',
        color: 'var(--text)',
    },
    modalText: {
        margin: '0 0 14px',
        fontSize: '14px',
        lineHeight: 1.4,
        color: '#333',
    },
    modalTextarea: {
        width: '100%',
        minHeight: '92px',
        resize: 'vertical',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '10px',
        fontSize: '14px',
        fontFamily: 'sans-serif',
        boxSizing: 'border-box',
    },
    modalError: {
        margin: '8px 0 0',
        fontSize: '12px',
        color: 'var(--text-denegada)',
    },
    modalActions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '10px',
        marginTop: '18px',
    },
    btnCancelarModal: {
        backgroundColor: 'transparent',
        color: '#333',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        padding: '8px 14px',
        fontSize: '12px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
    btnConfirmarModal: {
        backgroundColor: 'var(--text-pagada)',
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '6px',
        padding: '8px 14px',
        fontSize: '12px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
    btnRechazarModal: {
        backgroundColor: 'var(--text-denegada)',
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '6px',
        padding: '8px 14px',
        fontSize: '12px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
};

export default AutorizacionBandeja;


function gastosDesdeState(state) {
    if (!state?.desglose?.length) return [];
    return state.desglose.map((gasto) => ({
        ...gasto,
        backendId: gasto.backendId || gasto.backend_id || gasto.id,
        solicitudBackendId: state.solicitudBackendId || gasto.solicitudBackendId,
        tienda: gasto.tienda || state.solicitud?.tienda || '',
        tipo: gasto.tipo || gasto.type || '',
        estado: estadoAutorizacionDesdeGasto(gasto),
    }));
}

function gastosAutorizacionDesdeSolicitud(solicitud) {
    const solicitudBackendId = solicitud?.backendId || solicitud?.backend_id;
    const solicitudStatus = solicitud?.backendStatus || solicitud?.backend_status;
    if (!['submitted', 'authorization_review'].includes(solicitudStatus)) return [];

    return (solicitud?.gastos || [])
        .filter((gasto) => Boolean(gasto.requiresAuthorization || gasto.requires_authorization))
        .map((gasto) => ({
            ...gasto,
            backendId: gasto.backendId || gasto.backend_id || gasto.id,
            solicitudBackendId,
            solicitudFolio: solicitud?.folio || solicitud?.id,
            tienda: gasto.tienda || solicitud?.tienda || '',
            tipo: gasto.tipo || gasto.type || 'Gasto General',
            estado: estadoAutorizacionDesdeGasto(gasto),
            urlRecibo: gasto.urlRecibo || gasto.downloadUrl,
        }));
}

function estadoAutorizacionDesdeGasto(gasto) {
    const autorizacion = String(gasto?.autorizacion || '').toLowerCase().trim();
    const status = String(gasto?.backendStatus || gasto?.backend_status || gasto?.status || '').toLowerCase().trim();

    if (autorizacion === 'autorizado' || status === 'approved') return 'Autorizada';
    if (autorizacion === 'no_autorizado' || status === 'rejected') return 'No Autorizada';
    return 'Pendiente';
}

function decisionDesdeConfirmacion(nuevoEstado, justificacionRechazo) {
    if (nuevoEstado === 'Autorizada') {
        return { note: 'Gasto autorizado desde pantalla de autorización.' };
    }

    const cleanReason = justificacionRechazo.trim();
    if (!cleanReason) return null;

    return { reason: cleanReason };
}

async function asegurarSolicitudEnRevisionAutorizacion(requestId) {
    let solicitud = await getFrontendSolicitud(requestId);
    const status = solicitud?.backendStatus || solicitud?.backend_status;

    if (status === 'submitted' && solicitud?.availableActions?.includes('start_authorization_review')) {
        await executeRequestAction(requestId, 'start_authorization_review');
        solicitud = await getFrontendSolicitud(requestId);
    }

    return solicitud;
}

async function avanzarSolicitudSiAutorizacionCompleta(requestId) {
    const solicitud = await getFrontendSolicitud(requestId);
    const tienePendientes = (solicitud?.gastos || []).some((gasto) => (
        Boolean(gasto.requiresAuthorization || gasto.requires_authorization)
        && estadoAutorizacionDesdeGasto(gasto) === 'Pendiente'
    ));

    if (!tienePendientes && solicitud?.availableActions?.includes('approve_authorization')) {
        await executeRequestAction(requestId, 'approve_authorization');
    }
}


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

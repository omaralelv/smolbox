import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import {
    ACTION_TARGET_STATUS,
    apiErrorMessage,
    currentToken,
    executeRequestAction,
    getFrontendSolicitud,
    runAutomatedReview,
} from '../lib/api';

// Acciones que executeRequestAction() sabe ejecutar de verdad (transicion
// generica por ACTION_TARGET_STATUS, o los dos endpoints especiales).
// Cualquier otra accion (edit_expense, add_expense, authorize_expense...)
// necesita su propia pantalla/formulario y no se debe pintar como boton aqui.
const RENDERABLE_EXTRA_ACTIONS = new Set(['prepare_sap_policy', 'record_payment']);

function esAccionRenderizable(accion) {
    return Object.prototype.hasOwnProperty.call(ACTION_TARGET_STATUS, accion)
        || RENDERABLE_EXTRA_ACTIONS.has(accion);
}

const ESTILO_POR_ACCION = {
    submit_request: 'btnFilledCoral',
    approve_authorization: 'btnFilledCoral',
    start_accounting_manager_review: 'btnFilledCoral',
    approve_accounting_manager: 'btnFilledCoral',
    send_to_direction: 'btnFilledCoral',
    approve_direction: 'btnBlue',
    mark_approved_for_payment: 'btnBlue',
    record_payment: 'btnGreen',
    close_request: 'btnGreen',
};

function estiloParaAccion(accion) {
    return ESTILO_POR_ACCION[accion] || 'btnOutline';
}

function Acumulado( {currentRole} ) {

    const navigate = useNavigate();
    const location = useLocation();


    // 1. RECUPERAR LA SOLICITUD ENVIADA DESDE LA BANDEJA
    const [solicitudActual, setSolicitudActual] = useState(location.state?.solicitud || null);
    const solicitudSeleccionada = solicitudActual || location.state?.solicitud;
    const solicitudBackendId = solicitudSeleccionada?.backendId || solicitudSeleccionada?.folio || solicitudSeleccionada?.id;

    useEffect(() => {
        let activo = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                activo = false;
            };
        }

        if (!solicitudBackendId) return undefined;

        getFrontendSolicitud(solicitudBackendId)
            .then((solicitud) => {
                if (activo) setSolicitudActual(solicitud);
            })
            .catch(() => {});

        return () => {
            activo = false;
        };
    }, [solicitudBackendId, currentRole, navigate]);

    // Si no viene ninguna desde la bandeja (p. ej. recargaron la página), usamos datos base
    const datosSolicitud = {
        folio: solicitudSeleccionada?.id || "Solicitud T-001",
        fecha: solicitudSeleccionada?.fecha || "13/08/2026",
        tienda: solicitudSeleccionada?.tienda || "T-001",
        gerente: solicitudSeleccionada?.gerente || "Karen Ponce Hernández",
        cuentaBancaria: solicitudSeleccionada?.cuentaBancaria || "101328508"
    };

    // 2. RECUPERAR LOS GASTOS DE ESTA SOLICITUD
    // Si la solicitud trae gastos cargados los usa; si no, muestra el desglose por defecto
    const gastosBrutos = solicitudSeleccionada?.gastos?.length > 0 
        ? solicitudSeleccionada.gastos.map((g, index) => ({
            id: index + 1,
            tipo: g.tipo || g.type || 'Gasto General',
            facturas: g.facturas || 1,
            monto: parseFloat(g.monto) || 0,
            folio: g.folio || 'N/A'
            }))
        : [
            { id: 1, tipo: 'Servicio de Agua Municipio', facturas: 0, monto: 0.00 },
            { id: 2, tipo: 'Papelería', facturas: 1, monto: 56.00 },
            { id: 3, tipo: 'Alimentos', facturas: 0, monto: 0.00 },
            { id: 4, tipo: 'Bolsas', facturas: 0, monto: 0.00 },
            { id: 5, tipo: 'Sistemas', facturas: 2, monto: 268.01 },
            { id: 6, tipo: 'Equipo Menor', facturas: 0, monto: 0.00 },
            { id: 7, tipo: 'Artículos de Limpieza', facturas: 0, monto: 0.00 },
        ];


    // AGRUPACIÓN DINÁMICA CON REDUCE
    const resumenGastos = Object.values(
        gastosBrutos.reduce((acc, gastoActual) => {
            const categoria = gastoActual.tipo || gastoActual.type || 'Gasto General';
            const numFacturas = parseInt(gastoActual.facturas || 1, 10);
            const montoGasto = parseFloat(gastoActual.monto || 0);

            if (!acc[categoria]) {
                acc[categoria] = {
                    id: categoria,
                    tipo: categoria,
                    facturas: 0,
                    monto: 0,
                    elementosOriginales: [] // Guardamos el desglose individual para cuando den clic en "Ver detalle"
                };
            }

            acc[categoria].facturas += numFacturas;
            acc[categoria].monto += montoGasto;
            acc[categoria].elementosOriginales.push(gastoActual);

            return acc;
        }, {})
    );



    // CÁLCULO DINÁMICO DE TOTALES
    const totalFacturas = resumenGastos.reduce((acc, curr) => acc + curr.facturas, 0);
    const totalMonto = resumenGastos.reduce((acc, curr) => acc + curr.monto, 0).toFixed(2);



    async function ejecutarAcciones(acciones, mensajeExito) {
        if (!solicitudBackendId) return;

        try {
            let solicitud = await getFrontendSolicitud(solicitudBackendId);
            for (const accion of acciones) {
                const accionPermitida = solicitud.availableActions?.includes(accion) || accion === 'prepare_sap_policy';
                if (!accionPermitida) continue;
                await executeRequestAction(solicitud.backendId, accion);
                solicitud = await getFrontendSolicitud(solicitud.backendId);
            }
            setSolicitudActual(solicitud);
            localStorage.setItem('bandejaSolicitudes', JSON.stringify([solicitud]));
            alert(mensajeExito);
            navigate('/bandeja');
        } catch (error) {
            alert(apiErrorMessage(error));
        }
    }

    async function ejecutarRevisionAutomatica() {
        if (!solicitudSeleccionada?.backendId) return;

        try {
            await runAutomatedReview(solicitudSeleccionada.backendId);
            alert('Revisión automática ejecutada.');
        } catch (error) {
            alert(apiErrorMessage(error));
        }
    }

    // 3. BOTONES DE ACCION: se generan a partir de lo que el backend dice que
    // el usuario puede hacer ahora mismo (solicitud.availableActions), no de
    // una lista fija por rol. Asi el boton nunca queda desincronizado del
    // flujo real: si el backend agrega/quita una accion, el boton aparece o
    // desaparece solo.
    const renderBotonesPorRol = () => {
        if (currentRole === 'tienda' || currentRole === 'supervisor') {
            // Tienda captura desde Solicitud/Añadir Gasto; autorización todavía
            // no tiene pantalla propia. Sin botones de flujo aquí.
            return null;
        }

        const accionesDisponibles = (solicitudSeleccionada?.availableActions || [])
            .filter(esAccionRenderizable);
        const etiquetas = solicitudSeleccionada?.actionLabels || {};

        const botonesAcciones = accionesDisponibles.map((accion) => (
            <button
                key={accion}
                style={styles[estiloParaAccion(accion)]}
                onClick={() => ejecutarAcciones([accion], `${etiquetas[accion] || accion} completado.`)}
            >
                {etiquetas[accion] || accion}
            </button>
        ));

        if (currentRole === 'contabilidad' || currentRole === 'admin') {
            return (
                <>
                    <button style={styles.btnOutline} onClick={ejecutarRevisionAutomatica}>Cargar Reembolso</button>
                    {botonesAcciones}
                </>
            );
        }

        return botonesAcciones.length > 0 ? botonesAcciones : null;
    };

    const botonesGuardados = renderBotonesPorRol();


    return (
        <div style={styles.container}>
            {/* CABECERA DE LA SOLICITUD */}
            <div style={styles.headerRow}>
                <h2 style={styles.title}> Solicitud {datosSolicitud.folio}</h2>
                <button style={styles.regresarBtn} onClick={() => navigate(-1)}>
                    Regresar
                </button>
            </div>

            {/* CAMPOS SUPERIORES DE DATOS */}
            <div style={styles.gridAuto}>
                <div style={styles.inputGroup}>
                    <label style={styles.label}>Fecha</label>
                    <div style={styles.disabledInput}>{datosSolicitud.fecha}</div>
                </div>
                <div style={styles.inputGroup}>
                    <label style={styles.label}>Tienda</label>
                    <div style={styles.disabledInput}>{datosSolicitud.tienda}</div>
                </div>
                <div style={styles.inputGroup}>
                    <label style={styles.label}>Gerente</label>
                    <div style={styles.disabledInput}>{datosSolicitud.gerente}</div>
                </div>
                <div style={styles.inputGroup}>
                    <label style={styles.label}>Cuenta bancaria</label>
                    <div style={styles.disabledInput}>{datosSolicitud.cuentaBancaria}</div>
                </div>
            </div>

            {/* TABLA DE RESUMEN DE GASTOS */}
            <div style={styles.tableContainer}>
                <div style={styles.tableHeader}>
                    <span style={{ flex: 2, textAlign: 'left', paddingLeft: '20px' }}>TIPO DE GASTO</span>
                    <span style={{ flex: 1, textAlign: 'center' }}># FACTURAS</span>
                    <span style={{ flex: 1, textAlign: 'center' }}>MONTO</span>
                    <span style={{ width: '120px' }}></span>
                </div>

                {resumenGastos.map((item) => (
                    <div key={item.id} style={styles.tableRow}>
                        <span style={{ flex: 2, textAlign: 'left', paddingLeft: '20px' }}>{item.tipo}</span>
                        <span style={{ flex: 1, textAlign: 'center' }}>{item.facturas}</span>
                        <span style={{ flex: 1, textAlign: 'center' }}>{item.monto.toFixed(2)}</span>
                        <span style={styles.verDetalleLink}
                            onClick={() => {
                                navigate('/detalle', { 
                                    state: { 
                                        categoria: item.tipo, 
                                        solicitudFolio: datosSolicitud.folio,
                                        solicitudBackendId: solicitudSeleccionada?.backendId,
                                        desglose: item.elementosOriginales || []
                                    } 
                                });
                            }}
                        > Ver detalle</span>
                    </div>
                ))}
            </div>

            {/* FILA DE TOTALES */}
            <div style={styles.totalRow}>
                <span style={{ flex: 2, textAlign: 'left', paddingLeft: '20px', fontWeight: 'bold' }}>TOTAL</span>
                <span style={{ flex: 1, textAlign: 'center', fontWeight: 'bold' }}>{totalFacturas}</span>
                <span style={{ flex: 1, textAlign: 'center', fontWeight: 'bold' }}>{totalMonto}</span>
                <span style={{ width: '120px' }}></span>
            </div>

            {/* PIE DE PÁGINA FIJO DE ACCIONES DINÁMICAS */}

            {botonesGuardados && (
                <div style={styles.fixedStickyFooter}>
                    <div style={styles.footerActionContainer}>
                        {botonesGuardados}
                    </div>
                </div>
            )}
        </div>
    );
}

// 🎨 ESTILOS INTEGRADOS Y FIJO EN INFERIOR
const styles = {
    container: {
        maxWidth: '1000px',
        margin: '0 auto',
        padding: '20px',
        paddingBottom: '120px',
        textAlign: 'left',
    },
    headerRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
    },
    title: {
        margin: 0,
        fontSize: '22px',
        color: '#333',
    },
    regresarBtn: {
        backgroundColor: 'transparent',
        border: '1px solid var(--sb-btnBorder)',
        color: 'var(--text-WBtn)',
        borderRadius: '20px',
        padding: '6px 20px',
        fontSize: '13px',
        fontWeight: 'bold',
        boxShadow: 'var(--shadow)',
        cursor: 'pointer',
    },
    gridAuto: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '20px',
        marginBottom: '30px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '5px',
    },
    label: {
        fontSize: '13px',
        fontWeight: 'bold',
        textAlign: 'center',
        padding: '6px 0px',
        color: '#333',
    },
    disabledInput: {
        backgroundColor: '#ffffff',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '7px',
        padding: '8px 12px',
        fontSize: '14px',
        textAlign: 'center',
        color: '#444',
    },
    tableContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        marginBottom: '15px',
    },
    tableHeader: {
        display: 'flex',
        fontSize: '13px',
        fontWeight: 'bold',
        color: '#000',
        padding: '0 10px',
    },
    tableRow: {
        display: 'flex',
        alignItems: 'center',
        backgroundColor: '#ffffff',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '7px',
        padding: '8px 10px',
        fontSize: '13px',
        color: '#444',
    },
    verDetalleLink: {
        width: '120px',
        textAlign: 'center',
        color: 'var(--text-WBtn)',
        fontWeight: 'bold',
        cursor: 'pointer',
        fontSize: '13px',
    },
    totalRow: {
        display: 'flex',
        alignItems: 'center',
        padding: '10px',
        fontSize: '15px',
        color: '#000',
        marginBottom: '20px',
    },
    fixedStickyFooter: {
        position: 'fixed',
        bottom: 0,
        left: 0,
        width: '100%',
        backgroundColor: '#fffcfc',
        boxShadow: '0 -4px 10px rgba(0, 0, 0, 0.04)',
        padding: '18px 20px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 1000,
        borderTop: '1px solid #ffe3e3',
    },
    footerActionContainer: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: '15px',
        justifyContent: 'center',
        alignItems: 'center',
        maxWidth: '1100px',
    },
    // Estilos para los tipos de botones
    btnOutline: {
        backgroundColor: '#ffffff',
        border: '1px solid var(--sb-btnBorder)',
        color: 'var(--text-WBtn)',
        borderRadius: '12px',
        padding: '10px 22px',
        fontSize: '14px',
        fontWeight: '600',
        cursor: 'pointer',
    },
    btnFilledCoral: {
        backgroundColor: 'var(--sb-sendBtnBg)',
        border: 'none',
        color: '#ffffff',
        borderRadius: '12px',
        padding: '10px 22px',
        fontSize: '14px',
        fontWeight: 'bold',
        boxShadow: 'var(--shadow)',
        cursor: 'pointer',
    },
    btnBlue: {
        backgroundColor: 'var(--sb-aprobadaBg)',
        border: '1px solid var(--text-aprobada)',
        color: 'var(--text-aprobada)',
        borderRadius: '12px',
        padding: '10px 22px',
        fontSize: '14px',
        fontWeight: 'bold',
        boxShadow: 'var(--shadow-blue)',
        cursor: 'pointer',
    },
    btnGreen: {
        backgroundColor: 'var(--sb-pagadaBg)',
        border: '1px solid var(--text-pagada)',
        color: '#2e7d1f',
        borderRadius: '12px',
        padding: '10px 22px',
        fontSize: '14px',
        fontWeight: 'bold',
        boxShadow: 'var(--shadow-green)',
        cursor: 'pointer',
    }
};

export default Acumulado;

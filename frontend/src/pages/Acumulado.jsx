import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import {
    apiErrorMessage,
    currentToken,
    executeRequestAction,
    getFrontendSolicitud,
    runAutomatedReview,
} from '../lib/api';

const ACTION_BUTTONS = {
    start_accounting_review: {
        label: 'Iniciar revisión contable',
        styleKey: 'btnFilledCoral',
        success: 'Revisión contable iniciada.',
    },
    mark_accounting_reviewed: {
        label: 'Cerrar contabilidad',
        styleKey: 'btnFilledCoral',
        success: 'Revisión contable cerrada.',
    },
    prepare_sap_policy: {
        label: 'Póliza y Reembolso',
        styleKey: 'btnOutline',
        success: 'Póliza preparada.',
    },
    start_accounting_manager_review: {
        label: 'Enviar a Gerencia',
        styleKey: 'btnFilledCoral',
        success: 'Solicitud enviada a gerencia.',
    },
    approve_accounting_manager: {
        label: 'Enviar a Tesorería',
        styleKey: 'btnFilledCoral',
        success: 'Solicitud enviada a tesorería.',
    },
    return_to_accounting: {
        label: 'Regresar Acumulado',
        styleKey: 'btnOutline',
        success: 'Solicitud regresada a contabilidad.',
    },
    start_treasury_review: {
        label: 'Revisión tesorería',
        styleKey: 'btnFilledCoral',
        success: 'Revisión de tesorería iniciada.',
    },
    send_to_direction: {
        label: 'Enviar Dirección',
        styleKey: 'btnFilledCoral',
        success: 'Solicitud enviada a dirección.',
    },
    return_to_manager: {
        label: 'Regresar acumulado',
        styleKey: 'btnOutline',
        success: 'Solicitud regresada a gerencia.',
    },
    approve_direction: {
        label: 'Aprobar Dirección',
        styleKey: 'btnBlue',
        success: 'Solicitud aprobada por dirección.',
    },
    return_to_treasury: {
        label: 'Regresar Acumulado',
        styleKey: 'btnOutline',
        success: 'Solicitud regresada a tesorería.',
    },
    mark_approved_for_payment: {
        label: 'Aprobar pago',
        styleKey: 'btnBlue',
        success: 'Pago aprobado.',
    },
    record_payment: {
        label: 'Confirmar pago',
        styleKey: 'btnGreen',
        success: 'Pago confirmado.',
    },
    close_request: {
        label: 'Cerrar solicitud',
        styleKey: 'btnGreen',
        success: 'Solicitud cerrada.',
    },
    reject_request: {
        label: 'Rechazar solicitud',
        styleKey: 'btnOutline',
        success: 'Solicitud rechazada.',
    },
};

const AUTOMATED_REVIEW_STATUSES = new Set([
    'submitted',
    'authorized',
    'under_accounting_review',
    'accounting_reviewed',
]);

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
                const accionPermitida = solicitud.availableActions?.includes(accion);
                if (!accionPermitida) {
                    throw new Error('La solicitud todavía no está lista para esa acción. Actualiza la bandeja e intenta el siguiente paso disponible.');
                }
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

    const renderBotonesDisponibles = () => {
        const acciones = solicitudSeleccionada?.availableActions || [];
        const botones = acciones
            .map((accion) => {
                const config = ACTION_BUTTONS[accion];
                if (!config) return null;
                return (
                    <button
                        key={accion}
                        style={styles[config.styleKey]}
                        onClick={() => ejecutarAcciones([accion], config.success)}
                    >
                        {config.label}
                    </button>
                );
            })
            .filter(Boolean);

        if (
            ['contabilidad', 'admin'].includes(currentRole)
            && solicitudSeleccionada?.backendId
            && AUTOMATED_REVIEW_STATUSES.has(solicitudSeleccionada?.backendStatus)
        ) {
            botones.splice(
                1,
                0,
                <button key="automated-review" style={styles.btnOutline} onClick={ejecutarRevisionAutomatica}>
                    Cargar Reembolso
                </button>
            );
        }

        return botones.length ? <>{botones}</> : null;
    };

    const botonesGuardados = renderBotonesDisponibles();



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

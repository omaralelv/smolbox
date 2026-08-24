import { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import {
    apiErrorMessage,
    currentToken,
    executeRequestAction,
    getFrontendSolicitud,
    runAutomatedReview,
} from '../lib/api';

function Acumulado( {currentRole} ) {

    const navigate = useNavigate();
    const location = useLocation();
    const autoTransitionRef = useRef(new Set());


    // 1. RECUPERAR LA SOLICITUD ENVIADA DESDE LA BANDEJA
    const [solicitudActual, setSolicitudActual] = useState(location.state?.solicitud || null);
    const solicitudSeleccionada = solicitudActual || location.state?.solicitud || null;
    const solicitudBackendId = solicitudSeleccionada?.backendId || solicitudSeleccionada?.reimbursementRequestId || solicitudSeleccionada?.id;

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
            .then(async (solicitud) => {
                const accionInicial = accionInicialPorRol(currentRole, solicitud);
                const autoTransitionKey = `${solicitud.backendId}:${accionInicial || 'none'}`;

                if (
                    accionInicial
                    && !autoTransitionRef.current.has(autoTransitionKey)
                    && solicitud.availableActions?.includes(accionInicial)
                ) {
                    autoTransitionRef.current.add(autoTransitionKey);
                    await executeRequestAction(solicitud.backendId, accionInicial);
                    solicitud = await getFrontendSolicitud(solicitud.backendId);
                }

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
        ? solicitudSeleccionada.gastos.filter(gastoActivo).map((g, index) => ({
            id: index + 1,
            backendId: g.backendId || g.id,
            nombre: g.nombre || `Gasto ${index + 1}`,
            tipo: g.tipo || g.type || 'Gasto General',
            facturas: g.facturas || 1,
            monto: parseFloat(g.monto) || 0,
            folio: g.folio || 'N/A',
            folioFiscal: g.folioFiscal || g.folio_fiscal || g.folio || null,
            autorizacion: g.autorizacion || '',
            status: g.status || '',
            backendStatus: g.backendStatus || g.backend_status || '',
            requiresAuthorization: Boolean(g.requiresAuthorization || g.requires_authorization),
            downloadUrl: g.downloadUrl || g.download_url || null,
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



    // 2.5 Función para el frontend (la puede poner en su archivo de API o en el componente)
    const handleDescargarPoliza = async (solicitudId) => {
    console.log("Click en Póliza y Reembolso");
    console.log("UUID recibido por la función:", solicitudId);

    if (!solicitudId) {
        alert("No se encontró el UUID interno de la solicitud.");
        return;
    }

    const token = currentToken();

    if (!token) {
        alert("Tu sesión expiró. Inicia sesión nuevamente.");
        navigate("/login");
        return;
    }

    const url =
    `/api/v1/macro/generar-polizas/` +
    encodeURIComponent(String(solicitudId).trim());

    console.log("URL solicitada:", url);

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (!response.ok) {
            const contenidoError = await response.text();

            console.error(
                "Respuesta de macro:",
                response.status,
                contenidoError
            );

            throw new Error(
                `Error ${response.status}: ${contenidoError}`
            );
        }

        const blob = await response.blob();

        if (blob.size === 0) {
            throw new Error(
                "El backend respondió, pero el ZIP está vacío."
            );
        }
        const contentDisposition = response.headers.get(
        "content-disposition"
        );

        let nombreArchivo = "Polizas_Reembolso.zip";

        if (contentDisposition) {
        const coincidencia = contentDisposition.match(
            /filename="?([^";]+)"?/i
        );

            if (coincidencia?.[1]) {
                nombreArchivo = coincidencia[1];
            }
        }

        const urlDescarga = window.URL.createObjectURL(blob);
        const enlace = document.createElement("a");

        enlace.href = urlDescarga;
        enlace.download = nombreArchivo;

        document.body.appendChild(enlace);
        enlace.click();
        enlace.remove();

        window.URL.revokeObjectURL(urlDescarga);

    } catch (error) {
        console.error("Error descargando pólizas:", error);

        alert(
            "Hubo un problema descargando las pólizas: "
            + error.message
        );
    }
};



    // 3. MATRIZ DE CONFIGURACIÓN DE BOTONES POR ROL
    const renderBotonesPorRol = () => {

        switch (currentRole){
            case 'tienda':
                // Sin botones en el pie de página
                return null;

            case 'supervisor':
                return null;

            case 'contabilidad':
                return (
                    <>
                        <button
                            style={styles.btnOutline}
                            onClick={() => handleDescargarPoliza(solicitudBackendId)}>
                        Póliza y Reembolso</button>
                        <button style={styles.btnOutline} onClick={ejecutarRevisionAutomatica}>Cargar Reembolso</button>
                        <button
                            style={styles.btnFilledCoral}
                            onClick={() => ejecutarAcciones(
                                ['start_accounting_review', 'mark_accounting_reviewed', 'prepare_sap_policy', 'start_accounting_manager_review'],
                                'Solicitud enviada a gerencia.'
                            )}
                        >Enviar a Gerencia</button>
                    </>
                );

            case 'gerencia':
                return (
                    <>
                        <button
                            style={styles.btnOutline}
                            onClick={() => ejecutarAcciones(['return_to_accounting'], 'Solicitud regresada a contabilidad.')}
                        >Regresar Acumulado</button>
                        <button style={styles.btnOutline}>Ver Reembolso</button>
                        <button
                            style={styles.btnFilledCoral}
                            onClick={() => ejecutarAcciones(
                                ['start_accounting_manager_review', 'approve_accounting_manager'],
                                'Solicitud enviada a tesorería.'
                            )}
                        >Enviar a Tesorería</button>
                    </>
                );

            case 'tesoreria':
                return (
                    <>
                        <button
                            style={styles.btnOutline}
                            onClick={() => ejecutarAcciones(['return_to_manager'], 'Solicitud regresada a gerencia.')}
                        >Regresar acumulado</button>
                        <button style={styles.btnOutline}>Ver Reembolso</button>
                        <button
                            style={styles.btnBlue}
                            onClick={() => ejecutarAcciones(['approve_direction'], 'Pago aprobado por dirección.')}
                        >
                            Aprobar pago
                        </button>

                        <button 
                            style={styles.btnGreen}
                            onClick={() => ejecutarAcciones(['mark_approved_for_payment', 'record_payment'], 'Pago confirmado.')}
                        >
                            Confirmar pago
                        </button>

                    </>
                );

            case 'direccion':
                return (
                    <>
                        <button style={styles.btnOutline}>Ver Reembolso</button>
                    </>
                );

            case 'admin':
            default:
                // Muestra todos los botones de la suite
                return (
                        <>
                        <button
                            style={styles.btnOutline}
                            onClick={() => ejecutarAcciones(['return_to_manager'], 'Solicitud regresada a gerencia.')}
                        >Regresar acumulado</button>
                        <button
                            style={styles.btnOutline}
                            onClick={() => handleDescargarPoliza(solicitudBackendId)}>
                        Póliza y Reembolso</button>
                        <button style={styles.btnOutline} onClick={ejecutarRevisionAutomatica}>Cargar Reembolso</button>
                        <button style={styles.btnOutline}>Ver Reembolso</button>
                        <button
                            style={styles.btnFilledCoral}
                            onClick={() => ejecutarAcciones(
                                ['start_accounting_review', 'mark_accounting_reviewed', 'prepare_sap_policy', 'start_accounting_manager_review'],
                                'Solicitud enviada a gerencia.'
                            )}
                        >Enviar a Gerencia</button>
                        <button style={styles.btnOutline}>Ver Reembolso</button>
                        <button
                            style={styles.btnFilledCoral}
                            onClick={() => ejecutarAcciones(
                                ['start_accounting_manager_review', 'approve_accounting_manager'],
                                'Solicitud enviada a tesorería.'
                            )}
                        >Enviar a Tesorería</button>

                        <button
                            style={styles.btnBlue}
                            onClick={() => ejecutarAcciones(['approve_direction'], 'Pago aprobado por dirección.')}
                        >
                            Aprobar pago
                        </button>

                        <button 
                            style={styles.btnGreen}
                            onClick={() => ejecutarAcciones(['mark_approved_for_payment', 'record_payment'], 'Pago confirmado.')}
                        >
                            Confirmar pago
                        </button>

                    </>
                );
        }
    

    
};


    const botonesGuardados = renderBotonesPorRol();

    console.log("PROP currentRole RECIBIDA EN ACUMULADO:", currentRole);
    console.log("BOTONES GENERADOS:", renderBotonesPorRol());



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

function gastoActivo(gasto) {
    const backendStatus = String(gasto.backendStatus || gasto.backend_status || '').toLowerCase();
    const status = String(gasto.status || '').toLowerCase();
    return backendStatus !== 'removed' && status !== 'eliminado';
}

function accionInicialPorRol(currentRole, solicitud) {
    const rol = String(currentRole || '').toLowerCase().trim();
    const status = solicitud?.backendStatus || solicitud?.backend_status;

    if (rol === 'admin') {
        return [
            'start_authorization_review',
            'start_accounting_review',
            'start_accounting_manager_review',
            'start_treasury_review',
        ].find((accion) => solicitud?.availableActions?.includes(accion)) || null;
    }
    if (rol === 'supervisor' && status === 'submitted') {
        return 'start_authorization_review';
    }
    if (rol === 'contabilidad' && ['submitted', 'authorized'].includes(status)) {
        return 'start_accounting_review';
    }
    if (rol === 'gerencia' && status === 'accounting_reviewed') {
        return 'start_accounting_manager_review';
    }
    if (rol === 'tesoreria' && status === 'accounting_manager_approved') {
        return 'start_treasury_review';
    }
    return null;
}

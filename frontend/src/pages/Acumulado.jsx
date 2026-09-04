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


    // ESTADOS PARA EL MODAL DE DEVOLUCIÓN Y BANNER AMARILLO
    const [showReturnModal, setShowReturnModal] = useState(false);
    const [returnReason, setReturnReason] = useState('');
    const [accionPendiente, setAccionPendiente] = useState(null);
    const [motivoDevolucion] = useState(() => {
        // Recuperar motivo guardado previamente en localStorage si existe para esta solicitud
        if (!solicitudBackendId) return solicitudSeleccionada?.motivoDevolucion || '';
        return localStorage.getItem(`motivo_dev_${solicitudBackendId}`) || solicitudSeleccionada?.motivoDevolucion || '';
    });


    // Guardamos un objeto/mapa de motivos: { tesoreria: "motivo de tesorería", gerencia: "motivo de gerencia" }
    const [motivosPorRol, setMotivosPorRol] = useState(() => {
        if (!solicitudBackendId) return {};
        const guardado = localStorage.getItem(`motivos_map_${solicitudBackendId}`);
        return guardado ? JSON.parse(guardado) : {};
    });

    const [devueltoPor, setDevueltoPor] = useState(() => {
        if (!solicitudBackendId) return solicitudSeleccionada?.devueltoPor || '';
        return localStorage.getItem(`devuelto_por_${solicitudBackendId}`) || solicitudSeleccionada?.devueltoPor || '';
    });

    const [devueltoPorOriginal, setDevueltoPorOriginal] = useState(() => {
        if (!solicitudBackendId) return solicitudSeleccionada?.devueltoPorOriginal || '';
        return localStorage.getItem(`devuelto_por_orig_${solicitudBackendId}`) || solicitudSeleccionada?.devueltoPor || '';
    });


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
        cuentaBancaria: solicitudSeleccionada?.cuentaBancaria || "101328508",
    };

    // 2. RECUPERAR LOS GASTOS DE ESTA SOLICITUD
    // Si la solicitud trae gastos cargados los usa; si no, muestra el desglose por defecto
    const gastosBrutos = solicitudSeleccionada?.gastos?.length > 0 
        ? solicitudSeleccionada.gastos.map((g, index) => ({
            id: index + 1,
            backendId: g.backendId || g.id,
            nombre: g.nombre || `Gasto ${index + 1}`,
            tipo: g.tipo || g.type || 'Gasto General',
            facturas: g.facturas || 1,
            monto: parseFloat(g.monto) || 0,         
            observaciones: g.observaciones || g.observacion || '',
            folio: g.folio || 'N/A',
            folioFiscal: g.folioFiscal || g.folio_fiscal || g.folio || null,
            cfdiSubtotal: valorFiscalOculto(g.cfdiSubtotal ?? g.cfdi_subtotal),
            cfdiTotal: valorFiscalOculto(g.cfdiTotal ?? g.cfdi_total),
            cfdiTaxAmount: valorFiscalOculto(g.cfdiTaxAmount ?? g.cfdi_tax_amount),
            cfdiTaxRate: valorFiscalOculto(g.cfdiTaxRate ?? g.cfdi_tax_rate),
            cfdiCurrency: g.cfdiCurrency ?? g.cfdi_currency ?? null,
            autorizacion: g.autorizacion || '',
            status: g.status || '',
            backendStatus: g.backendStatus || g.backend_status || '',
            requiresAuthorization: Boolean(g.requiresAuthorization || g.requires_authorization),
            downloadUrl: g.downloadUrl || g.download_url || null,
            }))
        : [
        ];


    // AGRUPACIÓN DINÁMICA CON REDUCE
    const resumenGastos = Object.values(
        gastosBrutos.reduce((acc, gastoActual) => {
            const categoria = gastoActual.tipo || gastoActual.type || 'Gasto General';
            const numFacturas = parseInt(gastoActual.facturas || 1, 10);
            const montoGasto = parseFloat(gastoActual.monto || 0);
            const activo = gastoActivo(gastoActual);

            if (!acc[categoria]) {
                acc[categoria] = {
                    id: categoria,
                    tipo: categoria,
                    facturas: 0,
                    monto: 0,
                    elementosOriginales: [] // Guardamos el desglose individual para cuando den clic en "Ver detalle"
                };
            }

            if (activo) {
                acc[categoria].facturas += numFacturas;
                acc[categoria].monto += montoGasto;
            }
            acc[categoria].elementosOriginales.push(gastoActual);

            return acc;
        }, {})
    );



    // CÁLCULO DINÁMICO DE TOTALES
    const totalFacturas = resumenGastos.reduce((acc, curr) => acc + curr.facturas, 0);
    const totalMonto = resumenGastos.reduce((acc, curr) => acc + curr.monto, 0).toFixed(2);



    async function ejecutarAcciones(acciones, mensajeExito, motivo=null) {
        if (!solicitudBackendId) return;

        try {
            let solicitud = await getFrontendSolicitud(solicitudBackendId);
            for (const accion of acciones) {
                const accionPermitida = solicitud.availableActions?.includes(accion) || accion === 'prepare_sap_policy';
                if (!accionPermitida) continue;
                await executeRequestAction(solicitud.backendId, accion);
                solicitud = await getFrontendSolicitud(solicitud.backendId);
            }



            // Si se envió un motivo de devolución, lo asociamos a la solicitud
            if (motivo) {
                solicitud.motivoDevolucion = motivo;
                localStorage.setItem(`motivo_dev_${solicitudBackendId}`, motivo);
            }

            if (['approve_direction', 'mark_approved_for_payment', 'record_payment'].some(a => acciones.includes(a))) {
            setMotivosPorRol({});
            setDevueltoPor('');
            setDevueltoPorOriginal('');
            if (solicitudBackendId) {
                localStorage.removeItem(`motivos_map_${solicitudBackendId}`);
                localStorage.removeItem(`devuelto_por_${solicitudBackendId}`);
                localStorage.removeItem(`devuelto_por_orig_${solicitudBackendId}`);
            }
        }


            setSolicitudActual(solicitud);
            localStorage.setItem('bandejaSolicitudes', JSON.stringify([solicitud]));
            alert(mensajeExito);
            navigate('/bandeja');
        } catch (error) {
            alert(apiErrorMessage(error));
        }
    }




    // MANEJADORES DE DEVOLUCIÓN (MODAL)
    const abrirModalDevolucion = (accionDevolucion) => {
        setAccionPendiente(accionDevolucion);
        setReturnReason('');
        setShowReturnModal(true);
    };

    const confirmarDevolucion = async () => {
        const cleanReason = returnReason.trim();
        if (!cleanReason) {
            alert("Por favor ingresa un motivo para regresar el acumulado.");
            return;
        }

        const accion = accionPendiente || 'return_to_accounting';
        const msg = accion === 'return_to_accounting' 
            ? 'Solicitud regresada a contabilidad.' 
            : 'Solicitud regresada a gerencia.';


        // Preservamos si Tesorería fue el origen inicial de la cadena
        //const nuevoDevueltoPor = currentRole; // Quién devuelve ahorita
        const origenInicial = devueltoPor === 'tesoreria' ? 'tesoreria' : currentRole;

        // Actualizamos el mapa de motivos sumando el motivo del rol actual
        const nuevosMotivos = {
            ...motivosPorRol,
            [currentRole]: cleanReason
        };

        // Guardamos el motivo y quién lo devolvió
        //setMotivoDevolucion(cleanReason);
        setMotivosPorRol(nuevosMotivos);
        setDevueltoPor(currentRole); // 'gerencia' o 'tesoreria'
        setDevueltoPorOriginal(origenInicial); 


        if (solicitudBackendId) {
            localStorage.setItem(`motivo_dev_${solicitudBackendId}`, cleanReason);
            localStorage.setItem(`motivos_map_${solicitudBackendId}`, JSON.stringify(nuevosMotivos));
            localStorage.setItem(`devuelto_por_${solicitudBackendId}`, currentRole);
            localStorage.setItem(`devuelto_por_orig_${solicitudBackendId}`, origenInicial);
        }

        

        setShowReturnModal(false);
        await ejecutarAcciones([accion], msg, cleanReason);
    };




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
                            onClick={() => abrirModalDevolucion('return_to_accounting')}
                        >Regresar Acumulado</button>

                        <button style={styles.btnOutline}>Ver Reembolso</button>
                        <button
                            style={styles.btnFilledCoral}
                            onClick={() => ejecutarAcciones(
                                ['start_accounting_manager_review', 'approve_accounting_manager'],
                                'Solicitud enviada a tesorería.'
                            )}
                        >Enviar a Tesorería</button>

                        <button 
                            style={styles.btnGreen}
                            onClick={() => ejecutarAcciones(['mark_approved_for_payment', 'record_payment'], 'Pago confirmado.')}
                        >
                            Confirmar pago
                        </button>
                    </>
                );

            case 'tesoreria':
                return (
                    <>
                        <button
                            style={styles.btnOutline}
                            onClick={() => abrirModalDevolucion('return_to_manager')}
                        >Regresar acumulado</button>
                        <button style={styles.btnOutline}>Ver Reembolso</button>
                        <button
                            style={styles.btnBlue}
                            onClick={() => ejecutarAcciones(['approve_direction'], 'Pago aprobado por dirección.')}
                        >
                            Aprobar pago
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
                            onClick={() => abrirModalDevolucion('return_to_manager')}
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


    // EVALUACIÓN DEL BANNER
    const currentBackendStatus = solicitudActual?.backendStatus || solicitudSeleccionada?.backendStatus || '';

    // Recuperamos también el origen inicial
    //const devueltoPorOriginal = localStorage.getItem(`devuelto_por_orig_${solicitudBackendId}`) || devueltoPor;


    // 1. ¿Está devuelto / en corrección? -> AMARILLO
    const esDevuelto = Boolean(motivoDevolucion && 
        // Caso 1: Gerencia se lo regresó a Contabilidad (o venía desde Tesorería en cadena) y Contabilidad lo ve
        (currentRole === 'contabilidad' && ['gerencia', 'tesoreria'].includes(devueltoPorOriginal)) ||
        
        // Caso 2: Tesorería se lo regresó a Gerencia y Gerencia lo está viendo
        (currentRole === 'gerencia' && devueltoPor === 'tesoreria')
    );

    // 2. ¿Ya fue re-enviado al siguiente rol? -> VERDE
    //const esResuelto = Boolean(motivoDevolucion) && (
    const esResuelto = Boolean(Object.keys(motivosPorRol).length) && (
        // Caso 1: Fue devuelto por Gerencia, pero Contabilidad ya lo corrigió y reenvió a Gerencia
        (devueltoPor === 'gerencia' && currentRole === 'gerencia' && ['accounting_reviewed', 'accounting_manager_review'].includes(currentBackendStatus)) ||
        
        // Caso 2: Fue devuelto por Tesorería, pero Gerencia ya lo corrigió y reenvió a Tesorería
        (devueltoPorOriginal === 'tesoreria' && currentRole === 'tesoreria' && ['accounting_manager_approved', 'treasury_review'].includes(currentBackendStatus))
    );




    // 3. Selección dinámica del motivo según la perspectiva del usuario
    let motivoAMostrar = '';

    if (currentRole === 'tesoreria') {
        // Tesorería siempre ve su propio motivo original con el que regresó el acumulado
        motivoAMostrar = motivosPorRol['tesoreria'] || motivosPorRol['gerencia'] || '';
    } else if (currentRole === 'contabilidad') {
        // Contabilidad ve el motivo que le puso Gerencia (o el de Tesorería si aplica)
        motivoAMostrar = motivosPorRol['gerencia'] || motivosPorRol['tesoreria'] || '';
    } else if (currentRole === 'gerencia') {
        // Gerencia ve el motivo de Tesorería si viene devuelta de Tesorería, o el que él puso si lo tiene en verde
        motivoAMostrar = devueltoPor === 'tesoreria' ? motivosPorRol['tesoreria'] : (motivosPorRol['gerencia'] || motivosPorRol['tesoreria']);
    }



    // 3. Ocultar si ya avanzó de Tesorería a Pago/Dirección o Aprobado
    const ocultarBanner = ['direction_review', 'direction_approved' ,'approved_for_payment', 'paid', 'closed', 'rejected'].includes(currentBackendStatus);
    const mostrarBanner = motivoDevolucion && !ocultarBanner && (esDevuelto || esResuelto);







    return (
        <div style={styles.container}>
            {/* CABECERA DE LA SOLICITUD */}
            <div style={styles.headerRow}>
                <h2 style={styles.title}> Solicitud {datosSolicitud.folio}</h2>
                <button style={styles.regresarBtn} onClick={() => navigate(-1)}>
                    Regresar
                </button>
            </div>



            {/* BANNER AMARILLO DE MOTIVO DE DEVOLUCIÓN */}
            {mostrarBanner && (
                <div style={esResuelto ? styles.bannerResuelto : styles.bannerDevolucion}>
                    <div style={styles.bannerHeader}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ marginRight: '8px' }}>
                            {esResuelto ? (
                                /* Icono de Check Verde */
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                            ) : (
                                /* Icono de Alerta Amarillo */
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                            )}
                        </svg>
                        <strong>{esResuelto ? 'Solicitud Resuelta' : 'Solicitud Regresada'}</strong>
                    </div>
                    <p style={styles.bannerText}>
                        <strong>Motivo de devolución: </strong> {motivoAMostrar}
                    </p>
                </div>
            )}



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



            {/* MODAL EMERGENTE PARA MOTIVO DE DEVOLUCIÓN */}
            {showReturnModal && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modalContent}>
                        <h3 style={styles.modalTitle}>Motivo de Devolución</h3>
                        <p style={styles.modalSubtitle}>
                            Por favor ingresa el motivo por el cual regresas este acumulado:
                        </p>

                        <textarea
                            style={styles.modalTextarea}
                            rows="5"
                            placeholder="Escribe aquí el motivo..."
                            value={returnReason}
                            onChange={(e) => setReturnReason(e.target.value)}
                        />

                        <div style={styles.modalActions}>
                            <button
                                style={styles.modalCancelBtn}
                                onClick={() => setShowReturnModal(false)}
                            >
                                Cancelar
                            </button>
                            <button
                                style={styles.modalConfirmBtn}
                                onClick={confirmarDevolucion}
                            >
                                Confirmar
                            </button>
                        </div>
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




    /* BANNER VERDE (RESUELTO) */
    bannerResuelto: {
        backgroundColor: '#f6ffed',
        border: '1px solid #b7eb8f',
        borderRadius: '8px',
        padding: '12px 16px',
        marginBottom: '20px',
        color: '#389e0d',
        boxShadow: '0 2px 6px rgba(82, 196, 26, 0.15)',
    },

    /* BANNER AMARILLO */
    bannerDevolucion: {
        backgroundColor: '#fffbe6',
        border: '1px solid #ffe58f',
        borderRadius: '8px',
        padding: '12px 16px',
        marginBottom: '20px',
        color: '#d48806',
        boxShadow: '0 2px 6px rgba(250, 173, 20, 0.15)',
    },
    bannerHeader: {
        display: 'flex',
        alignItems: 'center',
        fontSize: '15px',
        marginBottom: '4px',
    },
    bannerText: {
        margin: 0,
        fontSize: '13px',
        color: '#595959',
        paddingLeft: '26px',
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
    },


    /* MODAL STYLES */
    modalOverlay: {
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        backgroundColor: 'rgba(0, 0, 0, 0.4)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 2000,
    },
    modalContent: {
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        padding: '24px',
        width: '90%',
        maxWidth: '480px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
    },
    modalTitle: {
        margin: '0 0 10px 0',
        fontSize: '18px',
        color: '#333',
    },
    modalSubtitle: {
        margin: '0 0 16px 0',
        fontSize: '13px',
        color: '#666',
    },
    modalTextarea: {
        width: '100%',
        boxSizing: 'border-box',
        borderRadius: '8px',
        border: '1px solid var(--border)',
        padding: '10px',
        fontSize: '14px',
        fontFamily: 'inherit',
        marginBottom: '20px',
        resize: 'vertical',
        background: '#ffffff',
        color: 'var(--text)',
    },
    modalActions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '12px',
    },
    modalCancelBtn: {
        backgroundColor: 'transparent',
        border: '1px solid #ccc',
        color: '#555',
        borderRadius: '8px',
        padding: '8px 16px',
        fontSize: '13px',
        fontWeight: '600',
        cursor: 'pointer',
    },
    modalConfirmBtn: {
        border: '1px solid var(--sb-btnBorder)',
        background: 'var(--gradient)',
        color: 'var(--text-CBtn)',
        borderRadius: '20px',
        padding: '7px 18px',
        cursor: 'pointer',
        fontWeight: 'bold',
        fontSize: '13px',
    }
};

export default Acumulado;

function gastoActivo(gasto) {
    const backendStatus = String(gasto.backendStatus || gasto.backend_status || '').toLowerCase();
    const status = String(gasto.status || '').toLowerCase();
    const autorizacion = String(gasto.autorizacion || '').toLowerCase();
    return (
        backendStatus !== 'removed'
        && backendStatus !== 'rejected'
        && status !== 'removed'
        && status !== 'eliminado'
        && status !== 'rejected'
        && status !== 'no autorizado'
        && autorizacion !== 'no_autorizado'
    );
}

function valorFiscalOculto(value) {
    if (value === null || value === undefined || value === '') return null;
    const numero = Number(value);
    return Number.isNaN(numero) ? null : numero;
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

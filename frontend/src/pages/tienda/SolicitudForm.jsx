import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import Drawer from '../../components/shared/Drawer';
import { VISIBILIDAD, PUEDE_LEER_OBSERVACION } from '../../components/shared/roles';
import { combinarHistorialObservaciones, historialDesdeEventos, observacionInicialDesdeGasto } from '../../lib/observationHistory';

import {
    addExpenseObservation,
    getRequestObservationEvents,
    apiErrorMessage,
    createFrontendSolicitud,
    currentToken,
    deleteDraftExpense,
    executeRequestAction,
    getFrontendContext,
    getFrontendSolicitud,
    parseCfdi,
    uploadExpenseAttachment,
    validateExpenseCfdi,
} from '../../lib/api';

import {
    clearDraftGastos,
    loadDraftGastos,
    loadDraftRequest,
    removeDraftGasto,
    replaceDraftGastos,
    saveDraftRequest,
    updateDraftGasto,
} from '../../lib/draftSolicitud';

const DATOS_INICIALES = {
    fecha: new Date().toLocaleDateString('es-MX', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
    }),
    tienda: 'V000',
    gerente: 'Por especificar',
    cuentaBancaria: 'Por especificar',
    estadoRegion: 'Por especificar',
    plaza: '',
};


function historialBorradorDesdeGastos(gastos = []) {
    return gastos
        .flatMap((gasto) => {
            const gastoId = gastoHistorialId(gasto);
            const historialGuardado = Array.isArray(gasto.observacionesHistorial)
                ? gasto.observacionesHistorial
                : [];

            if (historialGuardado.length > 0) {
                return historialGuardado.map((obs) => normalizarObservacionBorrador(obs, gastoId));
            }

            const inicial = observacionInicialDesdeGasto(gasto);
            return inicial ? [inicial] : [];
        })
        .filter(Boolean)
        .sort((a, b) => a.fechaTimestamp - b.fechaTimestamp);
}

function normalizarObservacionBorrador(obs, gastoId) {
    const idOriginal = String(obs.id || '');
    const idNormalizado = idOriginal.startsWith('local-') && !idOriginal.startsWith('local-obs-')
        ? idOriginal.replace(/^local-/, 'local-obs-')
        : idOriginal;

    return {
        ...obs,
        id: idNormalizado || `local-obs-${gastoId || 'gasto'}-${obs.fechaTimestamp || 0}`,
        gastoId: obs.gastoId ?? gastoId,
        fechaTimestamp: Number(obs.fechaTimestamp || 0),
        visibilidad: obs.visibilidad || VISIBILIDAD.PUBLIC,
    };
}

function crearObservacionLocal(gastoId, rol, textoObservacion) {
    const fechaCreacion = new Date();
    const timestamp = fechaCreacion.getTime();

    return {
        id: `local-obs-${gastoId || 'gasto'}-${timestamp}`,
        gastoId,
        autor: rol.toUpperCase(),
        rol,
        texto: textoObservacion,
        fecha: fechaCreacion.toLocaleString(),
        fechaTimestamp: timestamp,
        visibilidad: VISIBILIDAD.PUBLIC,
    };
}

function agregarObservacionLocalAGasto(gasto, gastoId, rol, observacion) {
    if (!idsIguales(gastoHistorialId(gasto), gastoId)) return gasto;

    const historialExistente = Array.isArray(gasto.observacionesHistorial)
        ? gasto.observacionesHistorial.map((obs) => normalizarObservacionBorrador(obs, gastoId))
        : [];
    const observacionInicial = historialExistente.length === 0
        ? observacionInicialDesdeGasto(gasto)
        : null;
    const obsPrevia = gasto.observaciones || gasto.observacion || '';
    const obsNueva = obsPrevia
        ? `${obsPrevia} | [${rol.toUpperCase()}]: ${observacion.texto}`
        : observacion.texto;

    return {
        ...gasto,
        observaciones: obsNueva,
        observacion: obsNueva,
        observacionesHistorial: [
            ...(observacionInicial ? [observacionInicial] : []),
            ...historialExistente,
            observacion,
        ],
    };
}

function observacionesHistorialParaBackend(gasto) {
    return historialBorradorDesdeGastos([gasto]).map((observacion) => ({
        texto: observacion.texto,
        rol: observacion.rol,
        autor: observacion.autor,
        fechaTimestamp: observacion.fechaTimestamp,
        visibilidad: observacion.visibilidad,
    }));
}


function SolicitudForm({ currentRole }) {
    const navigate = useNavigate();
    const location = useLocation();
    const [datosIniciales, setDatosIniciales] = useState(DATOS_INICIALES);
    const [enviando, setEnviando] = useState(false);
    const [borrandoGastoId, setBorrandoGastoId] = useState(null);

    // 2. ESTADOS PARA LA LISTA DE GASTOS Y FORMULARIO
    const [gastos, setGastos] = useState(() => loadDraftGastos());

    const solicitudBackendId = location.state?.solicitudBackendId || null;
    const observationRequestId = solicitudBackendId || loadDraftRequest()?.backendId || null;

    // 1. ESTADOS PARA CONTROLAR LOS PANELES Y OBSERVACIONES
        const [documentoActivo, setDocumentoActivo] = useState(null); // 'factura' | 'vale' | null
        const [observacionesAbiertas, setObservacionesAbiertas] = useState(false);
        const [gastoSeleccionado, setGastoSeleccionado] = useState(null);
    
        // Estado del chat de observaciones
        const [comentario, setComentario] = useState('');
        const [errorHistorial, setErrorHistorial] = useState('');
        const [historial, setHistorial] = useState(() => historialBorradorDesdeGastos(loadDraftGastos()));
    
        // 2. NORMALIZAR EL ROL
        const rol = String(currentRole || localStorage.getItem('currentRole') || 'admin').toLowerCase().trim();
    
    useEffect(() => {
        if (!currentToken()) {
            navigate('/login');
            return;
        }

        let activo = true;
        getFrontendContext()
            .then((contexto) => {
                if (!activo) return;
                setDatosIniciales({
                    fecha: DATOS_INICIALES.fecha,
                    tienda: contexto.tienda || DATOS_INICIALES.tienda,
                    gerente: contexto.gerente || DATOS_INICIALES.gerente,
                    cuentaBancaria: contexto.cuentaBancaria || DATOS_INICIALES.cuentaBancaria,
                    estadoRegion: contexto.estadoRegion || DATOS_INICIALES.estadoRegion,
                });
            })
            .catch(() => {
                if (activo) setDatosIniciales(DATOS_INICIALES);
            });

        return () => {
            activo = false;
        };
    }, [currentRole, navigate]);

    // Calcular el TOTAL dinámicamente basándose en la lista actual
    const calcularTotal = () => {
        return gastos
            .filter(gastoEnviableEnSolicitud)
            .reduce((sum, item) => sum + Number(item.monto || 0), 0)
            .toFixed(2);
    };

    const handleEnviarSolicitud = async () => {
        const borradorBackend = loadDraftRequest();
        const gastosActivos = gastos.filter(gastoEnviableEnSolicitud);

        if (gastosActivos.length === 0 && !borradorBackend?.backendId) {
            alert("Debes añadir al menos un gasto antes de enviar.");
            return;
        }

        const errorEvidencia = borradorBackend?.backendId
            ? null
            : validarEvidenciaAntesDeEnviar(gastosActivos);
        if (errorEvidencia) {
            alert(errorEvidencia);
            return;
        }

        setEnviando(true);

        try {
            if (borradorBackend?.backendId) {
                const solicitudBorrador = await getFrontendSolicitud(borradorBackend.backendId);
                const gastosBackendActivos = (solicitudBorrador.gastos || []).filter(gastoActivoEnBorrador);
                if (!gastosBackendActivos.length) {
                    throw new Error('El borrador no tiene gastos guardados.');
                }

                await executeRequestAction(solicitudBorrador.backendId, 'submit_request');
                const solicitudActualizada = await getFrontendSolicitud(solicitudBorrador.backendId);

                clearDraftGastos();
                localStorage.setItem('bandejaSolicitudes', JSON.stringify([solicitudActualizada]));

                alert(`¡Solicitud ${solicitudActualizada.id} enviada con éxito!`);
                navigate('/bandeja', { state: { solicitud: solicitudActualizada } });
                return;
            }

            await validarCfdisAntesDeCrearSolicitud(gastosActivos);

            const nuevaSolicitud = await createFrontendSolicitud({
                tienda: datosIniciales.tienda,
                montoTotal: calcularTotal(),
                gastos: gastosActivos.map((gasto) => ({
                    fecha: gasto.fecha,
                    categoria: gasto.tipo || gasto.type,
                    monto: String(gasto.monto),
                    folio: folioManual(gasto.folio),
                    cfdiUuid: gasto.cfdiUuid || null,
                    cfdiSubtotal: valorFiscalOculto(gasto.cfdiSubtotal),
                    cfdiTotal: valorFiscalOculto(gasto.cfdiTotal),
                    cfdiTaxAmount: valorFiscalOculto(gasto.cfdiTaxAmount),
                    cfdiTaxRate: valorFiscalOculto(gasto.cfdiTaxRate),
                    cfdiCurrency: gasto.cfdiCurrency || null,
                    observaciones: gasto.observaciones || null,
                    observacionesHistorial: observacionesHistorialParaBackend(gasto),
                    requiresAuthorization: Boolean(gasto.requiresAuthorization),
                    authorizationArea: (
                        gasto.areaAutoriza
                        || gasto.authorizationArea
                        || gasto.authorization_area
                        || null
                    ),
                })),
            });

            await subirArchivosPendientes(nuevaSolicitud, gastosActivos);
            await executeRequestAction(nuevaSolicitud.backendId, 'submit_request');
            const solicitudActualizada = await getFrontendSolicitud(nuevaSolicitud.backendId);

            clearDraftGastos();
            localStorage.setItem('bandejaSolicitudes', JSON.stringify([solicitudActualizada]));

            alert(`¡Solicitud ${solicitudActualizada.id} enviada con éxito!`);
            navigate('/bandeja', { state: { solicitud: solicitudActualizada } });
        } catch (error) {
            alert(apiErrorMessage(error));
        } finally {
            setEnviando(false);
        }

    };


    useEffect(() => {
        if (solicitudBackendId || !currentToken()) return undefined;

        const borradorBackend = loadDraftRequest();
        if (!borradorBackend?.backendId) return undefined;

        let activo = true;

        getFrontendSolicitud(borradorBackend.backendId)
            .then((solicitud) => {
                if (!activo) return;

                const backendStatus = solicitud.backendStatus || solicitud.backend_status;
                if (!['draft', 'correction_required'].includes(backendStatus)) {
                    clearDraftGastos();
                    setGastos([]);
                    setHistorial([]);
                    return;
                }

                const gastosBackend = (solicitud.gastos || []).filter(gastoActivoEnBorrador);
                saveDraftRequest(solicitud);
                replaceDraftGastos(gastosBackend);
                setGastos(gastosBackend);
                setHistorial((actual) => combinarHistorialObservaciones(historialBorradorDesdeGastos(gastosBackend), actual));
            })
            .catch((error) => {
                console.error('No se pudo restaurar el borrador guardado', error);
            });

        return () => {
            activo = false;
        };
    }, [solicitudBackendId]);


    useEffect(() => {
        if (!observationRequestId) {
            return undefined;
        }

        let activo = true;

        // 1. Extraemos las notas iniciales de la lista de gastos
        const obsIniciales = (gastos || [])
            .map(observacionInicialDesdeGasto)
            .filter(Boolean);

        getRequestObservationEvents(observationRequestId)
            .then((eventos) => {

                if (activo) {
                    // 1. Mapeamos las observaciones que vienen del backend o eventos
                    const obsEventos = historialDesdeEventos(eventos || []);

                    // 3. Unificamos descartando posibles duplicados y ordenamos por fecha
                    const historialCompleto = combinarHistorialObservaciones(obsIniciales, obsEventos);

                    setHistorial(historialCompleto);
                    setErrorHistorial('');
                    //setHistorial(historialDesdeEventos(eventos));
                }
            })
            .catch((error) => {
                if (activo) {
                    setHistorial((actual) => combinarHistorialObservaciones(obsIniciales, actual));
                    setErrorHistorial('No se pudieron actualizar las observaciones. Se conserva el historial cargado.');
                }
                console.error('No se pudieron cargar las observaciones', error);
            });

        return () => {
            activo = false;
        };
    }, [observationRequestId, gastos]);
    
    
    const refrescarHistorialBackend = async (requestId = observationRequestId) => {
        if (!requestId) return;
        try {
            const eventos = await getRequestObservationEvents(requestId);
            const obsIniciales = (gastos || []).map(observacionInicialDesdeGasto).filter(Boolean);
            setHistorial(combinarHistorialObservaciones(obsIniciales, historialDesdeEventos(eventos)));
            setErrorHistorial('');
        } catch {
            setErrorHistorial('No se pudieron actualizar las observaciones. Se conserva el historial cargado.');
        }
    };


    // HANDLERS PARA ABRIR Y CERRAR PANELES
    const handleVerDocumento = (gasto) => {
        setGastoSeleccionado(gasto);
        setDocumentoActivo('documento');
    };

    const handleToggleObservaciones = (gasto) => {
        setGastoSeleccionado(gasto);
        setObservacionesAbiertas(!observacionesAbiertas);
    };

    const handleEliminarGasto = async (gasto) => {
        const gastoId = gastoHistorialId(gasto);
        if (!gastoId) return;

        const nombreGasto = gasto.nombre || gasto.tipo || gasto.type || 'este gasto';
        const confirmar = window.confirm(`¿Eliminar ${nombreGasto} de la solicitud?`);
        if (!confirmar) return;

        setBorrandoGastoId(gastoId);

        try {
            const backendId = gasto.backendId || gasto.backend_id;
            const borradorBackend = loadDraftRequest();
            if (backendId && borradorBackend?.backendId) {
                await deleteDraftExpense(borradorBackend.backendId, backendId);
            }

            const gastosActualizados = removeDraftGasto(gastoId).filter(gastoActivoEnBorrador);
            setGastos(gastosActualizados);
            setHistorial(historialBorradorDesdeGastos(gastosActualizados));

            if (idsIguales(gastoHistorialId(gastoSeleccionado), gastoId)) {
                setGastoSeleccionado(null);
                setDocumentoActivo(null);
                setObservacionesAbiertas(false);
            }
        } catch (error) {
            alert(apiErrorMessage(error));
        } finally {
            setBorrandoGastoId(null);
        }
    };

    const handleEnviarObservacion = async (e) => {
        e.preventDefault();
        const textoObservacion = comentario.trim();
        if (!textoObservacion || !gastoSeleccionado) return;

        const expenseId = gastoSeleccionado.backendId || gastoSeleccionado.id;
        const draftBackendId = loadDraftRequest()?.backendId || null;
        const requestIdParaObservacion = solicitudBackendId || draftBackendId;
        if (requestIdParaObservacion && (!expenseId || typeof expenseId !== 'string')) {
            alert('Este gasto no tiene ID de backend para guardar la observación.');
            return;
        }
                
        const currentGastoId = gastoHistorialId(gastoSeleccionado); // 👈 Asigna el ID del gasto activo
        const nueva = crearObservacionLocal(currentGastoId, rol, textoObservacion);

        console.log("➡️ 1. Intentando añadir nueva observación:", nueva);

        try {
            if (requestIdParaObservacion) {
                await addExpenseObservation(expenseId, textoObservacion);
                await refrescarHistorialBackend(requestIdParaObservacion);
            } else {
                // 2. ACTUALIZAMOS EL OBJETO GASTO EN 'gastos'
                // Concatenamos las observaciones para que al enviar la solicitud no se pierdan
                const actualizarGasto = (g) => agregarObservacionLocalAGasto(g, currentGastoId, rol, nueva);
                const gastosActualizados = gastos.map(actualizarGasto);
                setGastos(gastosActualizados);
                setHistorial(historialBorradorDesdeGastos(gastosActualizados));
                updateDraftGasto(currentGastoId, actualizarGasto);
            }
            setComentario('');
        } catch (error) {
            alert(apiErrorMessage(error));
        }
    };
    
    
    const auditRequestId = solicitudBackendId || loadDraftRequest()?.backendId || null;

    return (
        <div style={styles.mainLayout} data-audit-request-id={auditRequestId || undefined}>
            <div style={styles.container}>
            
            {/* TÍTULO Y BOTÓN DE AÑADIR */}
            <div style={styles.titleRow}>
                <h2 style={styles.mainTitle}>Solicitud de Reembolso</h2>
                <button 
                style={styles.añadirBtn} 
                onClick={() => {
                    navigate('/gasto/nuevo')
                    }
                }
                //onClick={() => setMostrarFormGasto(!mostrarFormGasto)}
                >
                Añadir Gasto
                </button>
            </div>

            {/* BLOQUE DE DATOS AUTOCOMPLETADOS (Campos Fijos) */}
            <div style={styles.gridAuto}>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Fecha</label>
                <div style={styles.disabledInput}>{datosIniciales.fecha}</div>
                </div>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Tienda</label>
                <div style={styles.disabledInput}>{datosIniciales.tienda}</div>
                </div>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Gerente</label>
                <div style={styles.disabledInput}>{datosIniciales.gerente}</div>
                </div>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Cuenta bancaria</label>
                <div style={styles.disabledInput}>{datosIniciales.cuentaBancaria}</div>
                </div>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Plaza</label>
                <div style={styles.disabledInput}>{datosIniciales.estadoRegion}</div>
                </div>
            </div>


            {/* TABLA / LISTADO DE GASTOS AGREGADOS */}
            <div style={styles.tableContainer}>
                {/* ENCABEZADOS DE LA TABLA */}
                <div style={styles.tableHeader}>
                    <span style={{ flex: 1.5, textAlign: 'left', fontWeight: 'bold' }}>CONCEPTO</span>
                    <span style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>MONTO</span>
                    <span style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>TIPO DE GASTO</span>
                    <span style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>HERRAMIENTAS</span>
                </div>

                {/* FILAS DE GASTOS */}
                {gastos.filter(gastoActivoEnBorrador).map((gasto) => {
                    const gastoId = gastoHistorialId(gasto);
                    const borrandoEsteGasto = idsIguales(borrandoGastoId, gastoId);
                    return (
                        <div
                            key={gasto.id}
                            style={styles.tableRow}
                            data-audit-expense-id={gasto.backendId || undefined}
                        >
                            {/* 1. CONCEPTO (flex: 2) */}
                            <span style={{ flex: 1.5, textAlign: 'left', fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {gasto.nombre}
                            </span>

                            {/* 2. MONTO (flex: 1) */}
                            <span style={{ flex: 1.5, textAlign: 'center' }}>
                                $ {Number(gasto.monto || 0).toFixed(2)}
                            </span>

                            {/* 3. TIPO DE GASTO (flex: 1.5) */}
                            <span style={{ flex: 1.5, textAlign: 'center' }}>
                                {gasto.type || gasto.tipo}
                            </span>

                            {/* 4. HERRAMIENTAS (flex: 1.5) */}
                            <div style={{ ...styles.herramientasContainer, flex: 1.5, display: 'flex', justifyContent: 'center', gap: '8px' }}>
                                <button style={styles.iconBtn} title="Ver Documento" onClick={() => handleVerDocumento(gasto)}>
                                    <img src="/Factura.png" alt="Documento" style={styles.iconImg} />
                                </button>

                                <button style={styles.iconBtn} title="Observaciones" onClick={() => handleToggleObservaciones(gasto)}>
                                    <img src="/Observacion.png" alt="Observaciones" style={styles.iconImg} />
                                </button>

                                <button
                                    type="button"
                                    style={{
                                        ...styles.iconBtn,
                                        opacity: borrandoEsteGasto || enviando ? 0.5 : 1,
                                        cursor: borrandoEsteGasto || enviando ? 'not-allowed' : 'pointer',
                                    }}
                                    title="Eliminar gasto"
                                    aria-label="Eliminar gasto"
                                    disabled={borrandoEsteGasto || enviando}
                                    onClick={() => handleEliminarGasto(gasto)}
                                >
                                    <img src="/Eliminar.png" alt="Eliminar" style={styles.iconImg} />
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* FOOTER DE TOTALES */}
            <div style={styles.totalRow}>
                {/* CONCEPTO (flex: 2) -> Mantiene la etiqueta alineada como en la columna de nombres */}
                <span style={{ flex: 1.5, textAlign: 'left', fontWeight: 'bold', fontSize: '15px' }}>
                    TOTAL : 
                </span>

                {/* MONTO (flex: 1) -> Coincide exactamente abajo de los importes de la tabla */}
                <span style={{ flex: 2, textAlign: 'center', fontWeight: 'bold', fontSize: '15px' }}>
                    ${calcularTotal()}
                </span>

                {/* TIPO DE GASTO (flex: 1.5) -> Espacio vacío para rellenar */}
                <span style={{ flex: 1 }}></span>

                {/* TIPO DE GASTO (flex: 1.5) -> Espacio vacío para rellenar */}
                <span style={{ flex: 1.5 }}></span>
            </div>

        

            {/* BARRA FIJA INFERIOR (Solo para esta pantalla) */}
            <div style={{...styles.fixedStickyFooter, 
                right: (documentoActivo && observacionesAbiertas) ? '850px' 
                    : (documentoActivo || observacionesAbiertas) ? '350px' 
                    : 0
            }}>
                <button
                    onClick={handleEnviarSolicitud}
                    style={styles.enviarSolicitudBtnFixed}
                    disabled={enviando}
                >
                {enviando ? 'Enviando...' : 'Enviar Solicitud'}
                </button>
            </div>

            </div>

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
                errorObservaciones={errorHistorial}
                onReintentarObservaciones={() => refrescarHistorialBackend()}
                auditRequestId={auditRequestId}
                auditExpenseId={gastoSeleccionado?.backendId}
            />
        </div>
    );
    }

async function subirArchivosPendientes(nuevaSolicitud, gastosOriginales) {
    const gastosBackend = nuevaSolicitud.gastos || [];
    for (const [index, gasto] of gastosOriginales.entries()) {
        const gastoBackend = gastosBackend[index];
        if (!gastoBackend?.backendId) continue;

        if (gasto.valeFile) {
            await uploadExpenseAttachment(gastoBackend.backendId, gasto.valeFile, 'other');
        }

        if (gasto.reciboFile) {
            await uploadExpenseAttachment(gastoBackend.backendId, gasto.reciboFile, 'receipt');
        }

        if (gasto.facturaFile) {
            if (esXml(gasto.facturaFile)) {
                const resultado = await validateExpenseCfdi(gastoBackend.backendId, gasto.facturaFile);
                if (!resultado.is_valid) {
                    throw new Error(mensajeCfdiInvalido(gasto, resultado));
                }
            } else {
                await uploadExpenseAttachment(gastoBackend.backendId, gasto.facturaFile, 'receipt', {
                    ocrPreviewToken: gasto.ocrPreviewToken,
                });
            }
        }
    }
}

async function validarCfdisAntesDeCrearSolicitud(gastos) {
    for (const gasto of gastos) {
        if (!gasto.facturaFile || !esXml(gasto.facturaFile)) continue;

        const parsed = await parseCfdi(gasto.facturaFile);
        const errores = [];
        const montoGasto = Number(gasto.monto);
        const totalCfdi = parsed.total === null || parsed.total === undefined ? null : Number(parsed.total);

        if (!parsed.uuid) {
            errores.push('La factura no trae UUID fiscal.');
        }

        if (totalCfdi === null || Number.isNaN(totalCfdi)) {
            errores.push('La factura no trae total fiscal.');
        } else if (redondearMonto(totalCfdi) !== redondearMonto(montoGasto)) {
            errores.push(`El total de la factura (${formatoMonto(totalCfdi)}) no coincide con el monto del gasto (${formatoMonto(montoGasto)}).`);
        }

        if (parsed.currency && parsed.currency.toUpperCase() !== 'MXN') {
            errores.push(`La moneda de la factura es ${parsed.currency}, pero el gasto se enviará como MXN.`);
        }

        if (errores.length) {
            throw new Error([
                `La factura del gasto "${gasto.nombre}" no coincide con el gasto capturado:`,
                ...errores,
            ].join('\n'));
        }
    }
}

function validarEvidenciaAntesDeEnviar(gastos) {
    const sinComprobante = gastos.filter((gasto) => {
        if (gasto.tipoDocumento === 'vale') return !gasto.valeFile || !esPdf(gasto.valeFile);
        if (gasto.tipoDocumento === 'recibo') return !gasto.reciboFile || !esPdf(gasto.reciboFile);
        return !gasto.facturaFile || (!esXml(gasto.facturaFile) && !esPdf(gasto.facturaFile));
    });
    const pdfSinOcr = gastos.filter(
        (gasto) => gasto.tipoDocumento === 'factura'
            && gasto.facturaFile
            && esPdf(gasto.facturaFile)
            && !gasto.ocrPreviewToken,
    );

    if (sinComprobante.length) {
        return [
            'Antes de enviar, cada gasto debe tener su comprobante.',
            `Falta comprobante válido en ${sinComprobante.length} gasto(s).`,
        ].filter(Boolean).join('\n');
    }
    if (pdfSinOcr.length) {
        return [
            'Antes de enviar, cada factura PDF debe validarse con OCR.',
            `Falta validar OCR en ${pdfSinOcr.length} gasto(s).`,
        ].join('\n');
    }
    return null;
}

function esXml(file) {
    const nombre = file?.name?.toLowerCase() || '';
    const tipo = file?.type?.toLowerCase() || '';
    return nombre.endsWith('.xml') || tipo.includes('xml');
}

function esPdf(file) {
    const nombre = file?.name?.toLowerCase() || '';
    const tipo = file?.type?.toLowerCase() || '';
    return nombre.endsWith('.pdf') || tipo === 'application/pdf';
}

function mensajeCfdiInvalido(gasto, resultado) {
    const errores = (resultado.issues || [])
        .filter((issue) => issue.severity !== 'warning')
        .map((issue) => issue.message);

    return [
        `La factura del gasto "${gasto.nombre}" no es válida.`,
        errores.length ? errores.join('\n') : 'Revisa que el total, moneda, UUID y RFC coincidan.',
    ].join('\n');
}

function redondearMonto(value) {
    return Number(value || 0).toFixed(2);
}

function formatoMonto(value) {
    return `$${redondearMonto(value)}`;
}

function valorFiscalOculto(value) {
    if (value === null || value === undefined || value === '') return null;
    const numero = Number(value);
    return Number.isNaN(numero) ? null : numero;
}

function folioManual(folio) {
    if (!folio || folio === 'OCR pendiente' || folio === '5FB2822E-396D-4725-8521-CDC4BDD20CCF') return null;
    return folio;
}

// 🎨 ESTILOS INTEGRADOS CON TU INDEX.CSS
const styles = {
    // Layout principal en horizontal
    mainLayout: {
        display: 'flex',
        width: '100%',
        height: 'calc(100vh - 180px)', 
        padding: 0,
        overflow: 'hidden',
        margin: '0px',
    },

    container: {
        width: '100%',
        height: '91%',
        margin: '0 auto',
        padding: '20px 20px 20px 20px',
        textAlign: 'left',
        flex: 1,
        minWidth: 0, // CRUCIAL: Permite que la tabla se reduzca sin salirse de la pantalla
        display: 'flex',
        flexDirection: 'column',
        overflowY: 'auto',
        position: 'relative',
    },
    titleRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '30px',
    },
    mainTitle: {
        margin: 0,
        fontSize: '24px',
    },
    añadirBtn: {
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text-WBtn)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '20px',
        padding: '8px 24px',
        fontSize: '13px',
        fontWeight: '700',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
        transition: 'transform 0.1s',
    },
    gridAuto: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '10px',
        marginBottom: '40px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '5px',
    },
    label: {
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
        textAlign: 'center',
    },
    disabledInput: {
        backgroundColor: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '14px',
        textAlign: 'center',
        color: 'var(--text)',
    },
    manualForm: {
        backgroundColor: 'var(--sb-subhead)',
        border: '1px dashed var(--border)',
        borderRadius: '12px',
        padding: '10px',
        marginBottom: '30px',
        boxShadow: 'var(--shadow)',
    },
    subTitle: {
        margin: '0 0 15px 0',
        fontSize: '15px',
        color: 'var(--text-h)',
    },
    manualFormRow: {
        display: 'flex',
        gap: '20px',
        flexWrap: 'wrap',
    },
    manualInput: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '15px',
        width: '180px',
        textAlign: 'center',
        outline: 'none',
    },
    manualSelect: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '15px',
        width: '200px',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
        outline: 'none',
    },
    manualFormActions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '10px',
        marginTop: '15px',
    },
    tableContainer: {
        display: 'flex',
        width: '100%',
        flexDirection: 'column',
        gap: '12px',
        marginBottom: '20px',
    },
    tableHeader: {
        display: 'flex',
        padding: '0 10px',
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
        letterSpacing: '0.5px',
    },
    tableHeaderCell: {
        display: 'inline-block',
    },
    tableRow: {
        display: 'flex',
        alignItems: 'center',
        backgroundColor: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        padding: '9px 10px',
        fontSize: '13px',
    },
    verDetalleLink: {
        width: '100px',
        textAlign: 'right',
        color: 'var(--text-WBtn)',
        fontWeight: 'bold',
        cursor: 'pointer',
        fontSize: '13px',
        paddingRight: '18px',
    },

    herramientasContainer: {
        flex: 2,
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        gap: '20px'
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
        width: '18px',
        height: '18px',
        objectFit: 'contain'
    },

    totalRow: {
        display: 'flex',
        alignItems: 'left',
        gap: '270px',
        paddingLeft: '15px',
        marginBottom: '5px',
    },
    totalLabel: {
        fontWeight: 'bold',
        fontSize: '16px',
        color: 'var(--text-h)',
    },
    totalAmount: {
        fontWeight: 'bold',
        fontSize: '16px',
        color: 'var(--text-h)',
    },

    fixedStickyFooter: {
        position: 'fixed',
        bottom: 0,
        left: 0,
        backgroundColor: 'var(--sb-subhead)', /* Usa el fondo blanco de tu index.css */
        boxShadow: '0 -4px 10px rgba(0, 0, 0, 0.05)', /* Una sombra sutil hacia arriba para separarlo del contenido */
        padding: '12px 0',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 1000, /* Se asegura de quedar por encima de las filas de los gastos */
        borderTop: '1px solid #fff0f0',
        
    },
    enviarSolicitudBtnFixed: {
        backgroundColor: 'var(--sb-sendBtnBg)',
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '10px',
        padding: '10px 25px', /* Un poco más ancho para que destaque en la barra inferior */
        marginBottom: '8px',
        fontSize: '16px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
        transition: 'transform 0.1s ease',
    }
};

export default SolicitudForm;



function gastoHistorialId(gasto) {
    return gasto?.backendId ?? gasto?.backend_id ?? gasto?.id ?? null;
}

function idsIguales(uno, dos) {
    if (uno === null || uno === undefined || dos === null || dos === undefined) return false;
    return String(uno) === String(dos);
}

function gastoActivoEnBorrador(gasto) {
    if (!gasto) return false;
    if (gasto.deletedAt || gasto.deleted_at || gasto.removedAt || gasto.removed_at) return false;

    const estado = String(gasto.backendStatus || gasto.backend_status || gasto.status || gasto.estado || '')
        .toLowerCase()
        .trim();
    return !['deleted', 'removed', 'rejected', 'eliminado', 'no autorizado', 'no_autorizado'].includes(estado);
}

function gastoEnviableEnSolicitud(gasto) {
    return gastoActivoEnBorrador(gasto) && Number(gasto.monto || 0) > 0;
}

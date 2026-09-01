import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import Drawer from '../../components/shared/Drawer';
import { VISIBILIDAD, PUEDE_LEER_OBSERVACION } from '../../components/shared/roles';

import {
    addExpenseObservation,
    getRequestAuditEvents,
    apiErrorMessage,
    createFrontendSolicitud,
    currentToken,
    executeRequestAction,
    getFrontendContext,
    getFrontendSolicitud,
    parseCfdi,
    uploadExpenseAttachment,
    validateExpenseCfdi,
} from '../../lib/api';

import { clearDraftGastos, loadDraftGastos } from '../../lib/draftSolicitud';

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


function SolicitudForm({ currentRole }) {
    const navigate = useNavigate();
    const location = useLocation();
    const [datosIniciales, setDatosIniciales] = useState(DATOS_INICIALES);
    const [enviando, setEnviando] = useState(false);

    // 2. ESTADOS PARA LA LISTA DE GASTOS Y FORMULARIO
    const [gastos, setGastos] = useState(() => loadDraftGastos());

    const solicitudBackendId = location.state?.solicitudBackendId || null;

    // 1. ESTADOS PARA CONTROLAR LOS PANELES Y OBSERVACIONES
        const [documentoActivo, setDocumentoActivo] = useState(null); // 'factura' | 'vale' | null
        const [observacionesAbiertas, setObservacionesAbiertas] = useState(false);
        const [gastoSeleccionado, setGastoSeleccionado] = useState(null);
    
        // Estado del chat de observaciones
        const [comentario, setComentario] = useState('');
        const [historial, setHistorial] = useState([]);
    
        // 2. NORMALIZAR EL ROL
        const rol = String(currentRole || localStorage.getItem('currentRole') || 'admin').toLowerCase().trim();
    
        // Mock por si ingresas directo sin state
        const [gastosDesglosados] = useState([]);


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
        return gastos.reduce((sum, item) => sum + item.monto, 0).toFixed(2);
    };

    const handleEnviarSolicitud = async () => {
        if (gastos.length === 0) {
            alert("Debes añadir al menos un gasto antes de enviar.");
            return;
        }

        const errorEvidencia = validarEvidenciaAntesDeEnviar(gastos);
        if (errorEvidencia) {
            alert(errorEvidencia);
            return;
        }

        setEnviando(true);

        try {
            await validarCfdisAntesDeCrearSolicitud(gastos);

            const nuevaSolicitud = await createFrontendSolicitud({
                tienda: datosIniciales.tienda,
                montoTotal: calcularTotal(),
                gastos: gastos.map((gasto) => ({
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
                    requiresAuthorization: Boolean(gasto.requiresAuthorization),
                })),
            });

            await subirArchivosPendientes(nuevaSolicitud, gastos);
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
        let activo = true;

        // 1. Extraemos las notas iniciales de la lista de gastos
        // Revisa 'gastos' (borrador local) y 'gastosDesglosados'
        const listaGastos = solicitudBackendId ? gastosDesglosados : gastos;
        const obsIniciales = (listaGastos || [])
            .map(observacionInicialDesdeGasto)
            .filter(Boolean);

        console.log("Observaciones Iniciales: ", obsIniciales)

        // Si es un borrador (modo creación sin backendId)
        if (!solicitudBackendId) {
            if (activo) {
                // Unimos las iniciales con las agregadas en esta sesión evitando duplicados por ID
                ////setHistorial((prevHistorial) => {
                   // const map = new Map();
                    // Agregar iniciales
                   // obsIniciales.forEach(item => map.set(item.id, item));
                    // Conservar las agregadas manualmente desde la interfaz
                   // prevHistorial.forEach(item => map.set(item.id, item));
                   // return Array.from(map.values());
                
                setHistorial((prevHistorial) => {
                // Mantenemos solo las observaciones creadas localmente desde SolicitudForm 
                // y las combinamos con las iniciales de los gastos
                const obsLocalesNuevas = prevHistorial.filter((obs) => String(obs.id).startsWith('local-obs-'));

                // Evitamos duplicar observaciones iniciales
                const map = new Map();
                obsIniciales.forEach((item) => map.set(item.id, item));
                obsLocalesNuevas.forEach((item) => map.set(item.id, item));

                const resultado = Array.from(map.values());
                console.log("🔄 [useEffect] Historial recalculado:", resultado);
                return resultado;
            });
        }
            return undefined;
    }
        

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
    }, [solicitudBackendId, gastos]);
    
    
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

        const expenseId = gastoSeleccionado.backendId || gastoSeleccionado.id;
        if (solicitudBackendId && (!expenseId || typeof expenseId !== 'string')) {
            alert('Este gasto no tiene ID de backend para guardar la observación.');
            return;
        }
                
        
        const currentGastoId = gastoHistorialId(gastoSeleccionado); // 👈 Asigna el ID del gasto activo
        
        const nueva = {
            id: `local-${currentGastoId || 'gasto'}-${Date.now()}`,
            gastoId: currentGastoId,
            autor: rol.toUpperCase(),
            rol,
            texto: textoObservacion,
            fecha: new Date().toLocaleString(),
            fechaTimestamp: Date.now(),
            visibilidad: VISIBILIDAD.PUBLIC,
        };

        console.log("➡️ 1. Intentando añadir nueva observación:", nueva);

        try {
            if (solicitudBackendId) {
                await addExpenseObservation(expenseId, textoObservacion);
                await refrescarHistorialBackend();
            } else {
                // 1. Actualizamos el historial visible en pantalla
                setHistorial((prevHistorial) => [...prevHistorial, nueva]);

                // 2. ACTUALIZAMOS EL OBJETO GASTO EN 'gastos'
                // Concatenamos las observaciones para que al enviar la solicitud no se pierdan
                setGastos((prevGastos) =>
                    prevGastos.map((g) => {
                        if (idsIguales(gastoHistorialId(g), currentGastoId)) {
                            const obsPrevia = g.observaciones || g.observacion || '';
                            const obsNueva = obsPrevia 
                                ? `${obsPrevia} | [${rol.toUpperCase()}]: ${textoObservacion}`
                                : textoObservacion;
                            
                            return {
                                ...g,
                                observaciones: obsNueva,
                                observacion: obsNueva,
                            };
                        }
                        return g;
                    })
                );
            }
            setComentario('');
        } catch (error) {
            alert(apiErrorMessage(error));
        }
    };
    
    
    return (
        <div style={styles.mainLayout}>
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
                {gastos.map((gasto) => (
                    <div key={gasto.id} style={styles.tableRow}>
                        {/* 1. CONCEPTO (flex: 2) */}
                        <span style={{ flex: 1.5, textAlign: 'left', fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {gasto.nombre}
                        </span>
                        
                        {/* 2. MONTO (flex: 1) */}
                        <span style={{ flex: 1.5, textAlign: 'center' }}>
                            $ {gasto.monto.toFixed(2)}
                        </span>
                        
                        {/* 3. TIPO DE GASTO (flex: 1.5) */}
                        <span style={{ flex: 1.5, textAlign: 'center' }}>
                            {gasto.type || gasto.tipo}
                        </span>

                        {/* 4. HERRAMIENTAS (flex: 1.5) */}
                        <div style={{ ...styles.herramientasContainer, flex: 1.5, display: 'flex', justifyContent: 'center', gap: '8px' }}>
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
                right: (documentoActivo && observacionesAbiertas) ? '795px' 
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
            await uploadExpenseAttachment(gastoBackend.backendId, gasto.valeFile, 'receipt');
        }

        if (gasto.facturaFile) {
            if (esXml(gasto.facturaFile)) {
                const resultado = await validateExpenseCfdi(gastoBackend.backendId, gasto.facturaFile);
                if (!resultado.is_valid) {
                    throw new Error(mensajeCfdiInvalido(gasto, resultado));
                }
            } else {
                await uploadExpenseAttachment(gastoBackend.backendId, gasto.facturaFile, 'other');
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
            errores.push('El XML no trae UUID fiscal.');
        }

        if (totalCfdi === null || Number.isNaN(totalCfdi)) {
            errores.push('El XML no trae total fiscal.');
        } else if (redondearMonto(totalCfdi) !== redondearMonto(montoGasto)) {
            errores.push(`El total del XML (${formatoMonto(totalCfdi)}) no coincide con el monto del gasto (${formatoMonto(montoGasto)}).`);
        }

        if (parsed.currency && parsed.currency.toUpperCase() !== 'MXN') {
            errores.push(`La moneda del XML es ${parsed.currency}, pero el gasto se enviará como MXN.`);
        }

        if (errores.length) {
            throw new Error([
                `El CFDI XML del gasto "${gasto.nombre}" no coincide con el gasto capturado:`,
                ...errores,
            ].join('\n'));
        }
    }
}

function validarEvidenciaAntesDeEnviar(gastos) {
    const sinCfdi = gastos.filter((gasto) => !gasto.facturaFile || !esXml(gasto.facturaFile));

    if (sinCfdi.length) {
        return [
            'Antes de enviar, cada gasto debe tener CFDI XML.',
            sinCfdi.length ? `Falta CFDI XML válido en ${sinCfdi.length} gasto(s).` : '',
        ].filter(Boolean).join('\n');
    }
    return null;
}

function esXml(file) {
    const nombre = file?.name?.toLowerCase() || '';
    const tipo = file?.type?.toLowerCase() || '';
    return nombre.endsWith('.xml') || tipo.includes('xml');
}

function mensajeCfdiInvalido(gasto, resultado) {
    const errores = (resultado.issues || [])
        .filter((issue) => issue.severity !== 'warning')
        .map((issue) => issue.message);

    return [
        `El CFDI XML del gasto "${gasto.nombre}" no es válido.`,
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
    if (!folio || folio === '5FB2822E-396D-4725-8521-CDC4BDD20CCF') return null;
    return folio;
}

// 🎨 ESTILOS INTEGRADOS CON TU INDEX.CSS
const styles = {
    // Layout principal en horizontal
    mainLayout: {
        display: 'flex',
        width: '100%',
        height: 'calc(100vh - 140px)', 
        padding: 0,
        overflow: 'hidden',
        margin: 0,
    },

    container: {
        width: '100%',
        height: '100%',
        margin: '0 auto',
        padding: '20px 20px 0 20px',
        textAlign: 'left',
        flex: 1,
        minWidth: 0, // CRUCIAL: Permite que la tabla se reduzca sin salirse de la pantalla
        display: 'flex',
        flexDirection: 'column',
        paddingBottom: '0px',
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

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
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

function SolicitudForm({ currentRole }) {
    const navigate = useNavigate();
    const [datosIniciales, setDatosIniciales] = useState(DATOS_INICIALES);
    const [enviando, setEnviando] = useState(false);

    // 2. ESTADOS PARA LA LISTA DE GASTOS Y FORMULARIO
    const [gastos] = useState(() => loadDraftGastos());

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

    return (
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
            <div style={styles.tableHeader}>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'center', flex: 1 }}></span>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'right', width: '700px' }}>MONTO</span>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'center', width: '400px', paddingLeft: '100px'}}>TIPO DE GASTO</span>
            <span style={{ flex: 2, textAlign: 'right', paddingLeft: '60px' }}>HERRAMIENTAS</span>
            <span style={{ ...styles.tableHeaderCell, textAlign: 'center', width: '100px' }}></span>
            </div>

            {gastos.map((gasto) => (
            <div key={gasto.id} style={styles.tableRow}>
                <span style={{ fontWeight: 'bold', textAlign: 'left', flex: 1, paddingLeft: '20px' }}>{gasto.nombre}</span>
                <span style={{ textAlign: 'center', width: '200px', paddingLeft: '150px' }}>{gasto.monto.toFixed(2)}</span>
                <span style={{ textAlign: 'center', width: '280px'}}>{gasto.type || gasto.tipo}</span>
                
                <div style={styles.herramientasContainer}>
                    <button style={styles.iconBtn} title="Ver Vale">
                        <img src="/Vale.png" alt="Vale" style={styles.iconImg} />
                    </button>
                
                
                    <button style={styles.iconBtn} title="Ver Factura">
                        <img src="/Factura.png" alt="Factura" style={styles.iconImg} />
                    </button>
                
                
                    <button style={styles.iconBtn} title="Observaciones">
                        <img src="/Observacion.png" alt="Observaciones" style={styles.iconImg} />
                    </button>
                </div>
            </div>
            ))}
        </div>

        {/* FOOTER DE TOTALES */}
        <div style={styles.totalRow}>
            <span style={styles.totalLabel}>TOTAL :</span>
            <span style={styles.totalAmount}>$ {calcularTotal()}</span>
        </div>


        {/* BARRA FIJA INFERIOR (Solo para esta pantalla) */}
        <div style={styles.fixedStickyFooter}>
            <button
                onClick={handleEnviarSolicitud}
                style={styles.enviarSolicitudBtnFixed}
                disabled={enviando}
            >
            {enviando ? 'Enviando...' : 'Enviar Solicitud'}
            </button>
        </div>

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
    container: {
        maxWidth: '1000px',
        margin: '0 auto',
        padding: '20px',
        paddingBottom: '100px',
        textAlign: 'left',
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
        gap: '20px',
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
        paddingLeft: '30px',
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
        width: '100%',
        backgroundColor: 'var(--sb-subhead)', /* Usa el fondo blanco de tu index.css */
        boxShadow: '0 -4px 10px rgba(0, 0, 0, 0.05)', /* Una sombra sutil hacia arriba para separarlo del contenido */
        padding: '25px 0',
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

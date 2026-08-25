import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiErrorMessage, checkCfdiUuidAvailability, parseCfdi } from '../../lib/api';
import { addDraftGasto, loadDraftGastos } from '../../lib/draftSolicitud';

function AnadirGasto() {
    const navigate = useNavigate();

    // 1. ESTADOS DEL FORMULARIO
    const [fecha, setFecha] = useState(() => fechaHoyFormulario());
    const [categoria, setCategoria] = useState('Papelería');
    const [monto, setMonto] = useState('56.00');
    const [folio, setFolio] = useState('5FB2822E-396D-4725-8521-CDC4BDD20CCF');
    const [facturaFile, setFacturaFile] = useState(null);
    const [valeFile, setValeFile] = useState(null);
    const [observaciones, setObservaciones] = useState('');

    const [folioValidado, setFolioValidado] = useState(false);

    const handleValidarFolio = () => {
        if (!folio.trim()) return;
        setFolioValidado(true);
    };

    
    // Estados para simular la IA de Validación Automática
    const [estadoValidacion, setEstadoValidacion] = useState(null); // 'listo', 'error', 'legibilidad'
    const [cargandoValidacion, setCargandoValidacion] = useState(false);

    // Menú desplegable unificado para no perder coherencia
    const categoriasGasto = ["Agua", "Alimentos", "Artículos de Limpieza", "Bolsas", "Energía Eléctrica", "Equipo de Cómputo Menor", "Equipo Menor", "Extintores y Protección Civil", 
        "Hospedaje", "Impuesto Hospedaje", "Licencias y Permisos", "Medicamentos", "No Deducibles", "Papelería", "Paquetería y Mensajería", "Pasajes y taxis", "Publicidad", 
        "Recolección de Basura", "Servicio de Agua", "Trámites", "Trasportación", "Vigilancia", "Otros"];

    // 2. LÓGICA DE SIMULACIÓN DE IA
    const handleValidarGasto = async () => {
        const errorCfdi = validarCfdiXmlRequerido(facturaFile);
        if (errorCfdi) {
            alert(errorCfdi);
            return;
        }

        setCargandoValidacion(true);

        try {
            await validarCfdiAntesDeAnadir(facturaFile, monto, `Gasto - ${categoria}`);
            setEstadoValidacion('listo');
        } catch (error) {
            setEstadoValidacion('error');
            alert(apiErrorMessage(error));
        } finally {
            setCargandoValidacion(false);
        }
    };


    const handleGuardarGasto = async (e) => {
        e.preventDefault();

        const errorCfdi = validarCfdiXmlRequerido(facturaFile);
        if (errorCfdi) {
            alert(errorCfdi);
            return;
        }

        let cfdiParsed;
        try {
            cfdiParsed = await validarCfdiAntesDeAnadir(facturaFile, monto, `Gasto - ${categoria}`);
        } catch (error) {
            setEstadoValidacion('error');
            alert(apiErrorMessage(error));
            return;
        }

        // 1. Creamos el objeto con la misma estructura que espera tu lista
        const nuevoGastoItem = {
            id: Date.now(), // Un ID único usando el tiempo actual
            nombre: `Gasto - ${categoria}`,
            monto: parseFloat(monto) || 0,
            tipo: categoria,
            folio: folio,
            fecha: fecha,
            observaciones: observaciones,
            cfdiUuid: normalizarUuidLocal(cfdiParsed.uuid),
            cfdiSubtotal: numeroOculto(cfdiParsed.subtotal),
            cfdiTotal: cfdiParsed.total,
            cfdiCurrency: cfdiParsed.currency,
            cfdiTaxAmount: numeroOculto(cfdiParsed.tax_amount),
            cfdiTaxRate: numeroOculto(cfdiParsed.tax_rate),
            facturaFile: facturaFile,
            valeFile: valeFile,
        };

        alert("¡Gasto guardado exitosamente en la solicitud!");
        addDraftGasto(nuevoGastoItem);
        
        // 2. Pasamos el objeto dentro de la propiedad 'state' al regresar
        navigate('/solicitud/nueva');

    };


    return (
        <div style={styles.container}>
        
        {/* HEADER DE LA PÁGINA CON BOTÓN CANCELAR */}
        <div style={styles.topRow}>
            <h2 style={styles.mainTitle}>Añadir Gasto</h2>
            <button style={styles.cancelarBtn} onClick={() => navigate('/solicitud/nueva')}>
            Cancelar
            </button>
        </div>

        {/* DISEÑO EN DOS COLUMNAS (FORMULARIO E IA) */}
        <div style={styles.mainGrid}>
            
            {/* COLUMNA IZQUIERDA: FORMULARIO MANUAL */}
            <div style={styles.formColumn}>
            
            <div style={styles.formGrid}>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Fecha de la Factura *</label>
                <input type="text" value={fecha} onChange={(e) => setFecha(e.target.value)} style={styles.input} />
                </div>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Categoría *</label>
                <select value={categoria} onChange={(e) => setCategoria(e.target.value)} style={styles.select}>
                    {categoriasGasto.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                </select>
                </div>
                <div style={styles.inputGroup}>
                <label style={styles.label}>Monto *</label>
                <input type="number" value={monto} onChange={(e) => setMonto(e.target.value)} style={styles.input} />
                </div>




                {/* FOLIO FISCAL OCUPANDO AMBAS COLUMNAS CON BOTÓN DE CONFIRMACIÓN */}
                <div style={styles.inputGroupFull}>
                    <label style={styles.label}>Folio Fiscal *</label>
                    <div style={styles.inputWithButton}>
                        <input 
                            type="text" 
                            value={folio} 
                            onChange={(e) => {
                                setFolio(e.target.value);
                                setFolioValidado(false); // Resetea el estatus si el usuario edita el folio
                            }} 
                            placeholder="Ej. 12345678-ABCD-1234-ABCD-1234567890AB"
                            style={{
                                ...styles.input,
                                flex: 1, // Toma todo el espacio disponible
                                borderColor: folioValidado ? '#22c55e' : 'var(--border, #cbd5e1)'
                            }} 
                        />
                        <button 
                            type="button" 
                            onClick={handleValidarFolio}
                            style={{
                                ...styles.btnValidar,
                                backgroundColor: folioValidado ? '#22c55e' : 'var(--sb-sendBtnBg, #2563eb)'
                            }}
                        >
                            {folioValidado ? '✓ Confirmado' : 'Confirmar'}
                        </button>
                    </div>
                </div>
            </div>

            {/* SECCIÓN DE CARGA DE ARCHIVOS */}
            <div style={styles.fileUploadContainer}>
                <div style={styles.fileBox}>
                <span style={styles.fileLabel}>Cargar CFDI XML *</span>
                <div style={styles.fileRow}>
                    <span style={styles.fileName}>{facturaFile ? facturaFile.name : "Ningún archivo seleccionado"}</span>
                    <label style={styles.fileButtonLabel}>
                    Seleccionar archivo...
                    <input type="file" accept=".xml,application/xml,text/xml" style={{ display: 'none' }} onChange={(e) => setFacturaFile(e.target.files?.[0] || null)} />
                    </label>
                </div>
                </div>

                <div style={styles.fileBox}>
                <span style={styles.fileLabel}>Cargar Vale (opcional)</span>
                <div style={styles.fileRow}>
                    <span style={styles.fileName}>{valeFile ? valeFile.name : "Ningún archivo seleccionado"}</span>
                    <label style={styles.fileButtonLabel}>
                    Seleccionar archivo...
                    <input type="file" accept=".pdf" style={{ display: 'none' }} onChange={(e) => setValeFile(e.target.files[0])} />
                    </label>
                </div>
                </div>
            </div>

            {/* CAJA DE OBSERVACIONES */}
            <div style={styles.obsContainer}>
                <label style={styles.obsLabel}>Observaciones</label>
                <textarea 
                value={observaciones} 
                onChange={(e) => setObservaciones(e.target.value)} 
                style={styles.textarea}
                placeholder="Escribe aquí notas adicionales sobre este reembolso..."
                />
            </div>

            </div>

            {/* LÍNEA DIVISORA */}
            <div style={styles.divider}></div>

            {/* COLUMNA DERECHA: PANEL DE VALIDACIÓN AUTOMÁTICA */}
            <div style={styles.validationColumn}>
            <h3 style={styles.validationTitle}>Validación Automática</h3>
            
            {cargandoValidacion && <p style={{textAlign: 'center', color: 'var(--text-revision)'}}>Procesando documentos con IA...</p>}

            {/* TARJETA 1: GASTO LISTO */}
            <div style={{
                ...styles.valCard, 
                borderColor: 'var(--sb-gastoListo)',
                opacity: estadoValidacion === 'listo' || estadoValidacion === null ? 1 : 0.4
            }}>
                <div style={{...styles.iconCircle, backgroundColor: 'var(--sb-pagadaBg)', color: 'var(--sb-gastoListo)'}}>✓</div>
                <div>
                <h4 style={{margin: '0 0 4px 0', fontSize: '14px', color: 'var(--text-h)'}}>Gasto listo para añadirse</h4>
                <p style={styles.valText}>No se encontraron errores ni discrepancias fiscales.</p>
                </div>
            </div>

            {/* TARJETA 2: CORRECCIÓN DE DATOS */}
            <div style={{
                ...styles.valCard, 
                borderColor: 'var(--sb-errorDatos)',
                opacity: estadoValidacion === 'error' || estadoValidacion === null ? 1 : 0.4
            }}>
                <div style={{...styles.iconCircle, backgroundColor: 'var(--sb-denegadaBg)', color: 'var(--sb-errorDatos)'}}>⚠️</div>
                <div>
                <h4 style={{margin: '0 0 4px 0', fontSize: '14px', color: 'var(--text-h)'}}>Corrección de datos</h4>
                <p style={styles.valText}>La fecha de la factura no coincide con la registrada a mano. Corrija y valide nuevamente.</p>
                </div>
            </div>

            {/* TARJETA 3: VERIFICAR LEGIBILIDAD */}
            <div style={{
                ...styles.valCard, 
                borderColor: 'var(--sb-errorLegibilidad)',
                opacity: estadoValidacion === 'legibilidad' || estadoValidacion === null ? 1 : 0.4
            }}>
                <div style={{...styles.iconCircle, backgroundColor: '#fffde6', color: '#b39200'}}>🔍</div>
                <div>
                <h4 style={{margin: '0 0 4px 0', fontSize: '14px', color: 'var(--text-h)'}}>Verificar legibilidad</h4>
                <p style={styles.valText}>El documento no se pudo leer correctamente. Vuelva a cargar el documento y valide nuevamente.</p>
                </div>
            </div>

            </div>

        </div>

        {/* FOOTER INFERIOR DE ACCIONES FIJAS */}
        <div style={styles.fixedFooter}>
            <button style={styles.validarActionBtn} onClick={handleValidarGasto}>
            Validar Gasto
            </button>
            <button style={styles.añadirActionBtn} onClick={handleGuardarGasto}>
            Añadir
            </button>
        </div>

        </div>
    );
    }

    // 🎨 ESTILOS UNIFICADOS CON TU IDENTIDAD
    const styles = {
    container: {
        maxWidth: '1100px',
        margin: '0 auto',
        padding: '20px',
        paddingBottom: '100px',
        textAlign: 'left',
    },
    topRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
    },
    mainTitle: {
        margin: 0,
        fontSize: '24px',
    },
    cancelarBtn: {
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text-WBtn)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '20px',
        padding: '6px 22px',
        fontSize: '14px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
    },
    mainGrid: {
        display: 'flex',
        gap: '20px',
    },
    formColumn: {
        flex: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
    },
    divider: {
        width: '1px',
        backgroundColor: 'var(--border)',
        alignSelf: 'stretch',
        opacity: 0.5,
    },
    validationColumn: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: '15px',
        paddingLeft: '10px',
    },
    validationTitle: {
        fontSize: '16px',
        fontWeight: 'bold',
        margin: '0 0 5px 0',
        color: 'var(--text-h)',
        textAlign: 'center',
    },
    formGrid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '15px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
    },
    label: {
        fontSize: '13px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
        textAlign: 'center',
    },



    // 👈 Ocupa ambas columnas del Grid
    inputGroupFull: {
        gridColumn: 'span 2',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
    },
    // 👈 Alinea el input y el botón en la misma línea
    inputWithButton: {
        display: 'flex',
        gap: '10px',
        alignItems: 'center',
    },


    // 👈 Estilo para el botón de confirmación
    btnValidar: {
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '8px',
        padding: '8px 15px',
        fontSize: '13px',
        fontWeight: 'bold',
        cursor: 'pointer',
        whiteSpace: 'nowrap', // Evita que el texto del botón se corte
        transition: 'background-color 0.2s ease',
        boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)',
    },



    input: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '14px',
        textAlign: 'center',
        outline: 'none',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
    },
    select: {
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '14px',
        textAlign: 'center',
        outline: 'none',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
    },
    fileUploadContainer: {
        display: 'flex',
        gap: '40px',
        marginTop: '10px',
    },
    fileBox: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
    },
    fileLabel: {
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
        textAlign: 'center',
    },
    fileRow: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '10px',
    },
    fileName: {
        fontSize: '13px',
        color: 'var(--text)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
    },
    fileButtonLabel: {
        background: 'var(--sb-gradient-tab, var(--sb-sendBtnBg))',
        color: 'var(--text-CBtn)',
        padding: '6px 14px',
        borderRadius: '8px',
        fontSize: '13px',
        fontWeight: '500',
        cursor: 'pointer',
        textAlign: 'center',
        whiteSpace: 'nowrap',
    },
    obsContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
    },
    obsLabel: {
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'var(--text-h)',
        textAlign: 'center',
    },
    textarea: {
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '15px',
        minHeight: '140px',
        fontSize: '14px',
        outline: 'none',
        resize: 'vertical',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
    },
    valCard: {
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        border: '1px solid',
        borderRadius: '10px',
        padding: '12px',
        backgroundColor: 'var(--bg)',
        transition: 'opacity 0.3s ease',
    },
    iconCircle: {
        width: '28px',
        height: '28px',
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 'bold',
        fontSize: '14px',
        flexShrink: 0,
    },
    valText: {
        margin: 0,
        fontSize: '12px',
        lineHeight: '130%',
        color: '#555',
    },
    fixedFooter: {
        position: 'fixed',
        bottom: 0,
        left: 0,
        width: '100%',
        backgroundColor: '#fff9f9',
        boxShadow: '0 -4px 10px rgba(0, 0, 0, 0.03)',
        padding: '15px 0',
        display: 'flex',
        justifyContent: 'center',
        gap: '30px',
        zIndex: 1000,
        borderTop: '1px solid var(--border)',
    },
    validarActionBtn: {
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text-h)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        padding: '10px 40px',
        fontSize: '16px',
        cursor: 'pointer',
    },
    añadirActionBtn: {
        background: 'var(--sb-gradient-tab, var(--sb-sendBtnBg))',
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '10px',
        padding: '10px 55px',
        fontSize: '16px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
    }
};

export default AnadirGasto;

function fechaHoyFormulario() {
    const hoy = new Date();
    const dia = String(hoy.getDate()).padStart(2, '0');
    const mes = String(hoy.getMonth() + 1).padStart(2, '0');
    const anio = hoy.getFullYear();
    return `${dia}-${mes}-${anio}`;
}

function validarCfdiXmlRequerido(file) {
    if (!file) {
        return 'Debes cargar el CFDI XML antes de añadir el gasto.';
    }

    if (!esXml(file)) {
        return 'El archivo de CFDI debe ser XML.';
    }

    return null;
}

function esXml(file) {
    const nombre = file?.name?.toLowerCase() || '';
    const tipo = file?.type?.toLowerCase() || '';
    return nombre.endsWith('.xml') || tipo.includes('xml');
}

async function validarCfdiAntesDeAnadir(file, monto, nombreGasto) {
    const parsed = await parseCfdi(file);
    const errores = [];
    const montoGasto = Number(monto);
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

    if (parsed.uuid) {
        const uuidNormalizado = normalizarUuidLocal(parsed.uuid);
        if (uuidYaExisteEnSolicitud(uuidNormalizado)) {
            errores.push('El UUID fiscal del XML ya está agregado en otro gasto de esta solicitud.');
        } else {
            const disponibilidad = await checkCfdiUuidAvailability(parsed.uuid);
            if (!disponibilidad.is_available) {
                errores.push('El UUID fiscal del XML ya está registrado en otro gasto.');
            }
        }
    }

    if (errores.length) {
        throw new Error([
            `El CFDI XML del gasto "${nombreGasto}" no coincide con el gasto capturado:`,
            ...errores,
        ].join('\n'));
    }

    return parsed;
}

function uuidYaExisteEnSolicitud(uuid) {
    if (!uuid) return false;
    return loadDraftGastos().some((gasto) => {
        const uuidExistente = normalizarUuidLocal(
            gasto.cfdiUuid || gasto.cfdi_uuid || gasto.folioFiscal || gasto.folio_fiscal
        );
        return uuidExistente === uuid;
    });
}

function normalizarUuidLocal(value) {
    return value ? String(value).trim().toUpperCase() : null;
}

function numeroOculto(value) {
    if (value === null || value === undefined || value === '') return null;
    const numero = Number(value);
    return Number.isNaN(numero) ? null : numero;
}

function redondearMonto(value) {
    return Number(value || 0).toFixed(2);
}

function formatoMonto(value) {
    return `$${redondearMonto(value)}`;
}

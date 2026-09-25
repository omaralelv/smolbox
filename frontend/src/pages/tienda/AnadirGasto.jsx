import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
    addFrontendGasto,
    apiErrorMessage,
    checkCfdiUuidAvailability,
    createFrontendSolicitud,
    getFrontendContext,
    parseCfdi,
    previewInvoiceOcr,
    uploadExpenseAttachment,
    validateExpenseCfdi,
} from '../../lib/api';
import { addDraftGasto, loadDraftGastos, loadDraftRequest, saveDraftRequest } from '../../lib/draftSolicitud';

function AnadirGasto() {
    const navigate = useNavigate();

    // 1. ESTADOS DEL FORMULARIO
    const [fecha, setFecha] = useState('');
    const [categoria, setCategoria] = useState('Papelería');
    const [monto, setMonto] = useState('');
    const [folio, setFolio] = useState('');
    const [tipoDocumento, setTipoDocumento] = useState('factura'); // 'factura' | 'vale' | 'recibo'
    // Agrega el nuevo estado para el área
    const [areaAutoriza, setAreaAutoriza] = useState('');


    const [facturaFile, setFacturaFile] = useState(null);
    const [valeFile, setValeFile] = useState(null);
    const [reciboFile, setReciboFile] = useState(null);
    const [observaciones, setObservaciones] = useState('');

    const [folioValidado, setFolioValidado] = useState(false);
    const [ocrFactura, setOcrFactura] = useState(null);
    const [ocrVale, setOcrVale] = useState(null);
    const [ocrRecibo, setOcrRecibo] = useState(null);
    const [mensajeValidacion, setMensajeValidacion] = useState('');


    // Cambio dinámico de tipo de documento
    const handleTipoDocumentoChange = (nuevoTipo) => {
        setTipoDocumento(nuevoTipo);
        setMensajeValidacion('');
        if (nuevoTipo === 'vale' || nuevoTipo === 'recibo') {
            setFolio('N/A');
            setFolioValidado(true);
        } else {
            if (folio === 'N/A') setFolio('');
            setFolioValidado(false);
        }
    };

    const handleValidarFolio = () => {
        const folioNormalizado = normalizarUuidLocal(folio);
        if (!folioNormalizado || folioNormalizado === '') {
            const mensaje = 'Primero captura o valida un folio fiscal.';
            setEstadoValidacion('error');
            setMensajeValidacion(mensaje);
            alert(mensaje);
            return;
        }

        if (tipoDocumento === 'factura' && esPdf(facturaFile)) {
            if (!ocrCoincideConArchivoActual(ocrFactura, facturaFile)) {
                const mensaje = 'Primero presiona "Validar Gasto" para extraer la información faltante de la factura.';
                setEstadoValidacion('error');
                setMensajeValidacion(mensaje);
                alert(mensaje);
                return;
            }

            setOcrFactura((actual) => datosOcrParaBorrador(actual, facturaFile, {
                monto,
                folio: folioNormalizado,
            }));
        }

        setFolio(folioNormalizado);
        setFolioValidado(true);
    };

    const handleMontoChange = (nuevoMonto) => {
        setMonto(nuevoMonto);
        const archivoDocumento = archivoParaTipoDocumento(tipoDocumento, { facturaFile, valeFile, reciboFile });
        const ocrDocumento = ocrParaTipoDocumento(tipoDocumento, { ocrFactura, ocrVale, ocrRecibo });
        if (
            tipoDocumento === 'factura'
            && esPdf(facturaFile)
            && ocrCoincideConArchivoActual(ocrFactura, facturaFile)
            && ocrFactura.validatedAmount !== montoParaValidacion(nuevoMonto)
        ) {
            setEstadoValidacion('advertencia');
            setMensajeValidacion('El monto cambió. Revisa que sea correcto; se guardará el monto capturado para la factura.');
        }
        if (
            tipoDocumento !== 'factura'
            && ocrCoincideConArchivoActual(ocrDocumento, archivoDocumento)
            && ocrDocumento.validatedAmount !== montoParaValidacion(nuevoMonto)
        ) {
            const etiqueta = etiquetaDocumento(tipoDocumento).toLowerCase();
            setEstadoValidacion('advertencia');
            setMensajeValidacion(`El monto cambió. Revisa que sea correcto; se guardará el monto capturado para el ${etiqueta}.`);
        }
    };

    const handleFolioChange = (nuevoFolio) => {
        setFolio(nuevoFolio);
        setFolioValidado(false); // Resetea el estatus si el usuario edita el folio
        if (
            tipoDocumento === 'factura'
            && esPdf(facturaFile)
            && ocrCoincideConArchivoActual(ocrFactura, facturaFile)
        ) {
            setEstadoValidacion(null);
            setMensajeValidacion('El folio cambió. Presiona "Confirmar" para guardar el nuevo folio.');
        }
    };

    const handleValeFileChange = (file) => {
        const ocrDelMismoArchivo = ocrCoincideConArchivoActual(ocrVale, file);
        setValeFile(file || null);
        setEstadoValidacion(null);
        setMensajeValidacion(file ? 'Vale cargado. Presiona "Validar Gasto" para revisar monto y fecha.' : '');
        if (!ocrDelMismoArchivo) {
            setOcrVale(null);
        }
    };

    const handleReciboFileChange = (file) => {
        const ocrDelMismoArchivo = ocrCoincideConArchivoActual(ocrRecibo, file);
        setReciboFile(file || null);
        setEstadoValidacion(null);
        setMensajeValidacion(file ? 'Recibo cargado. Presiona "Validar Gasto" para revisar monto y fecha.' : '');
        if (!ocrDelMismoArchivo) {
            setOcrRecibo(null);
        }
    };

    const guardarOcrDocumento = (tipo, ocr) => {
        if (tipo === 'vale') {
            setOcrVale(ocr);
            return;
        }
        if (tipo === 'recibo') {
            setOcrRecibo(ocr);
            return;
        }
        setOcrFactura(ocr);
    };

    const handleFacturaFileChange = async (file) => {
        const ocrDelMismoArchivo = ocrCoincideConArchivoActual(ocrFactura, file);
        setFacturaFile(file || null);
        setEstadoValidacion(null);
        if (!ocrDelMismoArchivo) {
            setOcrFactura(null);
        }
        setMensajeValidacion('');

        if (!file) {
            setFolio('');
            setFolioValidado(false);
            return;
        }

        if (!esXml(file) && !esPdf(file)) {
            setFacturaFile(null);
            setFolio('');
            setFolioValidado(false);
            alert('La factura debe ser XML o PDF.');
            return;
        }

        if (esPdf(file)) {
            const folioOcr = ocrDelMismoArchivo ? normalizarUuidLocal(ocrFactura.suggested_cfdi_uuid) : null;
            setFolio(folioOcr || 'OCR pendiente');
            setFolioValidado(Boolean(folioOcr && folioValidado && normalizarUuidLocal(folio) === folioOcr));
            setMensajeValidacion(
                folioOcr
                    ? 'Esta factura PDF ya fue leída. Confirma el folio para poder añadir el gasto.'
                    : 'Factura PDF cargada. Presiona "Validar Gasto" para extraer el folio fiscal.'
            );
            return;
        }

        try {
            const parsed = await parseCfdi(file);
            const uuid = normalizarUuidLocal(parsed.uuid);

            if (!uuid) {
                setFolio('');
                setFolioValidado(false);
                alert('El XML no trae folio fiscal.');
                return;
            }

            setFolio(uuid);
            setFolioValidado(false);
        } 
        
        catch (error) {
            setFolio('');
            setFolioValidado(false);
            alert(apiErrorMessage(error));
        }
    };

    
    // Estados para simular la IA de Validación Automática
    const [estadoValidacion, setEstadoValidacion] = useState(null); // 'listo', 'advertencia', 'error', 'legibilidad'
    const [cargandoValidacion, setCargandoValidacion] = useState(false);
    const [guardandoGasto, setGuardandoGasto] = useState(false);

    // Menú desplegable unificado para no perder coherencia
    const categoriasGasto = ["Agua", "Alimentos", "Artículos de Limpieza", "Bolsas", "Energía Eléctrica", "Equipo de Cómputo Menor", "Equipo Menor", "Extintores y Protección Civil", 
        "Gasolina", "Hospedaje", "Insumo", "Licencias y Permisos", "Mantenimiento Equipo de Cómputo", "Medicamentos", "No Deducibles", "Papelería", "Paquetería y Mensajería", "Pasajes y Taxis", "Publicidad",
        "Recolección de Basura", "Servicio de Agua", "Teléfono", "Trámites", "Trasportación", "Vigilancia", "Otros"];

    // Lista de áreas que autorizan
    const areasAutorizan = ["Auditoría Interna", "Contabilidad", "Gestoría", "Insumos", "Mantenimiento",  "Operaciones", "Pago de Luz", "Recursos Humanos", "Servicio de Agua", "Sistemas", "Supervisores", "Tráfico"];


    // Condición para saber si la categoría seleccionada requiere habilitar el select
    const esTransporte = categoria === 'Pasajes y Taxis' || categoria === 'Trasportación';
    const esInsumo = categoria === 'Insumo';
    const areaAutorizaResuelta = esTransporte ? areaAutoriza : (esInsumo ? 'Insumos' : null);
    const requiereAutorizacion = esTransporte || esInsumo;
    const muestraAreaAutoriza = esTransporte || esInsumo;


    // 2. LÓGICA DE SIMULACIÓN DE IA
    const handleValidarGasto = async () => {
        if (cargandoValidacion) return;

        const errorDocumento = validarDocumentoRequerido(tipoDocumento, { facturaFile, valeFile, reciboFile });
        if (errorDocumento) {
            setEstadoValidacion('error');
            setMensajeValidacion(errorDocumento);
            alert(errorDocumento);
            return;
        }

        if (tipoDocumento !== 'factura') {
            const archivoDocumento = archivoParaTipoDocumento(tipoDocumento, { facturaFile, valeFile, reciboFile });
            const ocrDocumento = ocrParaTipoDocumento(tipoDocumento, { ocrFactura, ocrVale, ocrRecibo });
            const etiqueta = etiquetaDocumento(tipoDocumento);
            setCargandoValidacion(true);
            setMensajeValidacion('');

            try {
                const ocrParsed = await leerDocumentoConOcr(archivoDocumento, ocrDocumento, tipoDocumento);
                const advertencias = validarResultadoDocumentoSimpleOcr(ocrParsed, monto, fecha, etiqueta);
                const ocrActualizado = datosOcrParaBorrador(ocrParsed, archivoDocumento, { monto });
                guardarOcrDocumento(tipoDocumento, ocrActualizado);
                const etiquetaMinuscula = etiqueta.toLowerCase();
                const resultadoMonto = resultadoMontoDocumentoSimpleOcr(ocrParsed, monto);
                const mensajeBase = mensajeBaseDocumentoSimpleOcr(
                    etiquetaMinuscula,
                    resultadoMonto,
                    Boolean(ocrParsed.fueReutilizado),
                );
                setMensajeValidacion(mensajeConAdvertencias(mensajeBase, advertencias));
                setEstadoValidacion(estadoParaAdvertencias(advertencias));
            } catch (error) {
                const mensaje = apiErrorMessage(error);
                setEstadoValidacion(esErrorDeLecturaOcr(mensaje) ? 'legibilidad' : 'error');
                setMensajeValidacion(mensaje);
                alert(mensaje);
            } finally {
                setCargandoValidacion(false);
            }
            return;
        }

        const facturaEsXml = tipoDocumento === 'factura' && esXml(facturaFile);
        const facturaEsPdf = tipoDocumento === 'factura' && esPdf(facturaFile);

        if (tipoDocumento === 'factura' && facturaEsXml && !folioValidado) {
            const mensaje = "Por favor, confirma el Folio Fiscal antes de validar.";
            setEstadoValidacion('error');
            setMensajeValidacion(mensaje);
            alert(mensaje);
            return;
        }

        setCargandoValidacion(true);
        setMensajeValidacion('');

        try {
            if (facturaEsXml) {
                const { parsed: cfdiParsed, advertencias } = await validarCfdiAntesDeAnadir(facturaFile, monto, fecha, `Gasto - ${categoria}`, folio);
                validarSolicitudDespuesDeAnadir([
                    ...loadDraftGastos(),
                    crearGastoParaValidacion({ categoria, monto, folio, fecha, observaciones, cfdiParsed, facturaFile, valeFile }),
                ]);
                setMensajeValidacion(mensajeConAdvertencias('XML validado. El gasto está listo para añadirse.', advertencias));
                setEstadoValidacion(estadoParaAdvertencias(advertencias));
            } else if (facturaEsPdf) {
                const ocrParsed = await leerFacturaPdfConOcr(facturaFile, ocrFactura);
                const uuidOcr = normalizarUuidLocal(ocrParsed.suggested_cfdi_uuid);
                const folioActual = normalizarUuidLocal(folio);
                if (uuidOcr) {
                    setFolio(uuidOcr);
                    setFolioValidado(Boolean(folioValidado && folioActual === uuidOcr));
                }
                const advertencias = await validarResultadoFacturaPdf(ocrParsed, monto, fecha, `Gasto - ${categoria}`, uuidOcr || folio);
                const ocrActualizado = datosOcrParaBorrador(ocrParsed, facturaFile, {
                    monto,
                    folio: uuidOcr || folio,
                });
                setOcrFactura(ocrActualizado);
                validarSolicitudDespuesDeAnadir([
                    ...loadDraftGastos(),
                    crearGastoParaValidacion({
                        categoria,
                        monto,
                        folio: uuidOcr || folio,
                        fecha,
                        observaciones,
                        cfdiParsed: cfdiDesdeOcr(ocrActualizado),
                        facturaFile,
                        valeFile,
                        facturaRequiereOcr: true,
                        ocrValidado: true,
                    }),
                ]);
                const folioDetectado = uuidOcr || 'No detectado';
                const mensajeBase = ocrParsed.fueReutilizado
                    ? `Extracción de texto finalizada. Folio sugerido: ${folioDetectado}. Revisa que el Folio coincida con tu factura y presiona "Confirmar" para guardarlo.`
                    : `Extracción de texto finalizada. Folio sugerido: ${folioDetectado}. Revisa que el Folio coincida con tu factura y presiona "Confirmar" para guardarlo.`;
                setMensajeValidacion(mensajeConAdvertencias(mensajeBase, advertencias));
                setEstadoValidacion(estadoParaAdvertencias(advertencias));
            }
        } 
        catch (error) {
            const mensaje = apiErrorMessage(error);
            setEstadoValidacion(esErrorDeLecturaOcr(mensaje) ? 'legibilidad' : 'error');
            setMensajeValidacion(mensaje);
            alert(mensaje);
        } 
        finally {
            setCargandoValidacion(false);
        }
    };


    const handleGuardarGasto = async (e) => {
        e.preventDefault();
        if (guardandoGasto) return;

        const errorDocumento = validarDocumentoRequerido(tipoDocumento, { facturaFile, valeFile, reciboFile });
        if (errorDocumento) {
            setEstadoValidacion('error');
            setMensajeValidacion(errorDocumento);
            alert(errorDocumento);
            return;
        }

        const facturaEsXml = tipoDocumento === 'factura' && esXml(facturaFile);
        const facturaEsPdf = tipoDocumento === 'factura' && esPdf(facturaFile);
        if (tipoDocumento === 'factura' && facturaEsXml && !folioValidado) {
            const mensaje = 'Confirma el Folio Fiscal antes de añadir el gasto.';
            setEstadoValidacion('error');
            setMensajeValidacion(mensaje);
            alert(mensaje);
            return;
        }

        let cfdiParsed = null;
        let ocrParsed = ocrParaTipoDocumento(tipoDocumento, { ocrFactura, ocrVale, ocrRecibo });
        let advertencias = [];
        if (facturaEsXml) {
            try {
                const resultado = await validarCfdiAntesDeAnadir(facturaFile, monto, fecha, `Gasto - ${categoria}`, folio);
                cfdiParsed = resultado.parsed;
                advertencias = resultado.advertencias;
            } catch (error) {
                const mensaje = apiErrorMessage(error);
                setEstadoValidacion('error');
                setMensajeValidacion(mensaje);
                alert(mensaje);
                return;
            }
        } else if (facturaEsPdf) {
            try {
                if (!ocrCoincideConArchivoActual(ocrParsed, facturaFile)) {
                    const mensaje = 'Primero presiona "Validar Gasto" para leer la factura PDF con OCR.';
                    setEstadoValidacion('error');
                    setMensajeValidacion(mensaje);
                    alert(mensaje);
                    return;
                }
                advertencias = await validarResultadoFacturaPdf(ocrParsed, monto, fecha, `Gasto - ${categoria}`, folio);
                cfdiParsed = cfdiDesdeOcr(ocrParsed, folio);
            } catch (error) {
                const mensaje = apiErrorMessage(error);
                setEstadoValidacion(esErrorDeLecturaOcr(mensaje) ? 'legibilidad' : 'error');
                setMensajeValidacion(mensaje);
                alert(mensaje);
                return;
            }
        } else if (tipoDocumento !== 'factura') {
            const archivoDocumento = archivoParaTipoDocumento(tipoDocumento, { facturaFile, valeFile, reciboFile });
            const etiqueta = etiquetaDocumento(tipoDocumento);
            const etiquetaMinuscula = etiqueta.toLowerCase();

            try {
                if (!ocrCoincideConArchivoActual(ocrParsed, archivoDocumento)) {
                    const mensaje = `Primero presiona "Validar Gasto" para leer el ${etiquetaMinuscula} con OCR.`;
                    setEstadoValidacion('error');
                    setMensajeValidacion(mensaje);
                    alert(mensaje);
                    return;
                }
                advertencias = validarResultadoDocumentoSimpleOcr(ocrParsed, monto, fecha, etiqueta);
            } catch (error) {
                const mensaje = apiErrorMessage(error);
                setEstadoValidacion(esErrorDeLecturaOcr(mensaje) ? 'legibilidad' : 'error');
                setMensajeValidacion(mensaje);
                alert(mensaje);
                return;
            }
        }


        console.log("📝 TEXTO CAPTURADO EN EL INPUT:", observaciones);


        // 1. Creamos el objeto con la misma estructura que espera tu lista
        const nuevoGastoItem = {
            id: Date.now(), // Un ID único usando el tiempo actual
            nombre: `Gasto - ${categoria}`,
            monto: parseFloat(monto) || 0,
            tipo: categoria,
            tipoDocumento: tipoDocumento,
            folio: tipoDocumento === 'factura'
                ? (facturaEsPdf ? normalizarUuidLocal(folio) : folio)
                : 'N/A',
            fecha: fecha,
            areaAutoriza: areaAutorizaResuelta, // Guardamos la selección si aplica
            requiresAuthorization: requiereAutorizacion,

            observaciones: observaciones,
            
            //observacion: observaciones,
            cfdiUuid: cfdiParsed ? normalizarUuidLocal(cfdiParsed.uuid) : null,
            cfdiSubtotal: cfdiParsed ? numeroOculto(cfdiParsed.subtotal) : null,
            cfdiTotal: cfdiParsed ? cfdiParsed.total : null,
            cfdiCurrency: cfdiParsed ? cfdiParsed.currency : null,
            cfdiTaxAmount: cfdiParsed ? numeroOculto(cfdiParsed.tax_amount) : null,
            cfdiTaxRate: cfdiParsed ? numeroOculto(cfdiParsed.tax_rate) : null,
            facturaRequiereOcr: tipoDocumento === 'factura' && esPdf(facturaFile),
            ocrValidado: (tipoDocumento === 'factura' && esPdf(facturaFile)) || tipoDocumento !== 'factura',
            ocrPreviewToken: ocrParsed?.verification_token || null,
            ocrChecksumSha256: ocrParsed?.checksum_sha256 || null,

            facturaFile: tipoDocumento === 'factura' ? facturaFile : null,
            valeFile: tipoDocumento === 'vale' ? valeFile : null,
            reciboFile: tipoDocumento === 'recibo' ? reciboFile : null,
        };
    

        if (tipoDocumento === 'factura'){
            try {
                validarSolicitudDespuesDeAnadir([...loadDraftGastos(), nuevoGastoItem]);
            } catch (error) {
                const mensaje = apiErrorMessage(error);
                setEstadoValidacion('error');
                setMensajeValidacion(mensaje);
                alert(mensaje);
                return;
            }
        }

        setGuardandoGasto(true);

        try {
            const { solicitud, gastoBackend } = await guardarGastoEnBorradorBackend(nuevoGastoItem);
            const gastoGuardado = {
                ...nuevoGastoItem,
                id: gastoBackend.id || nuevoGastoItem.id,
                backendId: gastoBackend.backendId,
                folio: gastoBackend.folio || nuevoGastoItem.folio,
                cfdiSubtotal: numeroOculto(gastoBackend.cfdiSubtotal ?? gastoBackend.cfdi_subtotal),
                cfdiTotal: numeroOculto(gastoBackend.cfdiTotal ?? gastoBackend.cfdi_total),
                cfdiTaxAmount: numeroOculto(gastoBackend.cfdiTaxAmount ?? gastoBackend.cfdi_tax_amount),
                cfdiTaxRate: numeroOculto(gastoBackend.cfdiTaxRate ?? gastoBackend.cfdi_tax_rate),
                cfdiCurrency: gastoBackend.cfdiCurrency ?? gastoBackend.cfdi_currency ?? nuevoGastoItem.cfdiCurrency,
                areaAutoriza: (
                    gastoBackend.authorizationArea
                    || gastoBackend.authorization_area_name
                    || nuevoGastoItem.areaAutoriza
                    || null
                ),
                authorizationArea: (
                    gastoBackend.authorizationArea
                    || gastoBackend.authorization_area_name
                    || nuevoGastoItem.authorizationArea
                    || nuevoGastoItem.areaAutoriza
                    || null
                ),
                requiresAuthorization: Boolean(
                    gastoBackend.requiresAuthorization
                    ?? gastoBackend.requires_authorization
                    ?? nuevoGastoItem.requiresAuthorization
                ),
                urlFactura: gastoBackend.urlFactura || null,
                urlVale: gastoBackend.urlVale || null,
                urlRecibo: gastoBackend.urlRecibo || null,
                facturas: gastoBackend.facturas,
                documentoGuardadoEnBackend: true,
            };

            saveDraftRequest(solicitud);
            addDraftGasto(gastoGuardado);
            alert(mensajeConAdvertencias("¡Gasto guardado exitosamente en la solicitud!", advertencias));
            navigate('/solicitud/nueva');
        } catch (error) {
            const mensaje = apiErrorMessage(error);
            setEstadoValidacion('error');
            setMensajeValidacion(mensaje);
            alert(mensaje);
        } finally {
            setGuardandoGasto(false);
        }

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
                        <input type="text" value={fecha} onChange={(e) => setFecha(e.target.value)} 
                            placeholder="DD/MM/AAAA"
                            style={styles.input} />
                    </div>
                    <div style={styles.inputGroup}>
                        <label style={styles.label}>Categoría *</label>
                        <select value={categoria} onChange={(e) => setCategoria(e.target.value)} style={styles.select}>
                            {categoriasGasto.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                        </select>
                    </div>
                    <div style={styles.inputGroup}>
                        <label style={styles.label}>Monto *</label>
                        <input type="number" value={monto} onChange={(e) => handleMontoChange(e.target.value)}
                        placeholder="Ej. 123.45"
                        style={styles.input} />
                    </div>

                    {/* FOLIO FISCAL OCUPANDO AMBAS COLUMNAS CON BOTÓN DE CONFIRMACIÓN */}
                    <div style={styles.inputGroupFull}>
                        <label style={styles.label}>
                            Folio Fiscal {tipoDocumento === 'factura' ? '*' : ''}
                        </label>
                        <div style={styles.inputWithButton}>
                            <input 
                                type="text" 
                                value={tipoDocumento === 'factura' ? folio : 'N/A'} 
                                onChange={(e) => handleFolioChange(e.target.value)}
                                placeholder="Ej. 12345678-ABCD-1234-ABCD-1234567890AB"
                                style={{
                                    ...styles.input,
                                    flex: 1, // Toma todo el espacio disponible
                                    borderColor: folioValidado ? '#22c55e' : 'var(--border)'
                                }} 
                            />
                            {tipoDocumento === 'factura' && (
                                <button 
                                    type="button" 
                                    onClick={handleValidarFolio}
                                    style={{
                                        ...styles.btnValidar,
                                        backgroundColor: folioValidado ? '#22c55e' : 'var(--sb-sendBtnBg)'
                                    }}
                                >
                                    {folioValidado ? '✓ Confirmado' : 'Confirmar'}
                                </button>
                            )}
                        </div>
                    </div>

                    {/* SELECTOR DESPLEGABLE CON HABILITACIÓN CONDICIONAL */}
                    <div style={styles.inputGroupArea}>
                        <label style={{
                            ...styles.label,
                            opacity: muestraAreaAutoriza ? 1 : 0.4
                        }}>
                            Área que autoriza {esTransporte ? '*' : esInsumo ? '(automática)' : ''}
                        </label>
                        <select 
                            value={esInsumo ? 'Insumos' : areaAutoriza}
                            onChange={(e) => setAreaAutoriza(e.target.value)} 
                            disabled={!esTransporte}
                            style={{
                                ...styles.select,
                                opacity: muestraAreaAutoriza ? 1 : 0.4,
                                cursor: esTransporte ? 'pointer' : 'not-allowed',
                                backgroundColor: muestraAreaAutoriza ? 'var(--bg)' : '#f3f4f6'
                            }}
                        >
                            <option value="">Seleccionar área...</option>
                            {areasAutorizan.map(area => (
                                <option key={area} value={area}>{area}</option>
                            ))}
                        </select>
                    </div>
                </div>

            

            {/* SECCIÓN DE SELECCIÓN Y CARGA DE ARCHIVOS */}
                    <div style={styles.fileUploadContainer}>
                        {/* OP Cargar Factura */}
                        <div style={styles.fileBox}>
                            <label style={styles.radioLabel}>
                                <input 
                                    type="radio" 
                                    name="tipoDocumento" 
                                    value="factura" 
                                    checked={tipoDocumento === 'factura'} 
                                    onChange={() => handleTipoDocumentoChange('factura')}
                                    //style={styles.radioInput}
                                    style={{
                                        ...styles.radioInput,
                                        backgroundColor: tipoDocumento === 'factura' ? 'var(--border)' : 'transparent',
                                        boxShadow: tipoDocumento === 'factura' ? 'inset 0 0 0 2px #ffffff' : 'none',
                                    }}
                                />
                                Cargar Factura
                            </label>
                            <div style={styles.fileRow}>
                                <span style={styles.fileName}>
                                    {facturaFile ? facturaFile.name : "Ningún archivo seleccionado"}
                                </span>
                                <label style={{
                                    ...styles.fileButtonLabel,
                                    opacity: tipoDocumento === 'factura' ? 1 : 0.35,
                                    cursor: tipoDocumento === 'factura' ? 'pointer' : 'not-allowed'
                                }}>
                                    Seleccionar archivo...
                                    <input 
                                        type="file" 
                                        accept=".xml,.pdf,application/xml,text/xml,application/pdf"
                                        disabled={tipoDocumento !== 'factura'}
                                        style={{ display: 'none' }} 
                                        onChange={(e) => handleFacturaFileChange(e.target.files?.[0] || null)} 
                                    />
                                </label>
                            </div>
                        </div>

                        {/* OP Cargar Vale */}
                        <div style={styles.fileBox}>
                            <label style={styles.radioLabel}>
                                <input 
                                    type="radio" 
                                    name="tipoDocumento" 
                                    value="vale" 
                                    checked={tipoDocumento === 'vale'} 
                                    onChange={() => handleTipoDocumentoChange('vale')}
                                    style={{
                                        ...styles.radioInput,
                                        backgroundColor: tipoDocumento === 'vale' ? 'var(--border)' : 'transparent',
                                        boxShadow: tipoDocumento === 'vale' ? 'inset 0 0 0 2px #ffffff' : 'none',
                                    }}
                                />
                                Cargar Vale
                            </label>
                            <div style={styles.fileRow}>
                                <span style={styles.fileName}>
                                    {valeFile ? valeFile.name : "Ningún archivo seleccionado"}
                                </span>
                                <label style={{
                                    ...styles.fileButtonLabel,
                                    opacity: tipoDocumento === 'vale' ? 1 : 0.35,
                                    cursor: tipoDocumento === 'vale' ? 'pointer' : 'not-allowed'
                                }}>
                                    Seleccionar archivo...
                                    <input 
                                        type="file" 
                                        accept=".pdf,application/pdf" 
                                        disabled={tipoDocumento !== 'vale'}
                                        style={{ display: 'none' }} 
                                        onChange={(e) => handleValeFileChange(e.target.files?.[0] || null)}
                                    />
                                </label>
                            </div>
                        </div>

                        {/* OP Cargar Recibo */}
                        <div style={styles.fileBox}>
                            <label style={styles.radioLabel}>
                                <input 
                                    type="radio" 
                                    name="tipoDocumento" 
                                    value="recibo" 
                                    checked={tipoDocumento === 'recibo'} 
                                    onChange={() => handleTipoDocumentoChange('recibo')}
                                    style={{
                                        ...styles.radioInput,
                                        backgroundColor: tipoDocumento === 'recibo' ? 'var(--border)' : 'transparent',
                                        boxShadow: tipoDocumento === 'recibo' ? 'inset 0 0 0 2px #ffffff' : 'none',
                                    }}
                                />
                                Cargar Recibo
                            </label>
                            <div style={styles.fileRow}>
                                <span style={styles.fileName}>
                                    {reciboFile ? reciboFile.name : "Ningún archivo seleccionado"}
                                </span>
                                <label style={{
                                    ...styles.fileButtonLabel,
                                    opacity: tipoDocumento === 'recibo' ? 1 : 0.35,
                                    cursor: tipoDocumento === 'recibo' ? 'pointer' : 'not-allowed'
                                }}>
                                    Seleccionar archivo...
                                    <input 
                                        type="file" 
                                        accept=".pdf,application/pdf" 
                                        disabled={tipoDocumento !== 'recibo'}
                                        style={{ display: 'none' }} 
                                        onChange={(e) => handleReciboFileChange(e.target.files?.[0] || null)}
                                    />
                                </label>
                            </div>
                        </div>
                    </div>



            {/* CAJA DE OBSERVACIONES */}
            <div style={styles.obsContainer}>
                <label style={styles.obsLabel}>Observaciones</label>
                <textarea 
                    style={styles.textarea}
                    placeholder="Escribe aquí notas adicionales sobre este reembolso..."
                    value={observaciones} 
                    onChange={(e) => setObservaciones(e.target.value)} 
                />
            </div>

            </div>

            {/* LÍNEA DIVISORA */}
            <div style={styles.divider}></div>

            {/* COLUMNA DERECHA: PANEL DE VALIDACIÓN AUTOMÁTICA */}
            <div style={styles.validationColumn}>
            <h3 style={styles.validationTitle}>Validación Automática</h3>
            
            {cargandoValidacion && <p style={{textAlign: 'center', color: 'var(--text-revision)'}}>Procesando documentos con IA...</p>}

            {mensajeValidacion && (
                <div style={{
                    ...styles.validationMessage,
                    ...(estadoValidacion === 'listo'
                        ? styles.validationMessageOk
                        : estadoValidacion === 'advertencia'
                            ? styles.validationMessageWarning
                        : styles.validationMessageError)
                }}>
                    {mensajeValidacion}
                </div>
            )}

            </div>

        </div>

        {/* FOOTER INFERIOR DE ACCIONES FIJAS */}
        <div style={styles.fixedFooter}>
            <button
                style={{
                    ...styles.validarActionBtn,
                    opacity: cargandoValidacion || guardandoGasto ? 0.6 : 1,
                    cursor: cargandoValidacion || guardandoGasto ? 'not-allowed' : 'pointer',
                }}
                onClick={handleValidarGasto}
                disabled={cargandoValidacion || guardandoGasto}
            >
            Validar Gasto
            </button>            
            <button
                style={{
                    ...styles.añadirActionBtn,
                    opacity: guardandoGasto ? 0.6 : 1,
                    cursor: guardandoGasto ? 'not-allowed' : 'pointer',
                }}
                onClick={handleGuardarGasto}
                disabled={guardandoGasto}
            >
            {guardandoGasto ? 'Guardando...' : 'Añadir'}
            </button>
        </div>

        </div>
    );
    }

    // 🎨 ESTILOS UNIFICADOS CON TU IDENTIDAD
    const styles = {
    container: {
        maxWidth: '1350px',
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
        gap: '15px',
    },
    formColumn: {
        flex: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: '15px',
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

    inputGroupArea: {
        gridColumn: 'span 1', // Área que autoriza ocupa el 33% del ancho (2 de 6 columnas)
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
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
        //display: 'flex',
        //gap: '16px',
        //marginTop: '10px',
        //flexWrap: 'wrap',
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '20px',
        alignItems: 'start',
        marginTop: '10px',
    },
    fileBox: {
        flex: '1 1 0',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        //minWidth: '150px',
    },



    radioLabel: {
        fontSize: '14px',
        fontWeight: 'bold',
        color: '#000000',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '6px',
        cursor: 'pointer',
    },
    radioInput: {
        appearance: 'none',
        WebkitAppearance: 'none',
        border: '2px solid var(--border)',
        borderRadius: '50%',
        outline: 'none',
        placeContent: 'center',
        accentColor: 'var(--sb-sendBtnBg)',
        width: '16px',
        height: '16px',
        cursor: 'pointer',
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
        fontSize: '12px',
        color: 'var(--text)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
    },
    fileButtonLabel: {
        background: 'var(--sb-gradient-tab, var(--sb-sendBtnBg))',
        color: 'var(--text-CBtn)',
        padding: '5px 8px',
        borderRadius: '8px',
        fontSize: '12px',
        fontWeight: '500',
        cursor: 'pointer',
        textAlign: 'center',
        whiteSpace: 'nowrap',
    },
    obsContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
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
    validationMessage: {
        borderRadius: '10px',
        padding: '10px 12px',
        fontSize: '13px',
        lineHeight: 1.35,
        whiteSpace: 'pre-line',
        border: '1px solid',
    },
    validationMessageOk: {
        backgroundColor: 'var(--sb-pagadaBg)',
        borderColor: 'var(--sb-gastoListo)',
        color: 'var(--text-pagada)',
        fontWeight: '500',
    },
    validationMessageError: {
        backgroundColor: 'var(--sb-denegadaBg)',
        borderColor: 'var(--sb-errorDatos)',
        color: 'var(--text-denegada)',
        fontWeight: '500',
    },
    validationMessageWarning: {
        backgroundColor: '#fff2be',
        borderColor: '#eacf00',
        color: '#92400e',
        fontWeight: '500',
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

async function guardarGastoEnBorradorBackend(gasto) {
    const gastosPrevios = loadDraftGastos();
    const gastosPreviosBackendIds = new Set(
        gastosPrevios
            .map((item) => item.backendId || item.backend_id)
            .filter(Boolean)
            .map(String)
    );
    const payloadGasto = gastoPayloadParaBackend(gasto);
    const borradorActual = loadDraftRequest();
    let solicitud;

    if (borradorActual?.backendId) {
        solicitud = await addFrontendGasto(borradorActual.backendId, payloadGasto);
    } else {
        const contexto = await getFrontendContext();
        solicitud = await createFrontendSolicitud({
            tienda: contexto.tienda,
            montoTotal: String(gasto.monto || 0),
            gastos: [payloadGasto],
        });
    }

    const gastoBackend = gastoAgregadoDesdeRespuesta(solicitud, gastosPreviosBackendIds, gasto);
    if (!gastoBackend?.backendId) {
        throw new Error('No se pudo identificar el gasto guardado en el servidor.');
    }

    await subirDocumentoGastoBackend(gastoBackend.backendId, gasto);
    return { solicitud, gastoBackend };
}

function gastoPayloadParaBackend(gasto) {
    return {
        fecha: gasto.fecha,
        categoria: gasto.tipo || gasto.type,
        monto: String(gasto.monto),
        folio: folioManualLocal(gasto.folio),
        cfdiUuid: gasto.cfdiUuid || null,
        cfdiSubtotal: numeroOculto(gasto.cfdiSubtotal),
        cfdiTotal: numeroOculto(gasto.cfdiTotal),
        cfdiTaxAmount: numeroOculto(gasto.cfdiTaxAmount),
        cfdiTaxRate: numeroOculto(gasto.cfdiTaxRate),
        cfdiCurrency: gasto.cfdiCurrency || null,
        observaciones: gasto.observaciones || null,
        observacionesHistorial: [],
        requiresAuthorization: Boolean(gasto.requiresAuthorization || gasto.areaAutoriza),
        authorizationArea: gasto.areaAutoriza || gasto.authorizationArea || null,
    };
}

function gastoAgregadoDesdeRespuesta(solicitud, gastosPreviosBackendIds, gastoLocal) {
    const gastos = solicitud?.gastos || [];
    const nuevos = gastos.filter(
        (gasto) => !gastosPreviosBackendIds.has(String(gasto.backendId || gasto.backend_id || gasto.id))
    );
    const candidatos = nuevos.length ? nuevos : gastos;
    const folioLocal = normalizarUuidLocal(gastoLocal?.folio);
    const tipoLocal = String(gastoLocal?.tipo || gastoLocal?.type || '').trim().toLowerCase();
    const montoLocal = redondearMonto(gastoLocal?.monto);

    return (
        candidatos.find((gasto) => (
            redondearMonto(gasto.monto) === montoLocal
            && String(gasto.tipo || gasto.type || '').trim().toLowerCase() === tipoLocal
            && (!folioLocal || normalizarUuidLocal(gasto.folio || gasto.folioFiscal || gasto.folio_fiscal) === folioLocal)
        ))
        || nuevos[0]
        || gastos[gastos.length - 1]
        || null
    );
}

async function subirDocumentoGastoBackend(expenseId, gasto) {
    if (gasto.valeFile) {
        await uploadExpenseAttachment(expenseId, gasto.valeFile, 'other', {
            ocrPreviewToken: gasto.ocrPreviewToken,
        });
    }

    if (gasto.reciboFile) {
        await uploadExpenseAttachment(expenseId, gasto.reciboFile, 'receipt', {
            ocrPreviewToken: gasto.ocrPreviewToken,
        });
    }

    if (!gasto.facturaFile) return;

    if (esXml(gasto.facturaFile)) {
        const resultado = await validateExpenseCfdi(expenseId, gasto.facturaFile);
        if (!resultado.is_valid) {
            throw new Error(mensajeCfdiBackendInvalido(gasto, resultado));
        }
        return;
    }

    await uploadExpenseAttachment(expenseId, gasto.facturaFile, 'receipt', {
        ocrPreviewToken: gasto.ocrPreviewToken,
    });
}

function mensajeCfdiBackendInvalido(gasto, resultado) {
    const errores = (resultado.issues || [])
        .filter((issue) => issue.severity !== 'warning')
        .map((issue) => issue.message);

    return [
        `El CFDI XML del gasto "${gasto.nombre}" no es válido.`,
        errores.length ? errores.join('\n') : 'Revisa que el total, moneda, UUID y RFC coincidan.',
    ].join('\n');
}

function folioManualLocal(folio) {
    if (!folio || folio === '' || folio === 'N/A') return null;
    return folio;
}

function validarCfdiXmlRequerido(file) {
    if (!file) {
        return 'Debes cargar la factura XML o PDF antes de añadir el gasto.';
    }

    if (!esXml(file) && !esPdf(file)) {
        return 'La factura debe ser XML o PDF.';
    }

    return null;
}

function validarDocumentoRequerido(tipoDocumento, archivos) {
    if (tipoDocumento === 'factura') {
        return validarCfdiXmlRequerido(archivos.facturaFile);
    }

    const documento = tipoDocumento === 'vale' ? archivos.valeFile : archivos.reciboFile;
    if (!documento) {
        return `Debes cargar el ${tipoDocumento} antes de añadir el gasto.`;
    }
    if (!esPdf(documento)) {
        return `El ${tipoDocumento} debe ser un archivo PDF.`;
    }

    return null;
}

function archivoParaTipoDocumento(tipoDocumento, archivos) {
    if (tipoDocumento === 'factura') return archivos.facturaFile;
    if (tipoDocumento === 'vale') return archivos.valeFile;
    if (tipoDocumento === 'recibo') return archivos.reciboFile;
    return null;
}

function ocrParaTipoDocumento(tipoDocumento, ocrs) {
    if (tipoDocumento === 'vale') return ocrs.ocrVale;
    if (tipoDocumento === 'recibo') return ocrs.ocrRecibo;
    return ocrs.ocrFactura;
}

function etiquetaDocumento(tipoDocumento) {
    if (tipoDocumento === 'vale') return 'Vale';
    if (tipoDocumento === 'recibo') return 'Recibo';
    return 'Factura';
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

async function validarCfdiAntesDeAnadir(file, monto, fecha, nombreGasto, folioCapturado = null) {
    const parsed = await parseCfdi(file);
    const errores = [];
    const advertencias = [];
    const montoGasto = Number(monto);
    const totalCfdi = parsed.total === null || parsed.total === undefined ? null : Number(parsed.total);
    const fechaGasto = normalizarFechaCapturada(fecha);
    const fechaCfdi = normalizarFechaCfdi(parsed.issued_at);
    const uuidXml = normalizarUuidLocal(parsed.uuid);
    const uuidCapturado = normalizarUuidLocal(folioCapturado);

    if (!parsed.uuid) {
        errores.push('- El XML no trae UUID fiscal.');
    }

    if (uuidCapturado && uuidXml && uuidCapturado !== uuidXml) {
        advertencias.push(`- El folio confirmado (${uuidCapturado}) no coincide con el folio fiscal del XML (${uuidXml}). Se guardará el folio de la factura XML.`);
    }

    if (totalCfdi === null || Number.isNaN(totalCfdi)) {
        advertencias.push('- El XML no trae total fiscal. Se usará el monto capturado por el usuario.');
    } else if (redondearMonto(totalCfdi) !== redondearMonto(montoGasto)) {
        advertencias.push(`- El total del XML (${formatoMonto(totalCfdi)}) no coincide con el monto del gasto (${formatoMonto(montoGasto)}). Revisa el dato capturado; se guardará el monto que ingresó el usuario.`);
    }

    if (parsed.currency && parsed.currency.toUpperCase() !== 'MXN') {
        errores.push(`- La moneda del XML es ${parsed.currency}, pero el gasto se enviará como MXN.`);
    }

    if (!fechaGasto) {
        advertencias.push('- No se pudo revisar la fecha capturada. Revisa que esté en formato DD/MM/AAAA.');
    } else if (!fechaCfdi) {
        advertencias.push('- El XML no trae fecha fiscal para comparar.');
    } else if (fechaCfdi !== fechaGasto) {
        advertencias.push(`- La fecha del XML (${formatoFecha(fechaCfdi)}) no coincide con la fecha capturada (${formatoFecha(fechaGasto)}).`);
    }

    if (uuidXml) {
        if (uuidYaExisteEnSolicitud(uuidXml)) {
            errores.push('- El UUID fiscal del XML ya está agregado en otro gasto de esta solicitud.');
        } else {
            const disponibilidad = await checkCfdiUuidAvailability(parsed.uuid);
            if (!disponibilidad.is_available) {
                errores.push('- El UUID fiscal del XML ya está registrado en otro gasto.');
            }
        }
    }

    if (errores.length) {
        throw new Error([
            `- El CFDI XML del gasto no coincide con el gasto capturado:`,
            ...errores,
        ].join('\n'));
    }

    return { parsed, advertencias };
}

async function leerDocumentoConOcr(file, ocrActual = null, tipoDocumento = 'factura') {
    if (ocrCoincideConArchivoActual(ocrActual, file)) {
        return {
            ...ocrActual,
            fueReutilizado: true,
        };
    }

    return previewInvoiceOcr(file, tipoDocumento);
}

async function leerFacturaPdfConOcr(file, ocrActual = null) {
    return leerDocumentoConOcr(file, ocrActual, 'factura');
}

async function validarResultadoFacturaPdf(parsed, monto, fecha, nombreGasto, folioCapturado = null) {
    const errores = [];
    const advertencias = [];
    const uuid = normalizarUuidLocal(parsed.suggested_cfdi_uuid);
    const uuidCapturado = normalizarUuidLocal(folioCapturado);
    const uuidParaGuardar = uuidCapturado || uuid;
    const montoGasto = Number(monto);
    const totalOcr = parsed.extracted_total === null || parsed.extracted_total === undefined
        ? null
        : Number(parsed.extracted_total);
    const fechaGasto = normalizarFechaCapturada(fecha);
    const fechaOcr = normalizarFechaCfdi(parsed.extracted_date);

    if (totalOcr === null || Number.isNaN(totalOcr)) {
        advertencias.push('- El OCR no encontró total en el PDF. Se usará el monto capturado por el usuario.');
    } else if (redondearMonto(totalOcr) !== redondearMonto(montoGasto)) {
        advertencias.push(`- El total del PDF (${formatoMonto(totalOcr)}) no coincide con el monto del gasto (${formatoMonto(montoGasto)}). Revisa el dato capturado; se guardará el monto que ingresó el usuario.`);
    }

    if (!fechaGasto) {
        advertencias.push('- No se pudo revisar la fecha capturada. Revisa que esté en formato DD/MM/AAAA.');
    } else if (!fechaOcr) {
        advertencias.push('- El OCR no encontró fecha en el PDF para comparar.');
    } else if (fechaOcr !== fechaGasto) {
        advertencias.push(`- La fecha del PDF (${formatoFecha(fechaOcr)}) no coincide con la fecha capturada (${formatoFecha(fechaGasto)}).`);
    }

    if (uuidParaGuardar) {
        if (uuidYaExisteEnSolicitud(uuidParaGuardar)) {
            errores.push('- El folio fiscal del PDF ya está agregado en otro gasto de esta solicitud.');
        } else {
            const disponibilidad = await checkCfdiUuidAvailability(uuidParaGuardar);
            if (!disponibilidad.is_available) {
                errores.push('- El folio fiscal del PDF ya está registrado en otro gasto.');
            }
        }
    }

    if (errores.length) {
        throw new Error([
            `La factura PDF del gasto no coincide con el gasto capturado:`,
            ...errores,
        ].join('\n'));
    }

    return advertencias;
}

function validarResultadoDocumentoSimpleOcr(parsed, monto, fecha, etiquetaDocumento) {
    const etiqueta = etiquetaDocumento.toLowerCase();
    const errores = [];
    const advertencias = [];
    const montoGasto = Number(monto);
    const totalOcr = parsed.extracted_total === null || parsed.extracted_total === undefined
        ? null
        : Number(parsed.extracted_total);
    const fechaGasto = normalizarFechaCapturada(fecha);
    const fechaOcr = normalizarFechaCfdi(parsed.extracted_date);

    if (totalOcr === null || Number.isNaN(totalOcr)) {
        advertencias.push(`- El OCR no encontró total en el ${etiqueta}. Se usará el monto capturado por el usuario.`);
    } else if (redondearMonto(totalOcr) !== redondearMonto(montoGasto)) {
        advertencias.push(`- El total del ${etiqueta} (${formatoMonto(totalOcr)}) no coincide con el monto del gasto (${formatoMonto(montoGasto)}). Revisa el dato capturado; se guardará el monto que ingresó el usuario.`);
    }

    if (!fechaGasto) {
        advertencias.push('- No se pudo revisar la fecha capturada. Revisa que esté en formato DD/MM/AAAA.');
    } else if (!fechaOcr) {
        advertencias.push(`- El OCR no encontró fecha en el ${etiqueta} para comparar.`);
    } else if (fechaOcr !== fechaGasto) {
        advertencias.push(`- La fecha del ${etiqueta} (${formatoFecha(fechaOcr)}) no coincide con la fecha capturada (${formatoFecha(fechaGasto)}).`);
    }

    if (errores.length) {
        throw new Error([
            `El ${etiqueta} no coincide con el gasto capturado:`,
            ...errores,
        ].join('\n'));
    }

    return advertencias;
}

function resultadoMontoDocumentoSimpleOcr(parsed, monto) {
    const totalOcr = parsed?.extracted_total === null || parsed?.extracted_total === undefined
        ? null
        : Number(parsed.extracted_total);
    if (totalOcr === null || Number.isNaN(totalOcr)) {
        return 'no_detectado';
    }
    if (redondearMonto(totalOcr) !== redondearMonto(Number(monto))) {
        return 'diferente';
    }
    return 'coincide';
}

function mensajeBaseDocumentoSimpleOcr(etiquetaMinuscula, resultadoMonto, fueReutilizado) {
    if (resultadoMonto === 'no_detectado') {
        return fueReutilizado
            ? `OCR ya leído para este ${etiquetaMinuscula}. No encontró monto; se usará el monto capturado.`
            : `OCR completado para el ${etiquetaMinuscula}. No encontró monto; se usará el monto capturado.`;
    }
    if (resultadoMonto === 'diferente') {
        return fueReutilizado
            ? `OCR ya leído para este ${etiquetaMinuscula}. Detectó un monto diferente; revisa el dato capturado.`
            : `OCR completado para el ${etiquetaMinuscula}. Detectó un monto diferente; revisa el dato capturado.`;
    }

    return fueReutilizado
        ? `OCR ya leído para este ${etiquetaMinuscula}. El monto coincide.`
        : `OCR completado para el ${etiquetaMinuscula}. El monto coincide.`;
}

function esErrorDeLecturaOcr(mensaje) {
    const texto = String(mensaje || '').toLowerCase();
    return (
        texto.includes('ocr')
        || texto.includes('textract')
        || texto.includes('folio fiscal')
        || texto.includes('pdf')
        || texto.includes('leer')
        || texto.includes('legible')
    );
}

function datosOcrParaBorrador(parsed, file, validacion = {}) {
    return {
        ...parsed,
        fileName: file?.name || '',
        fileSize: file?.size || 0,
        fileLastModified: file?.lastModified || 0,
        validatedAmount: montoParaValidacion(validacion.monto),
        validatedCfdiUuid: normalizarUuidLocal(validacion.folio || parsed?.suggested_cfdi_uuid),
    };
}

function ocrCoincideConArchivoActual(ocr, file) {
    if (!ocr || !file) return false;
    return (
        ocr.fileName === file.name &&
        ocr.fileSize === file.size &&
        ocr.fileLastModified === file.lastModified
    );
}

function cfdiDesdeOcr(ocr, folioConfirmado = null) {
    return {
        uuid: normalizarUuidLocal(folioConfirmado) || ocr?.suggested_cfdi_uuid || null,
        subtotal: null,
        total: ocr?.extracted_total ?? null,
        currency: 'MXN',
        tax_amount: null,
        tax_rate: null,
        issued_at: ocr?.extracted_date || null,
    };
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

function crearGastoParaValidacion({
    categoria,
    monto,
    folio,
    fecha,
    observaciones,
    cfdiParsed,
    facturaFile,
    valeFile,
    facturaRequiereOcr = false,
    ocrValidado = false,
}) {
    return {
        id: `validacion-${Date.now()}`,
        nombre: `Gasto - ${categoria}`,
        monto: parseFloat(monto) || 0,
        tipo: categoria,
        folio,
        fecha,
        observaciones,
        cfdiUuid: normalizarUuidLocal(cfdiParsed.uuid),
        cfdiSubtotal: numeroOculto(cfdiParsed.subtotal),
        cfdiTotal: cfdiParsed.total,
        cfdiCurrency: cfdiParsed.currency,
        cfdiTaxAmount: numeroOculto(cfdiParsed.tax_amount),
        cfdiTaxRate: numeroOculto(cfdiParsed.tax_rate),
        facturaRequiereOcr,
        ocrValidado,
        facturaFile,
        valeFile,
    };
}

function validarSolicitudDespuesDeAnadir(gastos) {
    const activos = gastos.filter(esGastoActivo);
    const errores = [];

    const sinEvidenciaValida = activos.filter((gasto) => !gastoTieneEvidenciaValida(gasto));
    if (sinEvidenciaValida.length) {
        errores.push(`Todos los gastos activos deben tener un comprobante válido. Falta evidencia válida en ${sinEvidenciaValida.length} gasto(s).`);
    }

    const cfdisDuplicados = obtenerCfdisDuplicados(activos);
    if (cfdisDuplicados.length) {
        errores.push(`No debe haber CFDI duplicado. UUID repetido: ${cfdisDuplicados.join(', ')}.`);
    }

    if (errores.length) {
        throw new Error([
            'No se puede añadir el gasto porque la solicitud quedaría con errores:',
            ...errores,
        ].join('\n'));
    }
}

function esGastoActivo(gasto) {
    if (!gasto) return false;
    if (gasto.deletedAt || gasto.deleted_at || gasto.removedAt || gasto.removed_at) return false;

    const estado = String(gasto.backendStatus || gasto.backend_status || gasto.status || gasto.estado || '')
        .trim()
        .toLowerCase();
    return !['deleted', 'removed', 'rejected', 'eliminado', 'no autorizado', 'no_autorizado'].includes(estado);
}

function gastoTieneCfdiValido(gasto) {
    const uuid = cfdiUuidDesdeGasto(gasto);
    const moneda = String(gasto.cfdiCurrency || gasto.cfdi_currency || 'MXN').trim().toUpperCase();
    const archivoFacturaValida = gasto.facturaFile
        ? esXml(gasto.facturaFile) || (esPdf(gasto.facturaFile) && Boolean(gasto.ocrValidado))
        : Boolean(uuid || gastoTieneDocumentoGuardado(gasto, 'factura'));

    return Boolean(uuid || gastoTieneDocumentoGuardado(gasto, 'factura')) && moneda === 'MXN' && archivoFacturaValida;
}

function esGastoConFactura(gasto) {
    return !['vale', 'recibo'].includes(
        String(gasto?.tipoDocumento || gasto?.tipo_documento || '').trim().toLowerCase(),
    );
}

function gastoTieneEvidenciaValida(gasto) {
    if (!esGastoConFactura(gasto)) {
        const tipoDocumento = String(gasto.tipoDocumento || gasto.tipo_documento || '').trim().toLowerCase();
        const archivo = tipoDocumento === 'vale' ? gasto.valeFile : gasto.reciboFile;
        return Boolean((archivo && esPdf(archivo)) || gastoTieneDocumentoGuardado(gasto, tipoDocumento));
    }
    return gastoTieneCfdiValido(gasto);
}

function gastoTieneDocumentoGuardado(gasto, tipoDocumento) {
    const tipo = String(tipoDocumento || '').trim().toLowerCase();
    const urlFactura = gasto.urlFactura || gasto.url_factura;
    const urlVale = gasto.urlVale || gasto.url_vale;
    const urlRecibo = gasto.urlRecibo || gasto.url_recibo;
    const urlDescarga = gasto.downloadUrl || gasto.download_url || gasto.urlGasto || gasto.url_gasto;

    if (tipo === 'vale') return Boolean(urlVale || gasto.documentoGuardadoEnBackend);
    if (tipo === 'recibo') return Boolean(urlRecibo || gasto.documentoGuardadoEnBackend);
    return Boolean(urlFactura || urlDescarga || gasto.documentoGuardadoEnBackend);
}

function obtenerCfdisDuplicados(gastos) {
    const vistos = new Set();
    const duplicados = new Set();

    gastos.forEach((gasto) => {
        const uuid = cfdiUuidDesdeGasto(gasto);
        if (!uuid) return;
        if (vistos.has(uuid)) {
            duplicados.add(uuid);
        }
        vistos.add(uuid);
    });

    return Array.from(duplicados);
}

function cfdiUuidDesdeGasto(gasto) {
    const uuidFiscal = normalizarUuidLocal(
        gasto?.cfdiUuid || gasto?.cfdi_uuid || gasto?.folioFiscal || gasto?.folio_fiscal
    );
    if (uuidFiscal) return uuidFiscal;
    if (!esGastoConFactura(gasto)) return null;

    const folioManual = normalizarUuidLocal(gasto?.folio);
    if (!folioManual || ['N/A', 'OCR PENDIENTE'].includes(folioManual)) return null;
    return folioManual;
}

function normalizarUuidLocal(value) {
    return value ? String(value).trim().toUpperCase() : null;
}

function montoParaValidacion(value) {
    const numero = Number(value);
    if (Number.isNaN(numero)) return '';
    return redondearMonto(numero);
}

function mensajeConAdvertencias(mensaje, advertencias = []) {
    if (!advertencias.length) return mensaje;
    return [
        mensaje,
        '',
        'Advertencia:',
        ...advertencias,
    ].join('\n');
}

function estadoParaAdvertencias(advertencias = []) {
    return advertencias.length ? 'advertencia' : 'listo';
}

function normalizarFechaCapturada(value) {
    const texto = String(value || '').trim();
    const fechaConDiaPrimero = texto.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
    if (fechaConDiaPrimero) {
        const [, day, month, year] = fechaConDiaPrimero;
        return fechaIsoValida(year, month, day);
    }

    const fechaIso = texto.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (fechaIso) {
        const [, year, month, day] = fechaIso;
        return fechaIsoValida(year, month, day);
    }

    return null;
}

function normalizarFechaCfdi(value) {
    const texto = String(value || '').trim();
    const fechaIso = texto.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (!fechaIso) return null;

    const [, year, month, day] = fechaIso;
    return fechaIsoValida(year, month, day);
}

function fechaIsoValida(year, month, day) {
    const yyyy = Number(year);
    const mm = Number(month);
    const dd = Number(day);

    if (!yyyy || !mm || !dd) return null;

    const fecha = new Date(Date.UTC(yyyy, mm - 1, dd));
    if (
        fecha.getUTCFullYear() !== yyyy ||
        fecha.getUTCMonth() !== mm - 1 ||
        fecha.getUTCDate() !== dd
    ) {
        return null;
    }

    return `${String(yyyy).padStart(4, '0')}-${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`;
}

function formatoFecha(value) {
    const [year, month, day] = String(value || '').split('-');
    return [day, month, year].filter(Boolean).join('/');
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

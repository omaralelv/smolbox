import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

import Drawer from '../../components/shared/Drawer';
import {
    apiErrorMessage, currentStoredRole, currentToken, listHistoricalStores, ensureHistoricalDraft,
    getHistoricalRequest, registerHistoricalRequest, deleteHistoricalExpense, getHistoricalEvents,
    addHistoricalObservation, downloadProtectedFile, historicalZipUrl,
} from '../../lib/api';
import { newAuditId } from '../../lib/captureAuditQueue';
import {
    combinarHistorialObservaciones, historialDesdeEventos, historialParaGasto,
    mensajeErrorHistorial, observacionInicialDesdeGasto, puedeAgregarObservacion,
} from '../../lib/observationHistory';

function SolExtemp({ currentRole }) {
    const navigate = useNavigate();
    const location = useLocation();
    const { requestId } = useParams();
    const rol = String(currentRole || currentStoredRole() || '').toLowerCase();
    const puedeCapturar = ['admin', 'contabilidad'].includes(rol);
    const [stores, setStores] = useState([]);
    const [selectedStoreId, setSelectedStoreId] = useState(location.state?.selectedStoreId || '');
    const [request, setRequest] = useState(null);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const busyRef = useRef(false);
    const [error, setError] = useState('');
    const [documentoActivo, setDocumentoActivo] = useState(null);
    const [observacionesAbiertas, setObservacionesAbiertas] = useState(false);
    const [gastoSeleccionado, setGastoSeleccionado] = useState(null);
    const [comentario, setComentario] = useState('');
    const [historial, setHistorial] = useState([]);
    const [errorHistorial, setErrorHistorial] = useState('');
    const [guardandoObservacion, setGuardandoObservacion] = useState(false);
    const pendingObservation = useRef(null);
    const sendingObservation = useRef(false);
    const archived = Boolean(requestId || request?.backendStatus === 'historical_paid');
    const gastos = request?.gastos || [];

    useEffect(() => {
        if (!currentToken()) { navigate('/login'); return undefined; }
        if (requestId) return undefined;
        if (!puedeCapturar) return undefined;
        let active = true;
        listHistoricalStores().then((data) => {
            if (!active) return;
            setStores(data);
            setSelectedStoreId((current) => data.some((store) => store.id === current) ? current : data[0]?.id || '');
            if (!data.length) { setError('No hay tiendas con una asignación activa de Tienda.'); setLoading(false); }
        }).catch((cause) => { if (active) { setError(apiErrorMessage(cause)); setLoading(false); } });
        return () => { active = false; };
    }, [navigate, puedeCapturar, requestId]);

    useEffect(() => {
        if (!requestId && (!selectedStoreId || !puedeCapturar || !stores.length)) return undefined;
        let active = true;
        const operation = requestId ? getHistoricalRequest(requestId) : ensureHistoricalDraft(selectedStoreId);
        operation.then((data) => { if (active) setRequest(data); })
            .catch((cause) => { if (active) { setRequest(null); setError(apiErrorMessage(cause)); } })
            .finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, [requestId, selectedStoreId, puedeCapturar, stores]);

    useEffect(() => {
        if (!request?.backendId) return undefined;
        let active = true;
        getHistoricalEvents(request.backendId).then((events) => {
            if (!active) return;
            setHistorial(combinarHistorialObservaciones(
                request.gastos.map(observacionInicialDesdeGasto).filter(Boolean), historialDesdeEventos(events),
            ));
            setErrorHistorial('');
        }).catch(() => { if (active) setErrorHistorial(mensajeErrorHistorial()); });
        return () => { active = false; };
    }, [request]);

    const refreshHistory = async (saved = false) => {
        try {
            const events = await getHistoricalEvents(request.backendId);
            setHistorial(combinarHistorialObservaciones(
                gastos.map(observacionInicialDesdeGasto).filter(Boolean), historialDesdeEventos(events),
            ));
            setErrorHistorial('');
        } catch { setErrorHistorial(mensajeErrorHistorial(saved)); }
    };

    const sendObservation = async (event) => {
        event.preventDefault();
        const note = comentario.trim();
        if (!note || !gastoSeleccionado || sendingObservation.current) return;
        sendingObservation.current = true;
        setGuardandoObservacion(true);
        const expenseId = gastoSeleccionado.backendId;
        const key = `${expenseId}:${note}`;
        if (pendingObservation.current?.key !== key) pendingObservation.current = { key, eventId: newAuditId() };
        try {
            await addHistoricalObservation(expenseId, note, pendingObservation.current.eventId);
            pendingObservation.current = null;
            setComentario('');
            await refreshHistory(true);
        } catch (cause) { setErrorHistorial(apiErrorMessage(cause)); }
        finally { sendingObservation.current = false; setGuardandoObservacion(false); }
    };

    const removeExpense = async (expense) => {
        if (busyRef.current || !window.confirm(`¿Eliminar ${expense.nombre}?`)) return;
        busyRef.current = true;
        setBusy(true);
        try { setRequest(await deleteHistoricalExpense(expense.backendId)); }
        catch (cause) { setError(apiErrorMessage(cause)); }
        finally { busyRef.current = false; setBusy(false); }
    };

    const submit = async () => {
        if (!request || !gastos.length || busyRef.current) return;
        busyRef.current = true;
        setBusy(true);
        setError('');
        try {
            const result = await registerHistoricalRequest(request.backendId, gastos.map((expense) => expense.backendId));
            setRequest(result);
            alert(`Solicitud extemporánea ${result.folio} registrada en Histórico.`);
            navigate('/historico');
        } catch (cause) { setError(apiErrorMessage(cause)); }
        finally { busyRef.current = false; setBusy(false); }
    };

    if (!requestId && !puedeCapturar) return <p role="alert">No tienes permiso para capturar extemporáneos.</p>;

    return (
        <div style={styles.mainLayout} data-audit-historical-id={request?.backendId}>
            <div style={styles.container}>
                <div style={styles.titleRow}>
                    <h2 style={styles.mainTitle}>Solicitud Extemporánea</h2>
                    {!archived && puedeCapturar && <div style={styles.storeFilterGroup}>
                        <label style={styles.label} htmlFor="solicitud-store-select">Tienda activa</label>
                        <select id="solicitud-store-select" style={styles.storeSelect}
                            value={selectedStoreId} disabled={busy || guardandoObservacion || !stores.length}
                            onChange={(event) => {
                                setRequest(null); setLoading(Boolean(event.target.value)); setError('');
                                setGastoSeleccionado(null); setDocumentoActivo(null); setObservacionesAbiertas(false);
                                setSelectedStoreId(event.target.value);
                            }}>
                            <option value="">Selecciona una tienda</option>
                            {stores.map((store) => <option key={store.id} value={store.id}>{store.code} - {store.name}</option>)}
                        </select>
                    </div>}
                    {!archived && puedeCapturar && <button style={styles.añadirBtn}
                        disabled={loading || busy || guardandoObservacion || !request}
                        onClick={() => navigate('/gasto/extemporaneo', { state: { selectedStoreId } })}>Añadir Gasto</button>}
                    {archived && <button style={styles.cancelarBtn} disabled={!request || busy}
                        onClick={async () => {
                            setBusy(true);
                            try { await downloadProtectedFile(historicalZipUrl(request.backendId), `${request.folio}-comprobantes.zip`); }
                            catch (cause) { setError(apiErrorMessage(cause)); }
                            finally { setBusy(false); }
                        }}>Descargar comprobantes</button>}
                </div>
                {archived && request && <p style={{ overflowWrap: 'anywhere', textAlign: 'left' }}>{request.folio}</p>}
                {error && <p role="alert" style={styles.errorMessage}>{error}</p>}
                {loading && <p role="status" style={styles.loadingMessage}>Cargando solicitud...</p>}
                {request && !loading && <>
                    <div style={styles.gridAuto}>
                        {[['Fecha', request.fecha], ['Tienda', request.tienda], ['Gerente', request.gerente],
                            ['Cuenta bancaria', request.cuentaBancaria], ['Plaza', request.estadoRegion]].map(([label, value]) => (
                            <div key={label} style={styles.inputGroup}><label style={styles.label}>{label}</label>
                                <div style={styles.disabledInput}>{value || 'Por especificar'}</div></div>
                        ))}
                    </div>
                    <div style={{ overflowX: 'auto', width: '100%' }}>
                        <div style={{ ...styles.tableContainer, minWidth: '680px' }}>
                            <div style={styles.tableHeader}>
                                {['CONCEPTO', 'MONTO', 'TIPO DE GASTO', 'HERRAMIENTAS'].map((title) => (
                                    <span key={title} style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>{title}</span>
                                ))}
                            </div>
                            {gastos.map((expense) => <div key={expense.backendId} style={styles.tableRow}>
                                <span style={{ flex: 1.5, fontWeight: 'bold', overflowWrap: 'anywhere' }}>{expense.nombre}</span>
                                <span style={{ flex: 1.5, textAlign: 'center' }}>$ {Number(expense.monto).toFixed(2)}</span>
                                <span style={{ flex: 1.5, textAlign: 'center' }}>{expense.tipo}</span>
                                <div style={{ flex: 1.5, display: 'flex', justifyContent: 'center', gap: '8px' }}>
                                    <button style={styles.iconBtn} title="Ver Documento" onClick={() => {
                                        setGastoSeleccionado(expense); setDocumentoActivo('documento');
                                    }}><img src="/Factura.png" alt="Documento" style={styles.iconImg} /></button>
                                    <button style={styles.iconBtn} title="Observaciones" onClick={() => {
                                        setGastoSeleccionado(expense); setObservacionesAbiertas(true); setComentario('');
                                    }}><img src="/Observacion.png" alt="Observaciones" style={styles.iconImg} /></button>
                                    {!archived && <button style={styles.iconBtn} title="Eliminar gasto"
                                        disabled={busy} onClick={() => removeExpense(expense)}>
                                        <img src="/Eliminar.png" alt="Eliminar" style={styles.iconImg} /></button>}
                                </div>
                            </div>)}
                        </div>
                    </div>
                    <div style={styles.totalRow}><strong>TOTAL:</strong>
                        <strong>$ {Number(request.montoTotal).toFixed(2)}</strong></div>
                </>}
                <div style={{ ...styles.fixedStickyFooter,
                    right: `calc(${documentoActivo ? 'min(500px, 45vw)' : '0px'} + ${observacionesAbiertas ? 'min(320px, 35vw)' : '0px'} + ${documentoActivo || observacionesAbiertas ? '30px' : '0px'})`,
                }}><div style={styles.footerButtonsGroup}>
                    <button style={styles.cancelarBtn} disabled={busy} onClick={() => navigate('/historico')}>
                        {archived ? 'Regresar' : 'Cancelar'}
                    </button>
                    {!archived && puedeCapturar && <button style={styles.enviarSolicitudBtnFixed}
                        disabled={loading || busy || guardandoObservacion || !gastos.length} onClick={submit}>
                        {busy ? 'Enviando...' : 'Enviar Solicitud'}
                    </button>}
                </div></div>
            </div>
            <Drawer documentoActivo={documentoActivo} observacionesAbiertas={observacionesAbiertas}
                gasto={gastoSeleccionado} currentRole={rol}
                onCloseDocumento={() => setDocumentoActivo(null)} onCloseObservaciones={() => setObservacionesAbiertas(false)}
                comentario={comentario} setComentario={setComentario}
                historial={historialParaGasto(historial, gastoSeleccionado, rol)}
                onEnviarObservacion={sendObservation}
                puedeAgregarObservacion={!archived && puedeAgregarObservacion(gastoSeleccionado)}
                guardandoObservacion={guardandoObservacion} errorObservaciones={errorHistorial}
                onReintentarObservaciones={() => refreshHistory()} />
        </div>
    );
}

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
        gap: '16px',
        flexWrap: 'wrap',
        marginBottom: '30px',
    },
    storeFilterGroup: {
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
    },
    storeSelect: {
        minWidth: '240px',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
        fontSize: '14px',
    },
    errorMessage: {
        margin: '0 0 12px',
        color: '#b42318',
        fontSize: '14px',
    },
    loadingMessage: {
        margin: '0 0 12px',
        color: 'var(--text)',
        fontSize: '14px',
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
        letterSpacing: 0,
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
        right: 0,
        backgroundColor: 'var(--sb-subhead)', /* Usa el fondo blanco de tu index.css */
        boxShadow: '0 -4px 10px rgba(0, 0, 0, 0.05)', /* Una sombra sutil hacia arriba para separarlo del contenido */
        padding: '12px 0',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 1000, /* Se asegura de quedar por encima de las filas de los gastos */
        borderTop: '1px solid #fff0f0',
    },

    footerButtonsGroup: {
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: '15px',
        alignItems: 'center',
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
    },
    cancelarBtn: {
        backgroundColor: 'var(--sb-WBtnBg)',
        color: 'var(--text-WBtn)',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        padding: '10px 35px', /* Un poco más ancho para que destaque en la barra inferior */
        marginBottom: '8px',
        fontSize: '16px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
        transition: 'transform 0.1s ease',
    },
};


export default SolExtemp;

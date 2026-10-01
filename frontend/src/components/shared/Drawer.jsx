import { useEffect, useState } from 'react';

import { apiFileUrl, currentToken, fetchProtectedBlob } from '../../lib/api';

export default function Drawer({ 
    documentoActivo,      // 'factura' | 'vale' | 'recibo' | 'documento' | null
    observacionesAbiertas, // true | false
    gasto,                // Objeto del gasto seleccionado
    onCloseDocumento,     // Función para cerrar factura/vale
    onCloseObservaciones, // Función para cerrar observaciones
    comentario,           // Estado del texto escrito
    setComentario,        // Setter del texto
    historial,            // Array con el historial de comentarios
    onEnviarObservacion,   // Función al dar submit al comentario
    currentRole,
}) {
    const [documentoAmpliado, setDocumentoAmpliado] = useState(false);

    const rolNormalizado = String(currentRole).toLowerCase().trim();
    const documento = documentoActivo ? obtenerDocumento(gasto, documentoActivo) : null;
    const hayPanelAbierto = Boolean(documentoActivo || observacionesAbiertas);

    const tituloDocumento =
        documentoActivo === 'factura' ? 'Factura' :
        documentoActivo === 'vale' ? 'Vale' :
        documentoActivo === 'recibo' ? 'Gasto' :
        documentoActivo === 'documento' ? 'Documento' : '';

    useEffect(() => {
        setDocumentoAmpliado(false);
    }, [documentoActivo, documento]);

    if (!hayPanelAbierto) return null;

    return (
        <div style={styles.drawerWrapper}>
            
            {/* 1. SECCIÓN DE FACTURA / VALE */}
            {documentoActivo && (
                <div style={styles.panelDocumento}>
                    <div style={styles.header}>
                        <h3 style={styles.title}>
                            {tituloDocumento} {gasto?.nombre || gasto?.id || ''}
                        </h3>
                        <div style={styles.headerControls}>
                            {documento && (
                                <button
                                    type="button"
                                    title="Expandir"
                                    style={styles.iconBtn}
                                    onClick={() => setDocumentoAmpliado(true)}
                                >
                                    <img src="/Expand.png" alt="Expandir" style={styles.iconImg} />
                                </button>
                            )}
                            <button 
                                style={styles.closeBtn} 
                                onClick={onCloseDocumento}
                                title="Cerrar"
                                >
                                    ✕
                            </button>
                        </div>
                    </div>

                    <div style={styles.documentoBody}>
                        <DocumentoPreview
                            key={documentoKey(documentoActivo, documento)}
                            documento={documento}
                        />
                    </div>
                </div>
            )}

            {documentoActivo && documentoAmpliado && (
                <div style={styles.modalDocumentoOverlay}>
                    <div style={styles.modalDocumento}>
                        <div style={styles.modalDocumentoHeader}>
                            <h3 style={styles.title}>
                                {tituloDocumento} {gasto?.nombre || gasto?.id || ''}
                            </h3>
                            <button
                                type="button"
                                style={styles.closeBtn}
                                onClick={() => setDocumentoAmpliado(false)}
                            >
                                ✕
                            </button>
                        </div>
                        <div style={styles.modalDocumentoBody}>
                            <DocumentoPreview
                                key={`grande:${documentoKey(documentoActivo, documento)}`}
                                documento={documento}
                                ampliado
                            />
                        </div>
                    </div>
                </div>
            )}


            {/* 2. SECCIÓN DE OBSERVACIONES */}
            {observacionesAbiertas && (
                <div style={styles.panelObservaciones}>
                    <div style={styles.header}>
                        <h3 style={styles.title}>Observaciones {gasto?.nombre || gasto?.id || ''}</h3>
                        <button style={styles.closeBtn} onClick={onCloseObservaciones}>✕</button>
                    </div>

                    {/* Historial de comentarios */}
                    <div style={styles.chatBody}>
                        {historial && historial.map((obs) => {
                            const esMio = String(obs.rol || '').toLowerCase().trim() === rolNormalizado;
                            return (
                                <div 
                                    key={obs.id} 
                                    style={{
                                        ...styles.mensajeWrapper,
                                        alignItems: esMio ? 'flex-end' : 'flex-start'
                                    }}
                                >
                                    <span style={styles.autorLabel}>{obs.autor} - {obs.fecha}</span>

                                    {obs.visibilidad && (
                                            <span style={{
                                                ...styles.badgeVisibilidad,
                                                backgroundColor: obs.visibilidad === 'PUBLIC' ? '#e0f2fe' : '#fef3c7',
                                                color: obs.visibilidad === 'PUBLIC' ? '#0369a1' : '#b45309'
                                            }}>
                                                {obs.visibilidad}
                                            </span>
                                    )}


                                    <div style={{
                                        ...styles.globo,
                                        ...(esMio ? styles.globoMio : styles.globoOtro)
                                    }}>
                                        {obs.texto}
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Input para agregar comentario */}
                    <form style={styles.footer} onSubmit={onEnviarObservacion}>
                        <textarea
                            placeholder="Nueva observación..."
                            value={comentario}
                            onChange={(e) => setComentario(e.target.value)}
                            style={styles.textarea}
                        />
                        <button type="submit" style={styles.sendBtn}>
                            ➤
                        </button>
                    </form>
                </div>
            )}

        </div>
    );
}

function DocumentoPreview({ documento, ampliado = false }) {
    const [estado, setEstado] = useState(() => estadoInicialDocumento(documento));

    useEffect(() => {
        if (estado.revokeUrl) {
            return () => URL.revokeObjectURL(estado.url);
        }

        if (estado.status === 'local-xml') {
            let cancelado = false;

            estado.file.text()
                .then((texto) => {
                    if (cancelado) return;
                    setEstado({
                        status: 'xml',
                        xml: formatearXml(texto),
                        error: '',
                        revokeUrl: false,
                    });
                })
                .catch((error) => {
                    if (cancelado) return;
                    setEstado({
                        status: 'error',
                        url: null,
                        error: error.message || 'No se pudo abrir el XML.',
                        revokeUrl: false,
                    });
                });

            return () => {
                cancelado = true;
            };
        }

        if (estado.status !== 'protected') return undefined;

        let cancelado = false;
        let urlTemporal = null;
        let urlEntregadaAlEstado = false;
        const controller = new AbortController();

        fetchProtectedBlob(estado.fetchUrl, { signal: controller.signal })
            .then(async (blob) => {
                if (cancelado) return;
                if (esBlobXml(blob, estado.documento)) {
                    const texto = await blob.text();
                    if (cancelado) return;
                    setEstado({
                        status: 'xml',
                        xml: formatearXml(texto),
                        error: '',
                        revokeUrl: false,
                    });
                    return;
                }

                urlTemporal = URL.createObjectURL(blob);
                urlEntregadaAlEstado = true;
                setEstado({
                    status: 'ready',
                    url: urlTemporal,
                    error: '',
                    revokeUrl: true,
                });
            })
            .catch((error) => {
                if (cancelado || error.name === 'AbortError') return;
                setEstado({
                    status: 'error',
                    url: null,
                    error: error.message || 'No se pudo abrir el archivo.',
                    revokeUrl: false,
                });
            });

        return () => {
            cancelado = true;
            controller.abort();
            if (urlTemporal && !urlEntregadaAlEstado) {
                URL.revokeObjectURL(urlTemporal);
            }
        };
    }, [estado]);

    if (estado.status === 'loading' || estado.status === 'protected' || estado.status === 'local-xml') {
        return <div style={styles.documentoMensaje}>Cargando archivo...</div>;
    }
    if (estado.error) {
        return <div style={styles.documentoMensaje}>{estado.error}</div>;
    }
    if (estado.status === 'xml') {
        return (
            <pre style={{ ...styles.xmlPreview, ...(ampliado ? styles.xmlPreviewGrande : {}) }}>
                {estado.xml || 'El XML está vacío.'}
            </pre>
        );
    }
    if (!estado.url) {
        return <div style={styles.documentoMensaje}>No hay archivo para mostrar.</div>;
    }

    return (
        <iframe
            src={estado.url}
            title="Comprobante"
            style={{ ...styles.iframe, ...(ampliado ? styles.iframeGrande : {}) }}
        />
    );
}

function estadoInicialDocumento(documento) {
    if (!documento) {
        return {
            status: 'error',
            url: null,
            error: 'No hay archivo para mostrar.',
            revokeUrl: false,
        };
    }

    if (esArchivoLocal(documento)) {
        if (esDocumentoXml(documento)) {
            return {
                status: 'local-xml',
                file: documento,
                error: '',
                revokeUrl: false,
            };
        }

        return {
            status: 'ready',
            url: URL.createObjectURL(documento),
            error: '',
            revokeUrl: true,
        };
    }

    const url = apiFileUrl(documento);
    if (!url) {
        return {
            status: 'error',
            url: null,
            error: 'No hay archivo para mostrar.',
            revokeUrl: false,
        };
    }

    if (url.startsWith('blob:') || url.startsWith('data:')) {
        return {
            status: 'ready',
            url,
            error: '',
            revokeUrl: false,
        };
    }

    const token = currentToken();
    if (!token) {
        return {
            status: 'error',
            url: null,
            error: 'Inicia sesión para ver este archivo.',
            revokeUrl: false,
        };
    }

    return {
        status: 'protected',
        url: null,
        error: '',
        revokeUrl: false,
        fetchUrl: url,
        documento,
    };
}

function documentoKey(tipoDocumento, documento) {
    if (esArchivoLocal(documento)) {
        return [
            tipoDocumento,
            documento.name,
            documento.size,
            documento.lastModified,
        ].join(':');
    }

    return `${tipoDocumento || 'documento'}:${documento || 'sin-archivo'}`;
}

function obtenerDocumento(gasto, tipoDocumento) {
    if (!gasto) return null;

    if (tipoDocumento === 'documento') {
        return primerValor(
            gasto.facturaFile,
            gasto.urlFactura,
            gasto.facturaUrl,
            gasto.url_factura,
            gasto.valeFile,
            gasto.urlVale,
            gasto.valeUrl,
            gasto.url_vale,
            gasto.reciboFile,
            gasto.urlRecibo,
            gasto.reciboUrl,
            gasto.urlGasto,
            gasto.gastoUrl,
            gasto.url_recibo,
            gasto.url_gasto,
            gasto.downloadUrl,
            gasto.download_url
        );
    }

    if (tipoDocumento === 'factura') {
        return primerValor(
            gasto.facturaFile,
            gasto.urlFactura,
            gasto.facturaUrl,
            gasto.url_factura,
            gasto.downloadUrl,
            gasto.download_url
        );
    }

    if (tipoDocumento === 'vale') {
        return primerValor(
            gasto.valeFile,
            gasto.urlVale,
            gasto.valeUrl,
            gasto.url_vale
        );
    }

    if (tipoDocumento === 'recibo') {
        return primerValor(
            gasto.reciboFile,
            gasto.urlRecibo,
            gasto.reciboUrl,
            gasto.urlGasto,
            gasto.gastoUrl,
            gasto.url_recibo,
            gasto.url_gasto,
            gasto.downloadUrl,
            gasto.download_url
        );
    }

    return null;
}

function primerValor(...valores) {
    return valores.find((valor) => Boolean(valor)) || null;
}

function esArchivoLocal(valor) {
    return typeof File !== 'undefined' && valor instanceof File;
}

function esDocumentoXml(documento) {
    if (!documento) return false;
    if (esArchivoLocal(documento)) {
        return esNombreXml(documento.name) || String(documento.type || '').toLowerCase().includes('xml');
    }

    return esNombreXml(String(documento));
}

function esBlobXml(blob, documento) {
    return String(blob?.type || '').toLowerCase().includes('xml') || esDocumentoXml(documento);
}

function esNombreXml(nombre) {
    return String(nombre || '').toLowerCase().split('?')[0].endsWith('.xml');
}

function formatearXml(xml) {
    const texto = String(xml || '').trim();
    if (!texto) return '';

    try {
        const parser = new DOMParser();
        const document = parser.parseFromString(texto, 'application/xml');
        if (document.querySelector('parsererror')) return texto;
    } catch {
        return texto;
    }

    const lineas = texto
        .replace(/>\s*</g, '>\n<')
        .split('\n')
        .map((linea) => linea.trim())
        .filter(Boolean);
    let nivel = 0;

    return lineas.map((linea) => {
        if (/^<\//.test(linea)) {
            nivel = Math.max(nivel - 1, 0);
        }
        const formateada = `${'  '.repeat(nivel)}${linea}`;
        if (
            /^<[^!?/][^>]*[^/]?>$/.test(linea)
            && !linea.includes('</')
        ) {
            nivel += 1;
        }
        return formateada;
    }).join('\n');
}

const styles = {
    drawerWrapper: {
        display: 'flex',
        borderLeft: '1px solid #fecdd3',
        backgroundColor: '#ffffff',
        height: '100%',
        position: 'relative',
        boxSizing: 'border-box',
    },
    panelDocumento: {
        width: '500px',
        height: '100%',
        maxWidth: '45vw',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid #fecdd3',
        backgroundColor: '#ffffff',
    },
    panelObservaciones: {
        width: '320px',
        height: '100%',
        maxHeight: '100%',
        maxWidth: '35vw',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#ffffff',
        overflow: 'hidden',
        position: 'relative',
    },
    header: {
        padding: '9px 13px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid #fecdd3',
        flexShrink: 0,
    },
    title: {
        margin: 0,
        fontSize: '15px',
        fontWeight: 'bold',
        color: '#111827',
    },
    closeBtn: {
        background: 'none',
        border: 'none',
        fontSize: '16px',
        cursor: 'pointer',
        color: '#000000',
    },
    headerControls: {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexShrink: 0,
    },


    iconBtn: {
        background: 'none',
        border: '1px solid #000000',
        cursor: 'pointer',
        padding: 0,
        display: 'flex',
        alignItems: 'center',
        padding: '3px',
        borderRadius: '3px'
    },
    iconImg: {
        width: '13px',
        height: '13px',
        objectFit: 'contain'
    },


    ampliarBtn: {
        border: '1px solid #fecdd3',
        borderRadius: '16px',
        background: '#ffffff',
        color: '#9f5d68',
        padding: '4px 11px',
        fontSize: '12px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
    documentoBody: {
        flex: 1,
        backgroundColor: '#f9fafb',
    },
    documentoMensaje: {
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        color: '#6b7280',
        fontSize: '13px',
        textAlign: 'center',
    },
    iframe: {
        width: '100%',
        height: '100%',
        border: 'none',
    },
    iframeGrande: {
        backgroundColor: '#ffffff',
    },
    xmlPreview: {
        margin: 0,
        width: '100%',
        height: '100%',
        boxSizing: 'border-box',
        padding: '14px',
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        textAlign: 'left',
        backgroundColor: '#ffffff',
        color: '#000000',
        fontSize: '13px',
        lineHeight: '1.5',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    },
    xmlPreviewGrande: {
        fontSize: '14px',
    },
    modalDocumentoOverlay: {
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(17, 24, 39, 0.55)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '28px',
        boxSizing: 'border-box',
    },
    modalDocumento: {
        width: 'min(1180px, 96vw)',
        height: 'min(840px, 92vh)',
        backgroundColor: '#ffffff',
        border: '1px solid #fecdd3',
        boxShadow: '0 24px 70px rgba(17, 24, 39, 0.32)',
        display: 'flex',
        flexDirection: 'column',
    },
    modalDocumentoHeader: {
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #fecdd3',
        flexShrink: 0,
    },
    modalDocumentoBody: {
        flex: 1,
        minHeight: 0,
        backgroundColor: '#f9fafb',
    },
    chatBody: {
        flex: 1,
        padding: '10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        backgroundColor: 'var(--sb-subhead)',
        overflowY: 'auto',
    },
    mensajeWrapper: {
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '90%',
    },
    autorLabel: {
        fontSize: '10px',
        color: '#6b7280',
        marginBottom: '2px',
    },

    
    badgeVisibilidad: {
        fontSize: '9px',
        padding: '1px 4px',
        borderRadius: '3px',
        fontWeight: 'bold',
    },


    globo: {
        padding: '10px 12px',
        borderRadius: '10px',
        fontSize: '12px',
        lineHeight: '1.4',
        border: '1px solid #fecdd3',
    },
    globoMio: {
        backgroundColor: 'var(--sb-header)',
        color: '#ffffff',
        fontWeight: 'bold',
        boxShadow: 'var(--shadow)',
        border: '1px solid #ffffff',
    },
    globoOtro: {
        backgroundColor: '#ffffff',
        color: 'var(--text)',
        boxShadow: 'var(--shadow)'
    },
    footer: {
        position: 'relative',
        bottom: 0,
        left: 0,
        right: 0,
        width: '100%', // Toma exactamente el 100% de la tarjeta del drawer
        padding: '8px',
        background: '#ffffff',
        borderTop: '1px solid #fecdd3',
        display: 'flex',
        alignItems: 'center',
        boxSizing: 'border-box',
        flexShrink: 0,
    },
    textarea: {
        width: '100%',
        background:'#ffffff',
        height: '70px',
        borderRadius: '8px',
        border: '1px solid #fecdd3',
        padding: '8px 5px 8px 8px',
        fontSize: '12px',
        resize: 'none',
        outline: 'none',
        boxSizing: 'border-box',
        color: 'var(--text)',
    },
    sendBtn: {
        position: 'absolute',
        right: '13px',
        bottom: '13px',
        background: 'none',
        border: 'none',
        fontSize: '18px',
        cursor: 'pointer',
        color: 'var(--sb-sendBtnBg)',
    }
};

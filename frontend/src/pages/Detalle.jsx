import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import { apiErrorMessage, openProtectedFile, removeExpense } from '../lib/api';

import Drawer from '../components/shared/Drawer';


function Detalle({ currentRole }) {
    const navigate = useNavigate();
    const location = useLocation();


    // 1. ESTADOS PARA CONTROLAR LOS PANELES Y OBSERVACIONES
    const [documentoActivo, setDocumentoActivo] = useState(null); // 'factura' | 'vale' | null
    const [observacionesAbiertas, setObservacionesAbiertas] = useState(false);
    const [gastoSeleccionado, setGastoSeleccionado] = useState(null);
    const [eliminandoGastoId, setEliminandoGastoId] = useState(null);
    const [gastoParaEliminar, setGastoParaEliminar] = useState(null);
    const [motivoEliminacion, setMotivoEliminacion] = useState('');

    // Estado del chat de observaciones
    const [comentario, setComentario] = useState('');
    const [historial, setHistorial] = useState([
        {
            id: 1,
            autor: 'Contabilidad',
            rol: 'supervisor',
            texto: 'Modificación de impuesto de 16% a 8%. Artículos de limpieza para evento.',
            fecha: '10/08/2026 - 10:15 AM'
        }
    ]);

    

    // 1. RECUPERAR DATOS DE LA NAVEGACIÓN O USAR MOCK DE RESPALDO 
    const categoria = location.state?.categoria || 'Sistemas';
    const solicitudFolio = location.state?.solicitudFolio || 'Solicitud T-001';

    // Mock por si ingresas directo sin state
    const [gastosDesglosados, setGastosDesglosados] = useState(() => (
        location.state?.desglose?.length > 0
            ? filtrarGastosActivos(location.state.desglose)
            : [
            { 
                id: 1, 
                nombre: 'Gasto 1', 
                monto: 150.00, 
                folioFiscal: '5FB2822E-396D-4725-8521-CDC4BDD20CCF', 
                autorizacion: 'autorizado' // 'autorizado', 'no_autorizado', o ''
            },
            { 
                id: 2, 
                nombre: 'Gasto 2', 
                monto: 118.01, 
                folioFiscal: '467FE2EF-99E8-45CD-8E2F-F7C63D13847B', 
                autorizacion: '' 
            }
        ]
    ));

    // CÁLCULO DEL TOTAL DE LA CATEGORÍA
    const totalCategoria = gastosDesglosados
        .reduce((acc, curr) => acc + (parseFloat(curr.monto) || 0), 0)
        .toFixed(2);

    // 2. NORMALIZAR EL ROL
    const rol = String(currentRole || localStorage.getItem('currentRole') || 'admin').toLowerCase().trim();

    // 3. MATRIZ DE VISIBILIDAD DE ICONOS/HERRAMIENTAS SEGÚN EL ROL
    const visibilidadIconos = {
        vale: ['tienda', 'supervisor', 'contabilidad', 'gerencia', 'tesoreria', 'direccion', 'admin'],
        factura: ['tienda', 'supervisor', 'contabilidad', 'gerencia', 'tesoreria', 'direccion', 'admin'],
        observaciones: ['tienda', 'contabilidad', 'gerencia', 'tesoreria', 'direccion', 'admin'],
        editar: ['contabilidad', 'gerencia', 'admin'],
        eliminar: ['contabilidad', 'gerencia', 'admin']
    };

    const puedeVer = (herramienta) => visibilidadIconos[herramienta]?.includes(rol);



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

    const handleEnviarObservacion = (e) => {
        e.preventDefault();
        if (!comentario.trim()) return;

        const nueva = {
            id: Date.now(),
            autor: 'Tú',
            rol: 'supervisor',
            texto: comentario,
            fecha: new Date().toLocaleString()
        };

        setHistorial([...historial, nueva]);
        setComentario('');
    };






    const abrirArchivo = async (gasto) => {
        if (!gasto.downloadUrl) {
            alert('Este gasto no tiene archivo disponible para abrir.');
            return;
        }

        try {
            await openProtectedFile(gasto.downloadUrl);
        } catch (error) {
            alert(apiErrorMessage(error));
        }
    };

    const handleEliminarGasto = (gasto) => {
        const expenseId = gasto.backendId || gasto.id;

        if (!expenseId || typeof expenseId !== 'string') {
            alert('Este gasto no tiene ID de backend para eliminarse.');
            return;
        }

        setGastoParaEliminar(gasto);
        setMotivoEliminacion('');
    };

    const cancelarEliminacion = () => {
        setGastoParaEliminar(null);
        setMotivoEliminacion('');
    };

    const confirmarEliminacion = async () => {
        const expenseId = gastoParaEliminar?.backendId || gastoParaEliminar?.id;
        const cleanReason = motivoEliminacion.trim();

        if (!expenseId || typeof expenseId !== 'string') {
            alert('Este gasto no tiene ID de backend para eliminarse.');
            cancelarEliminacion();
            return;
        }

        if (!cleanReason) {
            alert('Necesitas escribir un motivo para eliminar el gasto.');
            return;
        }

        try {
            setEliminandoGastoId(expenseId);
            await removeExpense(expenseId, cleanReason);
            setGastosDesglosados((actuales) =>
                actuales.filter((item) => (item.backendId || item.id) !== expenseId)
            );

            if ((gastoSeleccionado?.backendId || gastoSeleccionado?.id) === expenseId) {
                setGastoSeleccionado(null);
                setDocumentoActivo(null);
                setObservacionesAbiertas(false);
            }

            alert('Gasto eliminado correctamente.');
            cancelarEliminacion();
        } catch (error) {
            alert(apiErrorMessage(error));
        } finally {
            setEliminandoGastoId(null);
        }
    };

    // 4. HELPER PARA MOSTRAR EL BADGE DE AUTORIZACIÓN
    const renderBadgeAutorizacion = (estatus) => {
        if (estatus === 'autorizado') {
            return <span style={styles.badgeAutorizado}>Autorizado</span>;
        }
        if (estatus === 'no_autorizado') {
            return <span style={styles.badgeNoAutorizado}>No Autorizado</span>;
        }
        return null; // Si no requiere autorización, se queda en blanco
    };



    // Evaluamos si ambos están abiertos para ocultar FOLIO FISCAL
    const ocultarFolio = documentoActivo && observacionesAbiertas;




    return (
        <div style={styles.mainLayout}>
            {/* VISTA PRINCIPAL (IZQUIERDA) */}
            <div style={styles.container}>
                {/* ENCABEZADO */}
                <div style={styles.headerRow}>
                    <h2 style={styles.title}>{solicitudFolio} / {categoria}</h2>
                    <button style={styles.regresarBtn} onClick={() => navigate(-1)}>
                        Regresar
                    </button>
                </div>


            {/* TABLA DE DESGLOSE */}
            <div style={styles.tableContainer}>

                {/* ENCABEZADO DE COLUMNAS */}
                <div style={styles.tableHeader}>
                    <span style={{ flex: 1.25}}></span>
                    <span style={{ flex: 1, textAlign: 'left', width: '30px', paddingLeft: '110px'}}>MONTO</span>

                    {/* OCULTAR ENCABEZADO DE FOLIO SI AMBOS PANELES ESTÁN ABIERTOS */}
                        {!ocultarFolio && (
                            <span style={{ flex: 1, textAlign: 'left', width: '20px', paddingRight: '5px'}}>FOLIO FISCAL</span>
                        )}

                    <span style={{ flex: 1, textAlign: 'left', paddingLeft: '10px',  }}>AUTORIZACION</span>
                    <span style={{ flex: 1, textAlign: 'right', paddingRight: '5px' }}>HERRAMIENTAS</span>
                </div>
                

                {/* FILAS DE GASTOS */}
                {gastosDesglosados.map((gasto, index) => {
                    const gastoKey = gasto.backendId || gasto.id || index;
                
                    return (

                    <div key={gastoKey} style={styles.tableRow}>
                        <span style={{ flex: 1.25, fontWeight: 'bold' , width: '30px', textAlign: 'left', paddingLeft: '0px'}}>
                            {gasto.nombre || `Gasto ${index + 1}`}
                        </span>

                        <span style={{ flex: 1, textAlign: 'center' , width: '50px', paddingLeft: '120px'}}>
                            {parseFloat(gasto.monto || 0).toFixed(2)}
                        </span>


                        {/* OCULTAR CELDA DE FOLIO SI AMBOS PANELES ESTÁN ABIERTOS */}
                            {!ocultarFolio && (
                                <span style={{ flex: 1, fontSize: '12px', wordBreak: 'break-all', paddingLeft: 50 }}>
                                    {gasto.folioFiscal || gasto.folio || 'N/A'}
                                </span>
                            )}



                        <span style={{ flex: 1, textAlign: 'right',  paddingLeft: '50px', width: '100px' }}>AUTORIZACION</span>




                        {/* BOTONES DE HERRAMIENTAS (ICONOS) */}
                        <div style={styles.herramientasContainer}>
                            {puedeVer('vale') && (
                                <button style={styles.iconBtn} title="Ver Vale" onClick={() => handleVerVale(gasto)}>
                                    <img src="/Vale.png" alt="Vale" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('factura') && (
                                <button style={styles.iconBtn} title="Ver Factura" onClick={() => handleVerFactura(gasto)}>
                                    <img src="/Factura.png" alt="Factura" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('observaciones') && (
                                <button style={styles.iconBtn} title="Observaciones" onClick={() => handleToggleObservaciones(gasto)}>
                                    <img src="/Observacion.png" alt="Observaciones" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('editar') && (
                                <button style={styles.iconBtn} title="Editar Gasto">
                                    <img src="/Editar.png" alt="Editar" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('eliminar') && (
                                <button
                                    style={{
                                        ...styles.iconBtn,
                                        opacity: eliminandoGastoId === gastoKey ? 0.5 : 1,
                                    }}
                                    title="Eliminar Gasto"
                                    onClick={() => handleEliminarGasto(gasto)}
                                    disabled={eliminandoGastoId === gastoKey}
                                >
                                    <img src="/Eliminar.png" alt="Eliminar" style={styles.iconImg} />
                                </button>
                            )}
                        </div>
                    </div>
                )})}
            </div>

            {/* TOTAL FINAL DE LA CATEGORÍA */}
            <div style={styles.totalRow}>
                <span style={{flex: 1, fontWeight: 'bold', fontSize: '14px', textAlign: 'left'}}>
                    TOTAL {categoria.toUpperCase()}:
                </span>
                <span style={{flex: 3, fontWeight: 'bold', fontSize: '14px', marginLeft: '80px', textAlign: 'left' }}>
                    {totalCategoria}
                </span>
            </div>
        </div>


        {/* PANEL DERECHO (DRAWER INTEGRADOR) */}
            <Drawer 
                documentoActivo={documentoActivo}
                observacionesAbiertas={observacionesAbiertas}
                gasto={gastoSeleccionado}
                onCloseDocumento={() => setDocumentoActivo(null)}
                onCloseObservaciones={() => setObservacionesAbiertas(false)}
                comentario={comentario}
                setComentario={setComentario}
                historial={historial}
                onEnviarObservacion={handleEnviarObservacion}
            />
            {gastoParaEliminar && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modal}>
                        <h3 style={styles.modalTitle}>Eliminar gasto</h3>
                        <p style={styles.modalText}>
                            Escribe el motivo para eliminar {gastoParaEliminar.nombre || 'este gasto'}.
                        </p>
                        <textarea
                            value={motivoEliminacion}
                            onChange={(event) => setMotivoEliminacion(event.target.value)}
                            style={styles.modalTextarea}
                            placeholder="Motivo de eliminación"
                            autoFocus
                        />
                        <div style={styles.modalActions}>
                            <button
                                type="button"
                                style={styles.modalCancelBtn}
                                onClick={cancelarEliminacion}
                                disabled={Boolean(eliminandoGastoId)}
                            >
                                Cancelar
                            </button>
                            <button
                                type="button"
                                style={styles.modalDeleteBtn}
                                onClick={confirmarEliminacion}
                                disabled={Boolean(eliminandoGastoId)}
                            >
                                {eliminandoGastoId ? 'Eliminando...' : 'Eliminar'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
        
    );
}

const styles = {
    mainLayout: {
        display: 'flex',
        width: '100%',
        height: 'calc(100vh - 160px)', 
        overflow: 'hidden',
    },

    container: {
        flex: 1,
        maxWidth: '1130px',
        margin: '0 auto',
        padding: '20px',
        fontFamily: 'sans-serif',
        overflowY: 'auto',
    },

    headerRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px'
    },
    title: {
        fontSize: '20px',
        color: '#333',
        fontWeight: 'bold'
    },
    regresarBtn: {
        border: '1px solid var(--sb-btnBorder)',
        background: '#fff',
        color: 'var(--text-WBtn)',
        borderRadius: '20px',
        padding: '6px 20px',
        cursor: 'pointer',
        fontSize: '13px',
        fontWeight: 'bold',
        boxShadow: 'var(--shadow)',
    },
    tableContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '4px'
    },
    tableHeader: {
        display: 'flex',
        fontSize: '13px',
        fontWeight: 'bold',
        color: '#000',
        padding: '10px 10px',
        textTransform: 'uppercase'
    },
    tableRow: {
        display: 'flex',
        alignItems: 'center',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        padding: '7px 13px',
        backgroundColor: '#fff',
        fontSize: '13px',
        color: '#333'
    },
    badgeAutorizado: {
        backgroundColor: 'var(--sb-pagadaBg)',
        color: 'var(--text-pagada)',
        fontSize: '11px',
        padding: '3px 10px',
        borderRadius: '12px',
        fontWeight: 'bold'
    },
    badgeNoAutorizado: {
        backgroundColor: 'var(--sb-denegadaBg)',
        color: 'var(--text-denegada)',
        fontSize: '11px',
        padding: '3px 10px',
        borderRadius: '12px',
        fontWeight: 'bold'
    },
    herramientasContainer: {
        flex: 2,
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        gap: '13px'
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
        marginTop: '25px',
        paddingLeft: '25px',
        display: 'flex',
        alignItems: 'center'
    },
    modalOverlay: {
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.35)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
    },
    modal: {
        width: 'min(420px, calc(100vw - 40px))',
        backgroundColor: '#fff',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        boxShadow: 'var(--shadow)',
        padding: '22px',
    },
    modalTitle: {
        margin: '0 0 8px',
        fontSize: '18px',
        color: 'var(--text-h)',
    },
    modalText: {
        margin: '0 0 14px',
        fontSize: '14px',
        color: '#444',
    },
    modalTextarea: {
        width: '100%',
        minHeight: '90px',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '14px',
        resize: 'vertical',
        boxSizing: 'border-box',
    },
    modalActions: {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '10px',
        marginTop: '16px',
    },
    modalCancelBtn: {
        border: '1px solid var(--sb-btnBorder)',
        backgroundColor: '#fff',
        color: 'var(--text-WBtn)',
        borderRadius: '20px',
        padding: '7px 18px',
        cursor: 'pointer',
        fontWeight: 'bold',
    },
    modalDeleteBtn: {
        border: '1px solid var(--sb-btnBorder)',
        background: 'var(--gradient)',
        color: 'var(--text-CBtn)',
        borderRadius: '20px',
        padding: '7px 18px',
        cursor: 'pointer',
        fontWeight: 'bold',
    }
};

export default Detalle;

function filtrarGastosActivos(gastos) {
    return gastos.filter((gasto) => {
        const backendStatus = String(gasto.backendStatus || gasto.backend_status || '').toLowerCase();
        const status = String(gasto.status || '').toLowerCase();
        return backendStatus !== 'removed' && status !== 'eliminado';
    });
}

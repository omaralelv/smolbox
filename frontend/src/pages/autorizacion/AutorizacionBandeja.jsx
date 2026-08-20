import React, { useState } from 'react';

// Datos de prueba maquetados (Mock Data)
const GASTOS_MOCK = [
    { id: 1, nombre: 'Gasto 1', tienda: 'T001', tipo: 'Sistemas', estado: 'Pendiente' },
    { id: 2, nombre: 'Gasto 2', tienda: 'T006', tipo: 'Sistemas', estado: 'Pendiente' },
    { id: 3, nombre: 'Gasto 3', tienda: 'T212', tipo: 'Papelería', estado: 'Autorizada' },
    { id: 4, nombre: 'Gasto 4', tienda: 'T124', tipo: 'Alimentos', estado: 'No Autorizada' },
];

function AutorizacionBandeja() {
    //const navigate = useNavigate();
    
    const [gastos, setGastos] = useState(GASTOS_MOCK);

    // Inicializamos con LocalStorage o Fallback Base
    //const [gastos, setGastos] = useState(() => {
    //    const guardados = localStorage.getItem('autorizacionGastos');
    //    return guardados ? JSON.parse(guardados) : GASTOS_MOCK;
    //});

    // Función pura de UI para cambiar el estatus al dar clic en los botones
    const handleCambiarEstado = (id, nuevoEstado) => {
        setGastos(prevGastos =>
            prevGastos.map(gasto =>
                gasto.id === id ? { ...gasto, estado: nuevoEstado } : gasto
            )
        );
    };

    // Helper para pintar el pill/tag de estado según su valor
    const renderEstadoBadge = (estado) => {
        switch (estado) {
            case 'Autorizada':
                return <span style={{ ...styles.badge, ...styles.badgeAutorizada }}>Autorizada</span>;
            case 'No Autorizada':
                return <span style={{ ...styles.badge, ...styles.badgeNoAutorizada }}>No Autorizada</span>;
            case 'Pendiente':
            default:
                return <span style={{ ...styles.badge, ...styles.badgePendiente }}>Pendiente</span>;
        }
    };

    return (
        <div style={styles.container}>
            {/* ENCABEZADOS DE LA TABLA */}
            <div style={styles.tableHeader}>
                <span style={{ flex: 1.5 }}></span>
                <span style={{ flex: 1, textAlign: 'center', fontWeight: 'bold' }}>TIENDA</span>
                <span style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>TIPO DE GASTO</span>
                <span style={{ flex: 1.5, textAlign: 'center', fontWeight: 'bold' }}>¿AUTORIZADO?</span>
                <span style={{ flex: 2.5, textAlign: 'center', fontWeight: 'bold' }}>HERRAMIENTAS</span>
            </div>

            {/* LISTA DE FILAS DE GASTOS */}
            <div style={styles.listContainer}>
                {gastos.map((gasto) => (
                    <div key={gasto.id} style={styles.rowCard}>
                        {/* NOMBRE DEL GASTO */}
                        <div style={{ flex: 1.5, paddingLeft: '20px', fontWeight: '500', color: '#333' }}>
                            {gasto.nombre}
                        </div>

                        {/* TIENDA */}
                        <div style={{ flex: 1, textAlign: 'center', color: '#444' }}>
                            {gasto.tienda}
                        </div>

                        {/* TIPO DE GASTO */}
                        <div style={{ flex: 1.5, textAlign: 'center', color: '#444' }}>
                            {gasto.tipo}
                        </div>

                        {/* ESTATUS VISUAL */}
                        <div style={{ flex: 1.5, display: 'flex', justifyContent: 'center' }}>
                            {renderEstadoBadge(gasto.estado)}
                        </div>

                        {/* ACCIONES / BOTONES DE CAMBIO DE ESTATUS Y HERRAMIENTAS */}
                        <div style={styles.actionsContainer}>
                            {gasto.estado === 'Pendiente' ? (
                                <>
                                    <button
                                        style={styles.btnAutorizar}
                                        onClick={() => handleCambiarEstado(gasto.id, 'Autorizada')}
                                    >
                                        AUTORIZAR
                                    </button>
                                    <button
                                        style={styles.btnNoAutorizar}
                                        onClick={() => handleCambiarEstado(gasto.id, 'No Autorizada')}
                                    >
                                        NO AUTORIZAR
                                    </button>
                                </>
                            ) : (
                                <div style={{ minWidth: '220px' }}></div> // Espaciador para mantener alineación
                            )}

                            {/* ICONO DE DOCUMENTO / COMPROBANTE */}
                            <button 
                                style={styles.iconBtn} 
                                title="Ver Vale" 
                                onClick={() => abrirArchivo(gasto, 'vale')}
                            >
                                <img src="/Vale.png" alt="Vale" style={styles.iconImg} />
                            </button>

                            <button 
                                style={styles.iconBtn} 
                                title="Ver Factura" 
                                onClick={() => abrirArchivo(gasto, 'factura')}
                            >
                                <img src="/Factura.png" alt="Factura" style={styles.iconImg} />
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ESTILOS EN OBJETO CSS-IN-JS
const styles = {
    container: {
        maxWidth: '1100px',
        margin: '20px auto',
        padding: '0 10px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
    },
    tableHeader: {
        display: 'flex',
        alignItems: 'center',
        padding: '12px 16px',
        marginBottom: '10px',
        fontSize: '14px',
        color: '#111',
    },
    listContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '5px',
    },
    rowCard: {
        display: 'flex',
        alignItems: 'center',
        backgroundColor: 'var(--bg)',
        border: '1px solid var(--border)', // Borde rosa idéntico a la imagen
        borderRadius: '10px',
        padding: '2px 10px',
        fontSize: '13px',
        boxShadow: '0 2px 4px var(--shadow)',
    },
    // BADGES DE ESTATUS
    badge: {
        padding: '4px 16px',
        borderRadius: '6px',
        fontSize: '13px',
        fontWeight: '500',
        display: 'inline-block',
        textAlign: 'center',
    },
    badgePendiente: {
        backgroundColor: 'var(--sb-revisionBg)',
        color: 'var(--text-revision)',
    },
    badgeAutorizada: {
        backgroundColor: 'var(--sb-pagadaBg)',
        color: 'var(--text-pagada)',
    },
    badgeNoAutorizada: {
        backgroundColor: 'var(--sb-denegadaBg)',
        color: 'var(--text-denegada)',
    },
    // ACCIONES
    actionsContainer: {
        flex: 2.5,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: '10px',
        paddingRight: '15px',
    },
    btnAutorizar: {
        backgroundColor: 'var(--text-pagada)', // Verde
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '6px',
        padding: '6px 14px',
        fontSize: '11px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
    btnNoAutorizar: {
        backgroundColor: 'var(--text-denegada)', // Naranja
        color: 'var(--text-CBtn)',
        border: 'none',
        borderRadius: '6px',
        padding: '6px 14px',
        fontSize: '11px',
        fontWeight: 'bold',
        cursor: 'pointer',
    },
    herramientasContainer: {
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginLeft: '8px',
    },
    iconBtn: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: '2px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    iconImg: {
        width: '20px',
        height: '20px',
        objectFit: 'contain',
    },
};

export default AutorizacionBandeja;
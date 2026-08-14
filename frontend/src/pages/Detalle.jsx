import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

function Detalle({ currentRole }) {
    const navigate = useNavigate();
    const location = useLocation();

    // 1. RECUPERAR DATOS DE LA NAVEGACIÓN O USAR MOCK DE RESPALDO (Basado en tu imagen)
    const categoria = location.state?.categoria || 'Sistemas';
    const solicitudFolio = location.state?.solicitudFolio || 'Solicitud T-001';

    // Mock por si ingresas directo sin state
    const gastosDesglosados = location.state?.desglose?.length > 0
        ? location.state.desglose
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
        ];

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



    return (
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
                    <span style={{ flex: 1, textAlign: 'left', width: '30px', textAlign: 'left', paddingLeft: '110px'}}>MONTO</span>
                    <span style={{ flex: 1, textAlign: 'left' , width: '20px', textAlign: 'left', paddingLeft: '0px'}}>FOLIO FISCAL</span>
                    <span style={{ flex: 1, textAlign: 'left', paddingLeft: '10px',  }}>AUTORIZACION</span>
                    <span style={{ flex: 1, textAlign: 'right', paddingRight: '5px' }}>HERRAMIENTAS</span>
                </div>
                

                {/* FILAS DE GASTOS */}
                {gastosDesglosados.map((gasto, index) => {
                    console.log("Objeto gasto completo:", gasto);
                
                    return (

                    <div key={gasto.id || index} style={styles.tableRow}>
                        <span style={{ flex: 1.25, fontWeight: 'bold' , width: '30px', textAlign: 'left', paddingLeft: '0px'}}>
                            {gasto.nombre || `Gasto ${index + 1}`}
                        </span>

                        <span style={{ flex: 1, textAlign: 'center' , width: '50px', paddingLeft: '120px'}}>
                            {parseFloat(gasto.monto || 0).toFixed(2)}
                        </span>

                        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0px', textAlign: 'center' , width: '400px', paddingLeft: '50px'}}>
                            <span>{gasto.folio || 'N/A'}</span>
                            {renderBadgeAutorizacion(gasto.autorizacion)}
                        </div>

                        <span style={{ flex: 1, textAlign: 'right',  paddingLeft: '50px', width: '100px' }}>AUTORIZACION</span>

                        {/* BOTONES DE HERRAMIENTAS (ICONOS) */}
                        <div style={styles.herramientasContainer}>
                            {puedeVer('vale') && (
                                <button style={styles.iconBtn} title="Ver Vale">
                                    <img src="/Vale.png" alt="Vale" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('factura') && (
                                <button style={styles.iconBtn} title="Ver Factura">
                                    <img src="/Factura.png" alt="Factura" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('observaciones') && (
                                <button style={styles.iconBtn} title="Observaciones">
                                    <img src="/Observacion.png" alt="Observaciones" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('editar') && (
                                <button style={styles.iconBtn} title="Editar Gasto">
                                    <img src="/Editar.png" alt="Editar" style={styles.iconImg} />
                                </button>
                            )}
                            {puedeVer('eliminar') && (
                                <button style={styles.iconBtn} title="Eliminar Gasto">
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
    );
}

const styles = {
    container: {
        maxWidth: '1130px',
        margin: '0 auto',
        padding: '20px',
        fontFamily: 'sans-serif'
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
    }
};

export default Detalle;
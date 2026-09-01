import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { currentToken, getFrontendBandeja } from '../lib/api';

const SOLICITUDES_BASE = [
    { id: 'Solicitud 3', tienda: 'T-001', fecha: '12/08/2026', status: 'Aprobada' },
    { id: 'Solicitud 2', tienda: 'T-001', fecha: '10/08/2026', status: 'Pagada' },
    { id: 'Solicitud 1', tienda: 'T-001', fecha: '10/08/2026', status: 'Pagada' }
];



function obtenerEstadoAlerta(solicitud, currentRole) {
    const solicitudBackendId = solicitud?.backendId || solicitud?.reimbursementRequestId || solicitud?.id;
    //if (!solicitudBackendId) return { esDevuelto: false, esResuelto: false };
    const queueStatus = solicitud?.accountingQueueStatus || solicitud?.accounting_queue_status || 'single';

    // Recuperar motivos/devuelto guardados en localStorage
    let motivosPorRol = {};
    let devueltoPor = '';
    let devueltoPorOriginal = '';

    if(solicitudBackendId) {
        // Recuperar información guardada por Acumulado.jsx
        const motivosPorRolRaw = localStorage.getItem(`motivos_map_${solicitudBackendId}`);
        motivosPorRol = motivosPorRolRaw ? JSON.parse(motivosPorRolRaw) : {};
        
        devueltoPor = localStorage.getItem(`devuelto_por_${solicitudBackendId}`) || solicitud?.devueltoPor || '';
        devueltoPorOriginal = localStorage.getItem(`devuelto_por_orig_${solicitudBackendId}`) || solicitud?.devueltoPorOriginal || devueltoPor;
    }
    
    const currentBackendStatus = solicitud?.backendStatus || solicitud?.backend_status || '';

    // Regla 1: Evaluador de Devuelto (AMARILLO)
    const esDevueltoBase = Boolean(
        Object.keys(motivosPorRol).length && 
        (
            (currentRole === 'contabilidad' && ['gerencia', 'tesoreria'].includes(devueltoPorOriginal)) ||
            (currentRole === 'gerencia' && devueltoPor === 'tesoreria')
        )
    );

    // Regla 2: Evaluador de Resuelto (VERDE)
    const esResueltoBase = Boolean(
        Object.keys(motivosPorRol).length && 
        (
            (devueltoPor === 'gerencia' && currentRole === 'gerencia' && ['accounting_reviewed', 'accounting_manager_review'].includes(currentBackendStatus)) ||
            (devueltoPorOriginal === 'tesoreria' && currentRole === 'tesoreria' && ['accounting_manager_approved', 'treasury_review'].includes(currentBackendStatus))
        )
    );

    // Ocultar banderas si ya avanzó de Tesorería en adelante
    const ocultarBanner = ['direction_review', 'direction_approved', 'approved_for_payment', 'paid', 'closed', 'rejected'].includes(currentBackendStatus);

    let esDevuelto = !ocultarBanner && esDevueltoBase;
    let esResuelto = !ocultarBanner && esResueltoBase;


    // 🎯 REGLAS EXCLUSIVAS PARA CONTABILIDAD
    if (currentRole === 'contabilidad') {
        // Si la tomó otro contador, anula cualquier color o alerta devuelta para este usuario
        if (queueStatus === 'taken_other') {
            return {
                esDevuelto: false,
                esResuelto: false,
                queueStatus: 'taken_other',
            };
        }

        // Si la solicitud está devuelta Y fue tomada por el perfil activo (taken),
        // prevalece el estado de devuelto en amarillo para este contador.
        if (queueStatus === 'taken' && esDevuelto) {
            return {
                esDevuelto: true,
                esResuelto: false,
                queueStatus: 'taken',
            };
        }
    }

    return {
        esDevuelto,
        esResuelto,
        queueStatus,
    };
}



function Bandeja({currentRole}) {
    const navigate = useNavigate();
    const [filtroTienda, setFiltroTienda] = useState('todas');
    const [solicitudes, setSolicitudes] = useState(() => {
        const guardadas = localStorage.getItem('bandejaSolicitudes');
        return guardadas ? JSON.parse(guardadas) : SOLICITUDES_BASE;
    });


    useEffect(() => {
        let activo = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                activo = false;
            };
        }

        getFrontendBandeja()
            .then((datos) => {
                if (!activo) return;
                setSolicitudes(datos);
                localStorage.setItem('bandejaSolicitudes', JSON.stringify(datos));
            })
            .catch(() => {
                if (!activo) return;
                const guardadas = localStorage.getItem('bandejaSolicitudes');
                setSolicitudes(guardadas ? JSON.parse(guardadas) : SOLICITUDES_BASE);
            });

        return () => {
            activo = false;
        };
    }, [currentRole, navigate]);


    const obtenerTienda = (solicitud) => solicitud.tienda || 'T-001';

    const tiendasDisponibles = Array.from(
        new Set(solicitudes.map((solicitud) => obtenerTienda(solicitud)))
    ).sort();

    const baseFiltrada = filtroTienda === 'todas'
        ? solicitudes
        : solicitudes.filter((solicitud) => obtenerTienda(solicitud) === filtroTienda);

    // Ordenamos situando las alertas (Devuelto/Resuelto) arriba
    const solicitudesFiltradas = [...baseFiltrada].sort((a, b) => {
        const alertaA = obtenerEstadoAlerta(a, currentRole);
        const alertaB = obtenerEstadoAlerta(b, currentRole);


        // Asignación de pesos para priorizar el renderizado
        // 1: Devueltas/Resueltas o Asignadas a mí (taken)
        // 2: Estado base (single)
        // 3: Tomadas por alguien más (taken_other)
        const getPeso = (alerta) => {
            if (alerta.queueStatus === 'taken_other') return 3;
            if (alerta.esDevuelto || alerta.esResuelto || alerta.queueStatus === 'taken') return 1;
            return 2;
        };
        //const pesoA = (alertaA.esDevuelto || alertaA.esResuelto) ? 1 : 2;
        //const pesoB = (alertaB.esDevuelto || alertaB.esResuelto) ? 1 : 2;

        return getPeso(alertaA) - getPeso(alertaB);
    });

  // Función para asignar colores exactos a cada Badge
    const getBadgeStyle = (status) => {
    switch (status) {
        case 'Aprobada':
            return {
                backgroundColor: 'var(--sb-aprobadaBg, #e6f7ff)',
                color: 'var(--text-aprobada, #1890ff)'
            };
        case 'Pagada':
            return {
                backgroundColor: 'var(--sb-pagadaBg, #e6ffe6)',
                color: 'var(--text-pagada, #52c41a)'
            };
        case 'En revisión':
        default:
            return {
                backgroundColor: 'var(--sb-revisionBg, #f2f2f2)',
                color: 'var(--text-revision, #777777)'
            };
        case 'Rechazada':
            return{
                backgroundColor: 'var(--sb-denegadaBg)',
                color: 'var(--text-denegada)',
            };
    }
    };

    return (
    <div style={styles.container}>
            <div style={styles.filtersRow}>
                <label style={styles.filterLabel}>
                    Tienda
                    <select
                        value={filtroTienda}
                        onChange={(event) => setFiltroTienda(event.target.value)}
                        style={styles.filterSelect}
                    >
                        <option value="todas">Todas</option>
                        {tiendasDisponibles.map((tienda) => (
                            <option key={tienda} value={tienda}>
                                {tienda}
                            </option>
                        ))}
                    </select>
                </label>
            </div>

        {/* ENCABEZADOS DE LA TABLA */}
            <div style={styles.tableHeader}>
                <span style={{ flex: 1.5, textAlign: 'left', paddingLeft: '50px' }}></span>
                <span style={{ flex: 1, textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '9px' }}>
                    TIENDA 
                    <svg width="12" height="12" viewBox="0 0 25 24" fill="currentColor">
                        <path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/>
                    </svg>
                </span>
                <span style={{ flex: 1, textAlign: 'center' }}>FECHA ENVÍO</span>
                <span style={{ flex: 1, textAlign: 'center' }}>ESTATUS</span>
                <span style={{ width: '100px' }}></span>
            </div>


        {/* LISTA DE FILAS DE SOLICITUDES */}
            <div style={styles.listContainer}>
                {solicitudesFiltradas.length === 0 ? (
                    <div style={styles.emptyState}>
                        No hay solicitudes para la tienda seleccionada.
                    </div>
                ) : (solicitudesFiltradas.map((sol) => {
                    const { esDevuelto, esResuelto, queueStatus } = obtenerEstadoAlerta(sol, currentRole);

                    // Definición de estilos condicionales para la fila
                    let rowStyle = { ...styles.row };
                    let textoEstatus = sol.status;
                    let badgeStyleOverride = {};

                    // 1. REGLA: Devuelta (Amarillo) - Prevalece si es devuelta y tomada por mí
                    if (esDevuelto) {
                        rowStyle = {
                            ...styles.row,
                            backgroundColor: '#fffbe6', // Fondo amarillo
                            borderColor: '#fac61d',     // Borde amarillo
                        };
                        textoEstatus = 'Devuelta';
                        badgeStyleOverride = {
                            backgroundColor: '#ffe693',
                            color: '#c17a00',
                            fontWeight: 'bold',
                        };
                    } 

                    // 2. REGLA: Resuelta (Verde)
                    else if (esResuelto) {
                        rowStyle = {
                            ...styles.row,
                            backgroundColor: '#f4ffec', // Fondo verde
                            borderColor: '#66d809',     // Borde verde
                        };
                        textoEstatus = 'Resuelta';
                        badgeStyleOverride = {
                            backgroundColor: '#cffeb8',
                            color: '#2e9a00',
                            fontWeight: 'bold',
                        };
                    }

                    // 3. REGLA CONTABILIDAD: Taken por otro contador (Grisáceo Opaco)
                    else if (currentRole === 'contabilidad' && queueStatus === 'taken_other') {
                        rowStyle = {
                            ...styles.row,
                            backgroundColor: '#fcf3f3', // Gris suave opaco
                            backgroundColor: '#f1e9e9', // Gris suave opaco
                            borderColor: '#ceb8b8',
                            color: '#e7d8d8',
                            opacity: 0.6,            // Baja opacidad para dar a entender que está ocupado
                        };
                        textoEstatus = 'Ajeno';
                        badgeStyleOverride = {
                            backgroundColor: '#957878',
                            color: '#ede2e2',
                            fontWeight: 'bold',
                        };
                    }

                    // 4. REGLA CONTABILIDAD: Taken por el perfil activo (Rosa Pastel)
                    else if (currentRole === 'contabilidad' && queueStatus === 'taken') {
                        rowStyle = {
                            ...styles.row,
                            backgroundColor: '#fff5f6', // Rosa pastel delicado
                            borderColor: '#f38c98',     // Borde rosa suave

                            
                            
                        };
                        textoEstatus = 'Propio';
                        badgeStyleOverride = {
                            backgroundColor: '#ffdaf9',
                            color: '#af1e9e',
                            fontWeight: 'bold',

                            
                        }
                    };
                    
                    return (
                        <div key={sol.id} style={rowStyle}>
                            {/* 1. Nombre / ID Solicitud */}
                            <span style={{ flex: 1.5, textAlign: 'left', paddingLeft: '30px', fontWeight: '500', color: '#333' }}>
                                {sol.id}
                            </span>

                            {/* 2. Tienda */}
                            <span style={{ flex: 1, textAlign: 'center', color: '#444' }}>
                                {obtenerTienda(sol)}
                            </span>

                            {/* 3. Fecha de Envío */}
                            <span style={{ flex: 1, textAlign: 'center', color: '#444' }}>
                                {sol.fecha || new Date().toLocaleDateString()}
                            </span>

                            {/* 4. Pill / Badge de Estatus */}
                            <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                                <span style={{ 
                                    ...styles.statusBadge, 
                                    ...getBadgeStyle(sol.status),
                                    ...badgeStyleOverride 
                                }}>
                                    {textoEstatus}
                                </span>
                            </div>

                            {/* 5. Botón Abrir */}
                            <div style={{ width: '100px', textAlign: 'center' }}>
                                <button 
                                    style={styles.abrirBtn}
                                    onClick={() => navigate('/acumulado', { state: { solicitud: sol } })}
                                >
                                    Abrir
                                </button>
                            </div>
                        </div>
                    );
                })

                )}
            </div>

        </div>
    );
}

// 🎨 ESTILOS ALINEADOS A LA NUEVA MAQUETA
const styles = {
    container: {
        maxWidth: '1250px',
        margin: '0 auto',
        padding: '30px 20px',
        textAlign: 'left',
    },
    filtersRow: {
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        marginBottom: '16px',
    },
    filterLabel: {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '13px',
        fontWeight: '700',
        color: '#333',
    },
    filterSelect: {
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        backgroundColor: '#ffffff',
        color: '#333',
        fontSize: '13px',
        padding: '7px 10px',
        minWidth: '120px',
    },
    tableHeader: {
        display: 'flex',
        alignItems: 'center',
        padding: '0 10px 12px 10px',
        fontSize: '13px',
        fontWeight: '700',
        color: '#000000',
        letterSpacing: '0.5px',
    },
    listContainer: {
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
    },
    row: {
        display: 'flex',
        alignItems: 'center',
        backgroundColor: '#ffffff',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        padding: '7px 10px',
        fontSize: '13px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.02)',
    },
    statusBadge: {
        padding: '4px 0px',
        borderRadius: '12px',
        fontSize: '13px',
        fontWeight: '400',
        display: 'inline-block',
        minWidth: '82px',
        textAlign: 'center',
    },
    abrirBtn: {
        backgroundColor: 'transparent',
        border: 'none',
        color: 'var(--text-WBtn)',
        fontWeight: 'bold',
        fontSize: '13px',
        cursor: 'pointer',
    },
    emptyState: {
        textAlign: 'center',
        padding: '20px',
        color: '#666',
        fontSize: '13px',
    }
};

export default Bandeja;

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { currentToken, getFrontendHistorico } from '../lib/api';
import { requestAgeDisplay } from '../lib/requestAge';
import {
    normalizarFechaSolicitud,
    obtenerFechaSolicitud,
    puedeFiltrarSolicitudes,
} from '../lib/requestFilters';

const HISTORICO_CACHE_KEY = 'historicoSolicitudes';
const BANDEJA_CACHE_KEY = 'bandejaSolicitudes';

const SOLICITUDES_BASE = [
    { id: 'Solicitud 3', tienda: 'T-001', fecha: '12/08/2026', status: 'Pagada' },
    { id: 'Solicitud 2', tienda: 'T-001', fecha: '10/08/2026', status: 'Pagada' },
    { id: 'Solicitud 1', tienda: 'T-001', fecha: '10/08/2026', status: 'Pagada' }
];

function formatearMonto(monto) {
    const valor = Number(monto) || 0;
    return new Intl.NumberFormat('es-MX', {
        style: 'currency',
        currency: 'MXN',
    }).format(valor);
}

function Historico({currentRole}) {
    const navigate = useNavigate();
    const [filtroTienda, setFiltroTienda] = useState('todas');
    const [filtroFecha, setFiltroFecha] = useState('');

    const [filtroExtemporaneo, setFiltroExtemporaneo] = useState('todas'); // 'todas' | 'extemporaneas' | 'normales'

    const [solicitudes, setSolicitudes] = useState(() => {
        const guardadas = localStorage.getItem(HISTORICO_CACHE_KEY) || localStorage.getItem(BANDEJA_CACHE_KEY);
        const lista = guardadas ? JSON.parse(guardadas) : SOLICITUDES_BASE;
        return lista.filter(esSolicitudHistorica);
    });


    useEffect(() => {
        let activo = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                activo = false;
            };
        }

        getFrontendHistorico()
            .then((datos) => {
                if (!activo) return;
                const historicas = Array.isArray(datos)
                ? datos.filter(esSolicitudHistorica) : []

                setSolicitudes(historicas);
                localStorage.setItem(HISTORICO_CACHE_KEY, JSON.stringify(historicas));
            })
            .catch(() => {
                if (!activo) return;
                const guardadas = localStorage.getItem(HISTORICO_CACHE_KEY) || localStorage.getItem(BANDEJA_CACHE_KEY);
                const listaFallback = guardadas ? JSON.parse(guardadas) : SOLICITUDES_BASE;
                setSolicitudes(listaFallback.filter(esSolicitudHistorica));
            });

        return () => {
            activo = false;
        };
    }, [currentRole, navigate]);


    // Lógica para el filtro por tienda idéntica a Bandeja.jsx
    const obtenerTienda = (solicitud) => solicitud.tienda || 'T-001';

    const solicitudesDelDia = filtroFecha
        ? solicitudes.filter((solicitud) => normalizarFechaSolicitud(obtenerFechaSolicitud(solicitud)) === filtroFecha)
        : solicitudes;

    const tiendasDisponibles = Array.from(
        new Set(solicitudesDelDia.map((solicitud) => obtenerTienda(solicitud)))
    ).sort();


    // Filtrado seguro de históricas + filtro por tienda seleccionada
    const solicitudesHistoricas = solicitudesDelDia.filter(esSolicitudHistorica);

    //const solicitudesFiltradas = filtroTienda === 'todas'
    //    ? solicitudesHistoricas
    //    : solicitudesHistoricas.filter((sol) => obtenerTienda(sol) === filtroTienda);

    const solicitudesFiltradas = solicitudesHistoricas.filter((sol) => {
        const coincideTienda = filtroTienda === 'todas' || obtenerTienda(sol) === filtroTienda;
        
        // =========================================================================================
        // 🌟🌟🌟 LÓGICA DE FILTRADO PARA EXTEMPORÁNEAS 🌟🌟🌟
        // =========================================================================================
        const esExt = Boolean(sol.esExtemporaneo || sol.es_extemporaneo);
        let coincideExtemporaneo = true;
        if (filtroExtemporaneo === 'extemporaneas') {
            coincideExtemporaneo = esExt;
        } else if (filtroExtemporaneo === 'normales') {
            coincideExtemporaneo = !esExt;
        }

        return coincideTienda && coincideExtemporaneo;
    });


  // Función para asignar colores exactos a cada Badge
    const getBadgeStyle = (status) => {
        if (String(status || '').toLowerCase() === 'rechazada') {
            return {
                backgroundColor: 'var(--sb-denegadaBg, #fff1e6)',
                color: 'var(--text-denegada, #d46b08)'
            };
        }
        return {
            backgroundColor: 'var(--sb-pagadaBg, #e6ffe6)',
            color: 'var(--text-pagada, #52c41a)'
        };
    };

    const rolActualLimpio = String(currentRole || '').toLowerCase().trim();
    const mostrarBotonExtemporaneo = ['admin', 'contabilidad'].includes(rolActualLimpio);
    
    return (
        <div style={styles.container}>

            <div style={styles.topActionsRow}>
                <div>
                    {mostrarBotonExtemporaneo && (
                        <button
                            type="button"
                            onClick={() => navigate('/solicitud/extemporanea', { state: { extemporaneo: true } })}
                            style={styles.btnAñadirExtemporaneo}
                        >
                            + Solicitud Extemporánea
                        </button>
                    )}
                </div>

                {/* FILTRO DE TIENDA */}
                {puedeFiltrarSolicitudes(currentRole) && (
                    <div style={styles.filtersRow}>
                        {(filtroFecha || filtroTienda !== 'todas') && (
                            <button
                                type="button"
                                onClick={() => {
                                    setFiltroFecha('');
                                    setFiltroTienda('todas');
                                }}
                                style={styles.clearDateFilter}
                            >
                                Quitar filtros
                            </button>
                        )}
                        <label style={styles.filterLabel}>
                            Fecha Envío
                            <input
                                type="date"
                                value={filtroFecha}
                                onClick={(event) => event.target.showPicker && event.target.showPicker()}
                                onChange={(event) => {
                                    const nuevaFecha = event.target.value;
                                    setFiltroFecha(nuevaFecha);
                                    if (
                                        nuevaFecha
                                        &&
                                        filtroTienda !== 'todas'
                                        && !solicitudes.some((solicitud) => (
                                            normalizarFechaSolicitud(obtenerFechaSolicitud(solicitud)) === nuevaFecha
                                            && obtenerTienda(solicitud) === filtroTienda
                                        ))
                                    ) {
                                        setFiltroTienda('todas');
                                    }
                                }}
                                style={styles.selectCal}
                            />
                        </label>

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

                        <label style={styles.filterLabel}>
                            Tipo
                            <select
                                value={filtroExtemporaneo}
                                onChange={(event) => setFiltroExtemporaneo(event.target.value)}
                                style={styles.filterSelect}
                            >
                                <option value="todas">Todas</option>
                                <option value="extemporaneas">Solo Extemporáneas</option>
                                <option value="normales">Solo Normales</option>
                            </select>
                        </label>
                    </div>
                )}
            </div>

            <div style={styles.tableScroll} data-request-age-table>
            <div style={styles.tableContent}>

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
                <span style={styles.ageColumn}>DÍAS</span>
                <span style={{ flex: 1, textAlign: 'center' }}>¿EXTEMPORÁNEO?</span>
                <span style={{ flex: 1, textAlign: 'center' }}>MONTO</span>
                <span style={{ flex: 1, textAlign: 'center' }}>ESTATUS</span>
                <span style={{ width: '100px' }}></span>
            </div>


            {/* LISTA DE FILAS DE SOLICITUDES */}
            <div style={styles.listContainer}>
                {solicitudesFiltradas.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                        No hay solicitudes registradas en el histórico.
                    </div>
                ) : (solicitudesFiltradas.map((sol) => {
                    const montoTotal = sol.totalAmount ?? sol.total_amount ?? sol.monto ?? sol.montoTotal ?? 0;
                    const esExt = Boolean(sol.esExtemporaneo || sol.es_extemporaneo);
                    const age = requestAgeDisplay(sol);
                    return (
                        <div
                            key={sol.id}
                            style={styles.row}
                            data-audit-request-id={sol.backendId || sol.backend_id || undefined}
                        >
                            {/* 1. Nombre / ID Solicitud */}
                            <span style={{ flex: 1.5, minWidth: 0, overflowWrap: 'anywhere', textAlign: 'left', paddingLeft: '30px', fontWeight: '500', color: '#333' }}>
                                {sol.id}
                            </span>

                            {/* 2. Tienda */}
                            <span style={{ flex: 1, textAlign: 'center', color: '#444' }}>
                                {sol.tienda || 'T-001'}
                            </span>

                            {/* 3. Fecha de Envío */}
                            <span style={{ flex: 1, textAlign: 'center', color: '#444' }}>
                                {sol.fecha || new Date().toLocaleDateString()}
                            </span>

                            {/*<span style={styles.ageColumn} title={age.title}
                                aria-label={age.title} data-request-age={sol.backendId || sol.id}>
                                {age.label}
                            </span>*/}

                            {/* 4. Días desde Envío hasta Pago */}
                            <span style={styles.ageColumn} title={esExt ? 'No aplica temporalidad' : age.title}
                                aria-label={age.title} data-request-age={sol.backendId || sol.id}>
                                {esExt ? '-' : age.label}
                            </span>

                            {/* 5. ¿Extemporáneo? */}
                            <span style={{ flex: 1, textAlign: 'center', color: '#666', fontWeight: esExt ? '700' : 'normal' }}>
                                {esExt ? 'Extemporánea' : ''}
                            </span>

                            {/* 6. Monto Total */}
                            <span style={{ flex: 1, textAlign: 'center', color: '#333', fontWeight: '700' }}>
                                {formatearMonto(montoTotal)}
                            </span>

                            {/* 7. Pill / Badge de Estatus */}
                            <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                                <span style={{ ...styles.statusBadge, ...getBadgeStyle(sol.status || sol.estatus) }}>
                                    {sol.status}
                                </span>
                            </div>

                            {/* 8. Botón / Acción Abrir */}
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
            </div>

        </div>
    );
}

// 🎨 ESTILOS ALINEADOS A LA NUEVA MAQUETA
const styles = {
    container: {
        maxWidth: '1450px',
        margin: '0 auto',
        padding: '30px 20px',
        textAlign: 'left',
        width: '95%',
        boxSizing: 'border-box'
    },

    topActionsRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '25px',
    },

    btnAñadirExtemporaneo: {
        backgroundColor: 'var(--sb-sendBtnBg)',
        color: '#ffffff',
        border: 'none',
        borderRadius: '20px',
        padding: '10px 15px',
        fontSize: '14px',
        fontWeight: '700',
        cursor: 'pointer',
        boxShadow: 'var(--shadow)',
    },

    filtersRow: {
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        gap: '16px',
        flexWrap: 'wrap',
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


    selectCal: {
        minWidth: '100px',
        height: '35px',
        border: '1px solid var(--border, #f3c6cc)',
        borderRadius: '8px',
        background: '#fff',
        color: '#333',
        padding: '0 12px',
        fontSize: '14px',

        // Forzar el tema claro para el calendario desplegable nativo
        colorScheme: 'light',

        // Cambiar el color de acento/selección (puedes usar el rosa corporativo o el tono que gustes)
        accentColor: 'var(--sb-sendBtnBg)',

        cursor: 'pointer',
    },

    clearDateFilter: {
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '20px',
        backgroundColor: 'var(--sb-sendBtnBg)',
        color: '#ffffff',
        padding: '7px 10px',
        fontSize: '13px',
        fontWeight: '700',
        cursor: 'pointer',
    },

    tableScroll: { width: '100%', overflowX: 'auto', paddingBottom: '6px' },
    tableContent: { minWidth: '820px' },
    ageColumn: { flex: '0 0 88px', textAlign: 'center', fontVariantNumeric: 'tabular-nums' },
    tableHeader: {
        display: 'flex',
        alignItems: 'center',
        padding: '0 10px 12px 10px',
        fontSize: '13px',
        fontWeight: '700',
        color: '#000000',
        letterSpacing: 0,
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
    }
};

export default Historico;

function esSolicitudHistorica(solicitud) {
    const status = String(solicitud?.status || solicitud?.estatus || '').toLowerCase();
    return status === 'pagada' || status === 'rechazada';
}

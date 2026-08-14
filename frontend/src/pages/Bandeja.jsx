import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';


// Solicitudes base si es la primera vez que se entra
const SOLICITUDES_BASE = [
    { id: 'Solicitud 3', tienda: 'T-001', fecha: '12/08/2026', status: 'Aprobada' },
    { id: 'Solicitud 2', tienda: 'T-001', fecha: '10/08/2026', status: 'Pagada' },
    { id: 'Solicitud 1', tienda: 'T-001', fecha: '10/08/2026', status: 'Pagada' }
];

function Bandeja({currentRole}) {
    const navigate = useNavigate();
    const [solicitudes, setSolicitudes] = useState(() => {
        const guardadas = localStorage.getItem('bandejaSolicitudes');
        return guardadas ? JSON.parse(guardadas) : SOLICITUDES_INICIALES;
    });


    useEffect(() => {
        // Leemos la bandeja del localStorage
        const guardadas = localStorage.getItem('bandejaSolicitudes');
        if (guardadas) {
            setSolicitudes(JSON.parse(guardadas));
        } else {
            setSolicitudes(SOLICITUDES_BASE);
            localStorage.setItem('bandejaSolicitudes', JSON.stringify(SOLICITUDES_BASE));
        }
    }, []);



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
    }
    };

    return (
    <div style={styles.container}>

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
                {solicitudes.map((sol) => (
                    <div key={sol.id} style={styles.row}>
                        {/* 1. Nombre / ID Solicitud */}
                        <span style={{ flex: 1.5, textAlign: 'left', paddingLeft: '30px', fontWeight: '500', color: '#333' }}>
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

                        {/* 4. Pill / Badge de Estatus */}
                        <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                            <span style={{ ...styles.statusBadge, ...getBadgeStyle(sol.status) }}>
                                {sol.status}
                            </span>
                        </div>

                        {/* 5. Botón / Acción Abrir */}
                        <div style={{ width: '100px', textAlign: 'center' }}>
                            <button 
                                style={styles.abrirBtn}
                                onClick={() => navigate('/acumulado', { state: { solicitud: sol } })}
                            >
                                Abrir
                            </button>
                        </div>
                    </div>
                ))}
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
    }
};

export default Bandeja;
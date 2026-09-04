import { Link, useLocation } from 'react-router-dom';

function TabsNav({ currentRole }) {
    const location = useLocation();
    const currentPath = location.pathname;

    // Definimos qué pestañas ve cada rol según tus reglas de negocio
    const obtenerPestañasPorRol = () => {
        switch (currentRole) {
            case 'tienda':
                return [
                    { label: 'Solicitud', path: '/solicitud/nueva' },
                    { label: 'Monitoreo', path: '/bandeja' },
                    { label: 'Historico', path: '/historico' }
                ];
            case 'supervisor':
                return [
                    { label: 'Autorización', path: '/autorizacion' }
                ];
            case 'contabilidad':
            case 'gerencia':
            case 'tesoreria':
            case 'direccion':
                return [
                    { label: 'Bandeja', path: '/bandeja' },
                    { label: 'Dashboard', path: '/dashboard' }, // Próximamente
                    { label: 'Historico', path: '/historico' }
                ];
            case 'admin':
                // El administrador tiene visibilidad de las secciones del sistema
                return [
                    { label: 'Usuarios', path: '/usuarios' },
                    { label: 'Solicitud', path: '/solicitud/nueva' },
                    { label: 'Autorizacion', path: '/autorizacion' },
                    { label: 'Bandeja', path: '/bandeja' },
                    { label: 'Dashboard', path: '/dashboard' },
                    { label: 'Historico', path: '/historico' }
                ];
            default:
                return [];
        }
    };

    const pestañas = obtenerPestañasPorRol();


    // Si el usuario no tiene pestañas asignadas en este rol, no pintamos la barra
    if (pestañas.length === 0) return null;

    return (
        <div style={styles.subNavContainer}>
        {pestañas.map((tab) => {
            const isActive = currentPath === tab.path;
            
            return (
            <Link
                key={tab.path}
                to={tab.path}
                style={{
                ...styles.tabButton,
                background: isActive ? 'var(--gradient)' : 'var(--sb-WBtnBg)',
                color: isActive ? 'var(--text-CBtn)' : 'var(--text-WBtn)',
                cursor: 'pointer'
                }}
            >
                {tab.label}
            </Link>
            );
        })}
        </div>
    );
    }

    const styles = {
    subNavContainer: {
        display: 'flex',
        gap: '12px',
        padding: '12px 30px',
        backgroundColor: 'var(--sb-subhead)', // Un fondo sutil para separar del Header, alineado a --sb-subhead
        borderBottom: '1px solid var(--border)',
        justifyContent: 'flex-start',
        alignItems: 'center'
    },
    tabButton: {
        textDecoration: 'none',
        padding: '8px 24px',
        borderRadius: '20px', // Forma ovalada/píldora idéntica a tu mockup
        border: '1px solid var(--sb-btnBorder)',
        fontSize: '14px',
        fontWeight: 'bold',
        transition: 'all 0.2s ease',
        display: 'inline-block'
    }
};

export default TabsNav;

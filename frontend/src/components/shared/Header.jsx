import { useNavigate } from 'react-router-dom';

import { clearSession } from '../../lib/api';

function Header({ onRoleChange }) {
    const navigate = useNavigate();

  // Función para refrescar la página actual
    const handleRefresh = () => {
    window.location.reload();
    };

    const handleLogout = () => {
    clearSession();
    if (onRoleChange) onRoleChange('admin');
    navigate('/login', { replace: true });
    };

    return (
    <header style={styles.header}>
      {/* SECCIÓN IZQUIERDA: LOGO Y SUBTÍTULO */}
        <div style={styles.logoContainer} onClick={() => navigate('/bandeja')}>
        {/* Cambia 'tu_logo.png' por el nombre exacto de tu archivo en public */}
        <img src="/Logotipo.png" alt="Smolbox Logo" style={styles.logoImg} />
        </div>


      {/* SECCIÓN DERECHA: ACCIONES */}
        <div style={styles.actionsContainer}>
        {/* Botón Refrescar */}
        <button onClick={handleRefresh} style={styles.refreshButton}>
            <span style={{ marginRight: '5px' }}></span> Actualizar
        </button>

        <button
            onClick={handleLogout}
            style={styles.logoutButton}
        >
            Cerrar sesión
        </button>
        </div>
    </header>
    );
}

// Estilos en línea para lograr los colores y formas de tu imagen
const styles = {
    header: {
        backgroundColor: 'var(--sb-header)', // Color salmón/coral claro de tu mockup
        height: '55px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 30px',
        boxShadow: 'var(--shadow)',
        fontFamily: 'var(--sans)',
    },
    logoContainer: {
        display: 'flex',
        alignItems: 'center',
        cursor: 'pointer',
    },
    logoImg: {
        height: '41px', // Ajusta según la proporción de tu imagen
        objectFit: 'contain',
    },
    nav: {
        display: 'flex',
        gap: '20px',
        marginLeft: '30px',
        flexGrow: 1,
    },
    navLink: {
        color: '#ffffff',
        textDecoration: 'none',
        fontWeight: '600',
        fontSize: '14px',
        padding: '5px 10px',
        borderRadius: '4px',
        transition: 'background-color 0.2s',
    },
    actionsContainer: {
        display: 'flex',
        alignItems: 'center',
        gap: '15px',
    },
    refreshButton: {
        backgroundColor: 'transparent',
        border: '2px solid var(--bg)',
        color: 'var(--text-CBtn)',
        padding: '8px 16px',
        borderRadius: '5px', // Estilo rectangular de tu imagen
        cursor: 'pointer',
        fontSize: '15px',
        fontWeight: '500',
        display: 'flex',
        alignItems: 'center',
    },
    logoutButton: {
        backgroundColor: 'var(--sb-WBtnBg)',
        border: 'none',
        color: 'var(--text-WBtn)', // Texto en tono coral
        padding: '10px 25px',
        borderRadius: '20px', // Totalmente ovalado como tu mockup
        cursor: 'pointer',
        fontWeight: 'bold',
        fontSize: '15px',
    }
};

export default Header;

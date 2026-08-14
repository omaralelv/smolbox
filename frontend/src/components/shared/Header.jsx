import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

// Supongamos que recibes el "rolLogueado" y la función para cambiarlo desde el contexto o App.jsx
// Esto te servirá para cambiar de rol con el botón de Perfil mientras pruebas los mocks.
function Header({ currentRole = 'admin', onRoleChange }) {
    const navigate = useNavigate();
    const [showProfileMenu, setShowProfileMenu] = useState(false);

  // Lista de todos tus roles para el simulador del menú
    const todosLosRoles = ['tienda', 'supervisor', 'contabilidad', 'gerencia', 'tesoreria', 'direccion', 'admin'];

  // Función para refrescar la página actual
    const handleRefresh = () => {
    window.location.reload();
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

        {/* Botón Perfil con simulador de Roles */}
        <div style={{ position: 'relative' }}>
            <button 
            onClick={() => setShowProfileMenu(!showProfileMenu)} 
            style={styles.profileButton}
            >
            Perfil ({currentRole})
            </button>

          {/* Menú desplegable para que cambies de rol fácilmente mientras desarrollas */}
            {showProfileMenu && (
            <div style={styles.dropdown}>
                <div style={styles.dropdownHeader}>Simular Rol:</div>
                {todosLosRoles.map((rol) => (
                <button
                    key={rol}
                    onClick={() => {
                    if (onRoleChange) onRoleChange(rol);
                    setShowProfileMenu(false);
                    }}
                    style={{
                    ...styles.dropdownItem,
                    fontWeight: currentRole === rol ? 'bold' : 'normal',
                    backgroundColor: currentRole === rol ? '#f0f0f0' : 'transparent'
                    }}
                >
                    {rol.toUpperCase()}
                </button>
                ))}
            </div>
            )}
        </div>
        </div>
    </header>
    );
}

// Estilos en línea para lograr los colores y formas de tu imagen
const styles = {
    header: {
        backgroundColor: 'var(--sb-header)', // Color salmón/coral claro de tu mockup
        height: '70px',
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
    profileButton: {
        backgroundColor: 'var(--sb-WBtnBg)',
        border: 'none',
        color: 'var(--text-WBtn)', // Texto en tono coral
        padding: '10px 25px',
        borderRadius: '20px', // Totalmente ovalado como tu mockup
        cursor: 'pointer',
        fontWeight: 'bold',
        fontSize: '15px',
    },
    dropdown: {
        position: 'absolute',
        right: 0,
        top: '45px',
        backgroundColor: '#ffffff',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        borderRadius: '8px',
        padding: '10px 0',
        width: '160px',
        zIndex: 100,
    },
    dropdownHeader: {
        padding: '5px 15px',
        fontSize: '11px',
        color: '#999',
        textTransform: 'uppercase',
        fontWeight: 'bold',
    },
    dropdownItem: {
        width: '100%',
        padding: '8px 15px',
        textAlign: 'left',
        border: 'none',
        background: 'none',
        cursor: 'pointer',
        fontSize: '13px',
        color: '#333',
    }
};

export default Header;
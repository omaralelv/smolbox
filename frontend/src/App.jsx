import { useEffect, useState } from 'react'
import { BrowserRouter, useLocation } from 'react-router-dom';

import './App.css'
import './index.css'

import Header from './components/shared/Header';
import TabsNav from './components/shared/TabsNav';
import AppRouter from './app/AppRouter';

import { clearSession, currentStoredRole, currentToken, getFrontendContext } from './lib/api';

function MainContent({ rolLogueado, setRolLogueado }) {
  const location = useLocation();

  // Evaluamos si la ruta actual es el login
  const esLogin = location.pathname === '/login' || location.pathname === '/';
  const esRecup = location.pathname === '/recuperar-contrasena';
  const esConfirm = location.pathname === '/confirmar-recuperacion';

  const esPantallaAuth = esLogin || esRecup || esConfirm;

  return (
    <>
      {/* 1. SECCIÓN FIJA SUPERIOR (HEADER Y TABS) */}
      {!esPantallaAuth && (
        <div style={{ flexShrink: 0, zIndex: 100 }}>
          <Header currentRole={rolLogueado} onRoleChange={setRolLogueado} />
          <TabsNav currentRole={rolLogueado} />
        </div>
      )}

      {/* Si estamos en autenticación eliminamos el padding para pantalla completa */}
      {/* 2. ÁREA DE CONTENIDO CON SCROLL INDEPENDIENTE */}
      <main 
        style={{ 
          flex: 1, 
          overflowY: 'auto', 
          padding: esPantallaAuth ? '0' : '20px 30px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'stretch'
        }}
      >
        <AppRouter currentRole={rolLogueado} />
      </main>
    </>
  );
}



function App() {
  const [rolLogueado, setRolLogueado] = useState(() => currentStoredRole());  

  useEffect(() => {
    if (!currentToken()) return;

    let activo = true;
    getFrontendContext()
      .then((contexto) => {
        if (activo && contexto?.currentRole) {
          setRolLogueado(contexto.currentRole);
        }
      })
      .catch(() => {
        clearSession();
      });

    return () => {
      activo = false;
    };
  }, []);

  return (
    <BrowserRouter>
      <MainContent 
        rolLogueado={rolLogueado} 
        setRolLogueado={setRolLogueado} 
      />
    </BrowserRouter>
  );
}

export default App;

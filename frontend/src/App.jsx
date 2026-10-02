import { useEffect, useState } from 'react'
import { BrowserRouter, useLocation } from 'react-router-dom';

import './App.css'
import './index.css'

import Header from './components/shared/Header';
import TabsNav from './components/shared/TabsNav';
import AppRouter from './app/AppRouter';
import ClickAuditTracker from './components/audit/ClickAuditTracker';

import {
  clearSession,
  currentStoredRole,
  currentToken,
  getAppHealth,
  getFrontendContext,
} from './lib/api';

const VERSION_CHECK_INTERVAL_MS = 30_000;
const VERSION_RELOAD_STORAGE_KEY = 'smolboxLastReloadVersion';

function MainContent({ rolLogueado, setRolLogueado }) {
  const location = useLocation();

  // Evaluamos si la ruta actual es el login
  const esLogin = location.pathname === '/login' || location.pathname === '/';
  const esRecup = location.pathname === '/recuperar-contrasena';
  const esConfirm = location.pathname === '/confirmar-recuperacion';

  const esPantallaAuth = esLogin || esRecup || esConfirm;

  return (
    <>
      <ClickAuditTracker />

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

  useEffect(() => {
    let activo = true;
    let versionInicial = '';

    const revisarVersion = async () => {
      try {
        const [health, pageSignature] = await Promise.all([
          getAppHealth(),
          obtenerFirmaPagina(),
        ]);
        if (!activo) return;

        const versionActual = [health?.version, pageSignature].filter(Boolean).join('|');
        if (!versionActual) return;

        if (!versionInicial) {
          versionInicial = versionActual;
          return;
        }

        if (versionActual !== versionInicial) {
          const ultimaRecarga = sessionStorage.getItem(VERSION_RELOAD_STORAGE_KEY);
          if (ultimaRecarga !== versionActual) {
            sessionStorage.setItem(VERSION_RELOAD_STORAGE_KEY, versionActual);
            window.location.reload();
          }
        }
      } catch {
        // Si la verificacion falla, la app sigue funcionando y se reintenta despues.
      }
    };

    const revisarAlVolver = () => {
      if (document.visibilityState === 'visible') {
        revisarVersion();
      }
    };

    revisarVersion();
    const intervalo = window.setInterval(revisarVersion, VERSION_CHECK_INTERVAL_MS);
    window.addEventListener('focus', revisarVersion);
    document.addEventListener('visibilitychange', revisarAlVolver);

    return () => {
      activo = false;
      window.clearInterval(intervalo);
      window.removeEventListener('focus', revisarVersion);
      document.removeEventListener('visibilitychange', revisarAlVolver);
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

async function obtenerFirmaPagina() {
  const response = await fetch(`/?smolboxVersionCheck=${Date.now()}`, {
    cache: 'no-store',
  });
  if (!response.ok) return '';

  const html = await response.text();
  const assets = Array.from(
    html.matchAll(/(?:src|href)=["']([^"']+\.(?:js|css)(?:\?[^"']*)?)["']/gi),
    (match) => match[1]
  ).sort();

  return assets.length > 0 ? assets.join('|') : String(html.length);
}

export default App;

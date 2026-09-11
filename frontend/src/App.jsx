import { useEffect, useState } from 'react'
import { BrowserRouter, useLocation } from 'react-router-dom';

import './App.css'
import './index.css'

import Header from './components/shared/Header';
import TabsNav from './components/shared/TabsNav';
import AppRouter from './app/AppRouter';

import { currentStoredRole, currentToken, getFrontendContext } from './lib/api';

function MainContent({ rolLogueado, setRolLogueado }) {
  const location = useLocation();

  // Evaluamos si la ruta actual es el login
  const esLogin = location.pathname === '/login' || location.pathname === '/';

  return (
    <>
      {/* Solo mostramos Header y TabsNav si NO estamos en Login */}
      {!esLogin && (
        <>
          <Header currentRole={rolLogueado} onRoleChange={setRolLogueado} />
          <TabsNav currentRole={rolLogueado} />
        </>
      )}

      {/* Si estamos en Login eliminamos el padding de 20px para pantalla completa */}
      <main style={{ padding: esLogin ? '0' : '20px' }}>
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
        localStorage.removeItem('smolboxApiToken');
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

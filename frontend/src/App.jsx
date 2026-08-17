import { useEffect, useState } from 'react'
import { BrowserRouter } from 'react-router-dom';

import './App.css'
import './index.css'

import Header from './components/shared/Header';
import TabsNav from './components/shared/TabsNav';
import AppRouter from './app/AppRouter';
import { currentStoredRole, currentToken, getFrontendContext } from './lib/api';

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
      <Header currentRole={rolLogueado} onRoleChange={setRolLogueado} />
      <TabsNav currentRole={rolLogueado} />

      <main style={{ padding: '20px' }}>
        <AppRouter currentRole={rolLogueado} /> 
      </main>
    </BrowserRouter>
  );
}

export default App;

import { useState } from 'react'
import { BrowserRouter } from 'react-router-dom';

import './App.css'
import './index.css'

import { MOCK_REEMBOLSOS } from './mocks/reembolsosMock';

// Components
import Header from './components/shared/Header';
import TabsNav from './components/shared/TabsNav';
import AppRouter from './app/AppRouter'; // Tu archivo de rutas actuales

// Pages
import Dashboard from './pages/Dashboard';

function App() {
  // Este estado simula el rol actual para que el Header y las rutas reaccionen
  const [rolLogueado, setRolLogueado] = useState('admin');

  return (
    <BrowserRouter>
      {/* El Header se queda fijo arriba y le pasamos el rol */}

      <Header currentRole={rolLogueado} onRoleChange={setRolLogueado} />
      
      <TabsNav currentRole={rolLogueado} />


      {/* El contenedor del contenido cambia según la ruta del AppRouter */}
      <main style={{ padding: '20px' }}>
        {/* Aquí pasas el rol a tu router por si tus ProtectedRoutes lo necesitan */}
        <AppRouter currentRole={rolLogueado} /> 
      </main>
    </BrowserRouter>
  );
}

export default App;

// AppRouter.jsx

import SolicitudForm from '../pages/tienda/SolicitudForm';
import AnadirGasto from '../pages/tienda/AnadirGasto';
import Bandeja from '../pages/Bandeja';
import Acumulado from '../pages/Acumulado';
import Detalle from '../pages/Detalle';
import Dashboard from '../pages/Dashboard';
import Login from '../pages/Login';
import Historico from '../pages/Historico';
import AutorizacionBandeja from '../pages/autorizacion/AutorizacionBandeja';

/*<Routes>
    <Route path="/solicitud/nueva" element={<ProtectedRoute roles={['tienda','admin']}><SolicitudForm/></ProtectedRoute>} />
    <Route path="/monitoreo" element={<ProtectedRoute roles={['tienda','admin']}><Monitoreo/></ProtectedRoute>} />
    <Route path="/autorizacion" element={<ProtectedRoute roles={['juanita','admin']}><AutorizacionBandeja/></ProtectedRoute>} />
    <Route path="/bandeja" element={<ProtectedRoute roles={['contabilidad','tesoreria','direccion','admin']}><Bandeja/></ProtectedRoute>} />
    <Route path="/solicitud/:id" element={<ProtectedRoute roles={['contabilidad','tesoreria','direccion','admin']}><Detalle/></ProtectedRoute>} />
    <Route path="/usuarios" element={<ProtectedRoute roles={['admin']}><Usuarios/></ProtectedRoute>} />
</Routes>*/

import { Routes, Route, Navigate } from 'react-router-dom';

function AppRouter({ currentRole }) { 
    return (
        <Routes>
        <Route path="/" element={<Navigate to="/solicitud/nueva" replace />} />

        <Route path="/login" element={<Login />} />
        <Route path="/solicitud/nueva" element={<SolicitudForm currentRole={currentRole} />} />
        <Route path="/gasto/nuevo" element={<AnadirGasto />} />
        <Route path="/autorizacion" element={<AutorizacionBandeja/>} />
        <Route path="/bandeja" element={<Bandeja currentRole={currentRole}/>} />

        <Route path="/acumulado" element={<Acumulado currentRole={currentRole} />}/>
        <Route path="/detalle" element={<Detalle currentRole={currentRole} />}/>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/historico" element={<Historico />}/>
        
        </Routes>
    );
}

export default AppRouter;

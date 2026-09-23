// AppRouter.jsx

import SolicitudForm from '../pages/tienda/SolicitudForm';
import AnadirGasto from '../pages/tienda/AnadirGasto';
import Bandeja from '../pages/Bandeja';
import Acumulado from '../pages/Acumulado';
import Detalle from '../pages/Detalle';
import Dashboard from '../pages/Dashboard';
import Login from '../pages/Login';
import RecoverPassword from '../pages/RecoverPassword';
import ConfirmPasswordReset from '../pages/ConfirmPasswordReset';
import Historico from '../pages/Historico';
import AutorizacionBandeja from '../pages/autorizacion/AutorizacionBandeja';
import Usuarios from '../pages/admin/Usuarios';
import { currentToken } from '../lib/api';

/*<Routes>
    <Route path="/solicitud/nueva" element={<ProtectedRoute roles={['tienda','admin']}><SolicitudForm/></ProtectedRoute>} />
    <Route path="/monitoreo" element={<ProtectedRoute roles={['tienda','admin']}><Monitoreo/></ProtectedRoute>} />
    <Route path="/autorizacion" element={<ProtectedRoute roles={['juanita','admin']}><AutorizacionBandeja/></ProtectedRoute>} />
    <Route path="/bandeja" element={<ProtectedRoute roles={['contabilidad','tesoreria','direccion','admin']}><Bandeja/></ProtectedRoute>} />
    <Route path="/solicitud/:id" element={<ProtectedRoute roles={['contabilidad','tesoreria','direccion','admin']}><Detalle/></ProtectedRoute>} />
    <Route path="/usuarios" element={<ProtectedRoute roles={['admin']}><Usuarios/></ProtectedRoute>} />
</Routes>*/

import { Routes, Route, Navigate, useLocation } from 'react-router-dom';

function RequireSession({ children }) {
    const location = useLocation();

    if (!currentToken()) {
        return <Navigate to="/login" replace state={{ from: location }} />;
    }

    return children;
}

function AppRouter({ currentRole }) { 
    return (
        <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />

        <Route path="/login" element={<Login />} />
        <Route path="/recuperar-contrasena" element={<RecoverPassword />} />
        <Route path="/confirmar-recuperacion" element={<ConfirmPasswordReset />} />
        <Route path="/solicitud/nueva" element={<RequireSession><SolicitudForm currentRole={currentRole} /></RequireSession>} />
        <Route path="/gasto/nuevo" element={<RequireSession><AnadirGasto /></RequireSession>} />
        <Route path="/autorizacion" element={<RequireSession><AutorizacionBandeja currentRole={currentRole}/></RequireSession>} />
        <Route path="/bandeja" element={<RequireSession><Bandeja currentRole={currentRole}/></RequireSession>} />

        <Route path="/acumulado" element={<RequireSession><Acumulado currentRole={currentRole} /></RequireSession>}/>
        <Route path="/detalle" element={<RequireSession><Detalle currentRole={currentRole} /></RequireSession>}/>
        <Route path="/dashboard" element={<RequireSession><Dashboard /></RequireSession>} />
        <Route path="/historico" element={<RequireSession><Historico currentRole={currentRole} /></RequireSession>}/>
        <Route path="/usuarios" element={<RequireSession><Usuarios /></RequireSession>} />
        
        </Routes>
    );
}

export default AppRouter;

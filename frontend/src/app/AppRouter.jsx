// AppRouter.jsx

import SolicitudForm from '../pages/tienda/SolicitudForm';
import AnadirGasto from '../pages/tienda/AnadirGasto';
import Bandeja from '../pages/Bandeja';
import Acumulado from '../pages/Acumulado';
import Detalle from '../pages/Detalle';
import Dashboard from '../pages/Dashboard';
import Bitacora from '../pages/Bitacora';
import Login from '../pages/Login';
import RecoverPassword from '../pages/RecoverPassword';
import ConfirmPasswordReset from '../pages/ConfirmPasswordReset';
import Historico from '../pages/Historico';
import AutorizacionBandeja from '../pages/autorizacion/AutorizacionBandeja';
import Usuarios from '../pages/admin/Usuarios';
import { currentToken } from '../lib/api';

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
            <Route path="/dashboard" element={<RequireSession><Dashboard currentRole={currentRole} /></RequireSession>} />
            <Route path="/bitacora" element={<RequireSession><Bitacora /></RequireSession>} />
            <Route path="/historico" element={<RequireSession><Historico currentRole={currentRole} /></RequireSession>}/>
            <Route path="/usuarios" element={<RequireSession><Usuarios /></RequireSession>} />

        </Routes>
    );
}

export default AppRouter;

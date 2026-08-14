// AppRouter.jsx

import SolicitudForm from '../pages/tienda/SolicitudForm';
import AnadirGasto from '../pages/tienda/AnadirGasto';
import Bandeja from '../pages/Bandeja';
import Acumulado from '../pages/Acumulado';
import Detalle from '../pages/Detalle';

/*<Routes>
    <Route path="/solicitud/nueva" element={<ProtectedRoute roles={['tienda','admin']}><SolicitudForm/></ProtectedRoute>} />
    <Route path="/monitoreo" element={<ProtectedRoute roles={['tienda','admin']}><Monitoreo/></ProtectedRoute>} />
    <Route path="/autorizacion" element={<ProtectedRoute roles={['juanita','admin']}><AutorizacionBandeja/></ProtectedRoute>} />
    <Route path="/bandeja" element={<ProtectedRoute roles={['contabilidad','tesoreria','direccion','admin']}><Bandeja/></ProtectedRoute>} />
    <Route path="/solicitud/:id" element={<ProtectedRoute roles={['contabilidad','tesoreria','direccion','admin']}><Detalle/></ProtectedRoute>} />
    <Route path="/usuarios" element={<ProtectedRoute roles={['admin']}><Usuarios/></ProtectedRoute>} />
</Routes>*/

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
// ... tus imports de las páginas ...

// Asegúrate de recibir "currentRole" o "roles" aquí si tu ProtectedRoute lo necesita
function AppRouter({ currentRole }) { 
    return (
        <Routes>
        {/* Redirección inicial */}
        <Route path="/" element={<Navigate to="/solicitud/nueva" replace />} />

        {/* Tus rutas */}
        <Route path="/solicitud/nueva" element={<SolicitudForm />} />
        <Route path="/gasto/nuevo" element={<AnadirGasto />} />
        <Route path="/bandeja" element={<Bandeja currentRole={currentRole}/>} />

        <Route path="/acumulado" element={<Acumulado currentRole={currentRole} />}/>
        <Route path="/detalle" element={<Detalle currentRole={currentRole} />}/>
        
        </Routes>
    );
}

// ¡Súper importante que esta línea esté aquí abajo!
export default AppRouter;
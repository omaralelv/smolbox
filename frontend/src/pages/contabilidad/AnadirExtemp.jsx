import AnadirGasto from '../tienda/AnadirGasto';
import { Navigate, useLocation } from 'react-router-dom';
import { currentStoredRole } from '../../lib/api';

export default function AnadirExtemp() {
    const location = useLocation();
    if (!['admin', 'contabilidad'].includes(currentStoredRole()) || !location.state?.selectedStoreId) {
        return <Navigate to="/solicitud/extemporanea" replace />;
    }
    return <AnadirGasto extemporaneo />;
}

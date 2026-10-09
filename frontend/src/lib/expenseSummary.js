export function resumirGastos(gastos, gastoActivo) {
    const resumen = gastos.reduce((acumulado, gasto) => {
        if (gasto.inactivo) return acumulado;

        const status = String(gasto.status || '').toLowerCase();
        const backendStatus = String(gasto.backendStatus || gasto.backend_status || '').toLowerCase();
        const esEliminado = (
            (status === 'removed' || status === 'eliminado' || backendStatus === 'removed')
            && !gasto.esHijoParticion
            && !gasto.es_hijo_particion
            && !gasto.idOriginal
            && !gasto.id_original
        );
        if (!gastoActivo(gasto) && !esEliminado) return acumulado;

        const categoria = gasto.tipo || gasto.type || 'Gasto General';

        if (!acumulado[categoria]) {
            acumulado[categoria] = {
                id: categoria,
                tipo: categoria,
                facturas: 0,
                monto: 0,
                elementosOriginales: [],
            };
        }

        const grupo = acumulado[categoria];
        grupo.elementosOriginales.push(gasto);

        if (gastoActivo(gasto)) {
            grupo.facturas += parseInt(gasto.facturas || 1, 10);
            grupo.monto += parseFloat(gasto.monto || 0);
        }

        return acumulado;
    }, {});

    return Object.values(resumen);
}

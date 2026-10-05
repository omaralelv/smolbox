export function resumirGastos(gastos, gastoActivo) {
    const resumen = gastos.reduce((acumulado, gasto) => {
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

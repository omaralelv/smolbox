import assert from 'node:assert/strict';
import test from 'node:test';

import { resumirGastos } from './expenseSummary.js';

test('preserva los gastos eliminados para detalle y solo agrega los activos al resumen', () => {
    const gastos = [
        { tipo: 'Papelería', facturas: 2, monto: 300, status: 'removed' },
        { tipo: 'Papelería', facturas: 1, monto: 150, status: 'active' },
        { tipo: 'Agua', facturas: 1, monto: 80, status: 'removed' },
    ];

    const resumen = resumirGastos(gastos, gasto => gasto.status === 'active');

    assert.deepEqual(resumen, [
        {
            id: 'Papelería',
            tipo: 'Papelería',
            facturas: 1,
            monto: 150,
            elementosOriginales: [gastos[0], gastos[1]],
        },
        {
            id: 'Agua',
            tipo: 'Agua',
            facturas: 0,
            monto: 0,
            elementosOriginales: [gastos[2]],
        },
    ]);
});

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

test('oculta categorías originadas solo por una partición y las restaura al anularla', () => {
    const gastoOriginalParticionado = {
        tipo: 'Papelería',
        monto: 1500,
        status: 'En revisión',
        inactivo: true,
        esParticionado: true,
    };
    const particiones = [
        { tipo: 'Agua', monto: 1000, status: 'En revisión', esHijoParticion: true },
        { tipo: 'Limpieza', monto: 500, status: 'En revisión', esHijoParticion: true },
    ];
    const esActivo = gasto => !['removed', 'eliminado'].includes(String(gasto.status).toLowerCase());

    assert.deepEqual(
        resumirGastos([gastoOriginalParticionado, ...particiones], esActivo).map(grupo => grupo.tipo),
        ['Agua', 'Limpieza'],
    );

    const gastoOriginalRestaurado = { ...gastoOriginalParticionado, inactivo: false, esParticionado: false };
    assert.deepEqual(
        resumirGastos([gastoOriginalRestaurado], esActivo).map(grupo => grupo.tipo),
        ['Papelería'],
    );
});

test('no conserva categorías que solo tengan particiones eliminadas', () => {
    const particionEliminada = {
        tipo: 'Agua',
        status: 'Eliminado',
        backendStatus: 'removed',
        esHijoParticion: true,
        idOriginal: 'gasto-original',
    };

    assert.deepEqual(resumirGastos([particionEliminada], () => false), []);
});

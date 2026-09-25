// src/mocks/reembolsosMock.js

export const MOCK_REEMBOLSOS = [
    {
        id: "REEM-001",
        concepto: "Visita técnica CEDIS Equinix",
        monto: 1250.00,
        solicitante: "Ameyalli Contreras",
        fecha: "2026-08-10",
        estado: "Pendiente Autorización",
        pasoActual: "juanita", // Le toca a Juanita revisar en su bandeja
        motivo: "Reunión de requerimientos e infraestructura"
    },
    {
        id: "REEM-002",
        concepto: "Licencia mensual Docker Desktop",
        monto: 450.00,
        solicitante: "Rommel",
        fecha: "2026-08-11",
        estado: "Pendiente Aprobación Dirección",
        pasoActual: "direccion", // Le toca a Fernando / Dirección
        motivo: "Entorno local de desarrollo"
    },
    {
        id: "REEM-003",
        concepto: "Papelería y consumibles de oficina",
        monto: 320.00,
        solicitante: "Omar",
        fecha: "2026-08-05",
        estado: "Listo para Pago",
        pasoActual: "tesoreria", // Le toca a Samuel en Tesorería dispersar
        motivo: "Configuración de hardware en estaciones de trabajo"
    }
];
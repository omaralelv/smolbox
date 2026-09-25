import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
    apiErrorMessage,
    currentToken,
    getFrontendBandeja,
    getFrontendHistorico,
    getRequestAuditEvents,
    listAllUsers,
} from '../lib/api';

const ACTION_GROUPS = [
    { value: 'all', label: 'Todos los movimientos' },
    { value: 'carga', label: 'Cargas' },
    { value: 'validacion', label: 'Validaciones' },
    { value: 'autorizacion', label: 'Autorizaciones/Rechazos' },
    { value: 'edicion', label: 'Ediciones' },
    { value: 'documento', label: 'Documentos' },
    { value: 'flujo', label: 'Flujo' },
];

const ROLE_LABELS = {
    admin: 'Admin',
    accountant: 'Contabilidad',
    accounting_manager: 'Gerencia',
    authorizer: 'Supervisor',
    director: 'Dirección',
    store: 'Tienda',
    system: 'Sistema',
    treasury: 'Tesorería',
};

const STATUS_LABELS = {
    accounting_manager_approved: 'Aprobada por gerencia',
    accounting_manager_review: 'Revisión de gerencia',
    accounting_reviewed: 'Revisada por contabilidad',
    approved_for_payment: 'Aprobada para pago',
    authorization_review: 'Revisión de autorización',
    authorized: 'Autorizada',
    closed: 'Cerrada',
    correction_required: 'Corrección requerida',
    direction_approved: 'Aprobada por dirección',
    direction_review: 'Revisión de dirección',
    draft: 'Borrador',
    paid: 'Pagada',
    rejected: 'Rechazada',
    submitted: 'Enviada',
    treasury_review: 'Revisión de tesorería',
    under_accounting_review: 'Revisión de contabilidad',
};

const FIELD_LABELS = {
    amount: 'monto',
    cfdi_uuid: 'folio fiscal',
    currency: 'moneda',
    folio: 'folio',
    merchant: 'proveedor',
    receipt_number: 'folio',
    supplier_tax_id: 'RFC',
    requires_authorization: 'autorización',
};

function Bitacora() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [events, setEvents] = useState([]);
    const [selectedDate, setSelectedDate] = useState(() => todayDateInput());
    const [followToday, setFollowToday] = useState(true);
    const [storeFilter, setStoreFilter] = useState('all');
    const [requestFilter, setRequestFilter] = useState('all');
    const [actionFilter, setActionFilter] = useState('all');

    useEffect(() => {
        if (!followToday) return undefined;

        const timer = window.setInterval(() => {
            setSelectedDate(todayDateInput());
        }, 60_000);

        return () => window.clearInterval(timer);
    }, [followToday]);

    useEffect(() => {
        let active = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                active = false;
            };
        }

        async function loadAuditData() {
            setLoading(true);
            setError('');

            try {
                const [bandejaResult, historicoResult, usersResult] = await Promise.allSettled([
                    getFrontendBandeja(),
                    getFrontendHistorico(),
                    listAllUsers(),
                ]);

                const bandeja = fulfilledArray(bandejaResult);
                const historico = fulfilledArray(historicoResult);

                if (!bandeja.length && !historico.length) {
                    const firstError = [bandejaResult, historicoResult].find(
                        (result) => result.status === 'rejected'
                    );
                    if (firstError) throw firstError.reason;
                }

                const users = fulfilledArray(usersResult);
                const usersById = new Map(
                    users.map((user) => [String(user.id), user])
                );
                const requests = uniqueRequests([...bandeja, ...historico]).slice(0, 120);

                const auditResults = await Promise.allSettled(
                    requests.map((request) => {
                        const requestId = request.backendId || request.backend_id || request.id;
                        if (!requestId) return Promise.resolve([]);
                        return getRequestAuditEvents(requestId).then((auditEvents) => (
                            auditEvents.map((event) => normalizeAuditEvent(event, request, usersById))
                        ));
                    })
                );

                const normalizedEvents = auditResults
                    .flatMap((result) => (result.status === 'fulfilled' ? result.value : []))
                    .filter(Boolean)
                    .sort((a, b) => b.timestamp - a.timestamp);

                if (!active) return;
                setEvents(normalizedEvents);
            } catch (requestError) {
                if (!active) return;
                setError(apiErrorMessage(requestError));
            } finally {
                if (active) setLoading(false);
            }
        }

        loadAuditData();

        return () => {
            active = false;
        };
    }, [navigate]);

    const dayEvents = useMemo(() => (
        events.filter((event) => event.dateKey === selectedDate)
    ), [events, selectedDate]);

    const storeOptions = useMemo(() => {
        const options = new Map();
        dayEvents.forEach((event) => {
            if (event.storeKey) {
                options.set(event.storeKey, event.storeLabel);
            }
        });
        return [...options.entries()]
            .map(([value, label]) => ({ value, label }))
            .sort((a, b) => a.label.localeCompare(b.label, 'es-MX'));
    }, [dayEvents]);

    const requestOptions = useMemo(() => {
        const options = new Map();
        dayEvents.forEach((event) => {
            if (storeFilter !== 'all' && event.storeKey !== storeFilter) return;
            if (event.requestId) {
                options.set(event.requestId, event.requestLabel);
            }
        });
        return [...options.entries()]
            .map(([value, label]) => ({ value, label }))
            .sort((a, b) => a.label.localeCompare(b.label, 'es-MX'));
    }, [dayEvents, storeFilter]);

    useEffect(() => {
        if (
            storeFilter !== 'all'
            && !storeOptions.some((option) => option.value === storeFilter)
        ) {
            setStoreFilter('all');
        }
    }, [storeFilter, storeOptions]);

    useEffect(() => {
        if (
            requestFilter !== 'all'
            && !requestOptions.some((option) => option.value === requestFilter)
        ) {
            setRequestFilter('all');
        }
    }, [requestFilter, requestOptions]);

    const filteredEvents = useMemo(() => (
        dayEvents.filter((event) => (
            (storeFilter === 'all' || event.storeKey === storeFilter)
            && (requestFilter === 'all' || event.requestId === requestFilter)
            && (actionFilter === 'all' || event.group === actionFilter)
        ))
    ), [dayEvents, storeFilter, requestFilter, actionFilter]);

    const summary = useMemo(() => ({
        movements: filteredEvents.length,
        requests: new Set(filteredEvents.map((event) => event.requestId)).size,
        users: new Set(filteredEvents.map((event) => event.actorName).filter(Boolean)).size,
    }), [filteredEvents]);

    return (
        <main style={styles.container}>
            <section style={styles.header}>
                <span style={styles.kicker}>Auditoría visible</span>
                <h1 style={styles.title}>Bitácora de actividad</h1>
                <p style={styles.description}>
                    Movimientos registrados por solicitud: quién cargó, validó,
                    autorizó, rechazó o editó información, con fecha y motivo.
                </p>
            </section>

            <section style={styles.toolbar}>
                <label style={styles.filterLabel}>
                    Día
                    <input
                        type="date"
                        value={selectedDate}
                        onClick={(e) => e.target.showPicker && e.target.showPicker()}
                        onChange={(event) => {
                            setSelectedDate(event.target.value);
                            setFollowToday(event.target.value === todayDateInput());
                            setStoreFilter('all');
                            setRequestFilter('all');
                        }}
                        style={styles.selectCal}
                    />
                </label>

                <label style={styles.filterLabel}>
                    Tienda
                    <select
                        value={storeFilter}
                        onChange={(event) => {
                            setStoreFilter(event.target.value);
                            setRequestFilter('all');
                        }}
                        style={styles.select}
                    >
                        <option value="all">Todas</option>
                        {storeOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </label>

                <label style={styles.filterLabel}>
                    Solicitud
                    <select
                        value={requestFilter}
                        onChange={(event) => setRequestFilter(event.target.value)}
                        style={styles.select}
                    >
                        <option value="all">Todas</option>
                        {requestOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </label>

                <label style={styles.filterLabel}>
                    Movimiento
                    <select
                        value={actionFilter}
                        onChange={(event) => setActionFilter(event.target.value)}
                        style={styles.select}
                    >
                        {ACTION_GROUPS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </label>

                <button
                    type="button"
                    onClick={() => {
                        setSelectedDate(todayDateInput());
                        setFollowToday(true);
                        setStoreFilter('all');
                        setRequestFilter('all');
                    }}
                    style={styles.todayButton}
                >
                    Hoy
                </button>
            </section>

            <section style={styles.summaryGrid}>
                <SummaryCard label="Movimientos" value={summary.movements} />
                <SummaryCard label="Solicitudes" value={summary.requests} />
                <SummaryCard label="Usuarios" value={summary.users} />
            </section>

            <section style={styles.panel}>

                {loading ? (
                    <div style={styles.message}>Cargando bitácora...</div>
                ) : error ? (
                    <div style={styles.errorBox}>{error}</div>
                ) : filteredEvents.length === 0 ? (
                    <div style={styles.message}>No hay movimientos con los filtros seleccionados.</div>
                ) : (
                    <div style={styles.tableWrap}>
                        <table style={styles.table}>
                            <thead>
                                <tr>
                                    <th style={styles.th}>Fecha</th>
                                    <th style={styles.th}>Tienda</th>
                                    <th style={styles.th}>Solicitud</th>
                                    <th style={styles.th}>Movimiento</th>
                                    <th style={styles.th}>Rol</th>
                                    <th style={styles.th}>Usuario</th>
                                    <th style={styles.th}>Detalle</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredEvents.map((event) => (
                                    <tr key={event.id} style={styles.tr}>
                                        <td style={styles.tdStrong}>{event.dateLabel}</td>
                                        <td style={styles.td}>{event.storeLabel}</td>
                                        <td style={styles.td}>{event.requestLabel}</td>
                                        <td style={styles.tdStrong}>
                                            {event.actionLabel}
                                        </td>
                                        <td style={styles.td}>
                                            <span style={styles.badge}>{event.roleLabel}</span>
                                        </td>
                                        <td style={styles.td}>{event.actorName}</td>
                                        <td style={styles.detailTd}>{event.detail}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </main>
    );
}

function SummaryCard({ label, value }) {
    return (
        <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>{label}</span>
            <strong style={styles.summaryValue}>{value}</strong>
        </div>
    );
}

function fulfilledArray(result) {
    return result.status === 'fulfilled' && Array.isArray(result.value)
        ? result.value
        : [];
}

function uniqueRequests(requests) {
    const byId = new Map();
    requests.forEach((request) => {
        const id = request?.backendId || request?.backend_id || request?.id;
        if (id && !byId.has(String(id))) {
            byId.set(String(id), request);
        }
    });
    return [...byId.values()];
}

function normalizeAuditEvent(event, request, usersById) {
    const payload = event.event_payload || event.payload || {};
    const actorId = event.actor_user_id || event.actorUserId;
    const actor = actorId ? usersById.get(String(actorId)) : null;
    const actorRole = payload.actor_role || actor?.role || event.actor_type || 'system';
    const requestId = String(request.backendId || request.backend_id || request.id || '');
    const timestamp = Date.parse(event.created_at || event.createdAt || '');
    const storeLabel = request.tienda || request.storeCode || request.store_code || 'N/A';

    return {
        id: String(event.id),
        requestId,
        requestLabel: request.folio || request.id || requestId,
        storeKey: String(storeLabel).trim().toLowerCase(),
        storeLabel,
        actionLabel: actionLabel(event.action, event.to_status || event.toStatus),
        group: actionGroup(event.action),
        actorName: actorName(actor, event.actor_type || event.actorType, actorId),
        roleLabel: roleLabel(actorRole),
        detail: eventDetail(event, payload),
        timestamp: Number.isNaN(timestamp) ? 0 : timestamp,
        dateKey: dateInputFromValue(event.created_at || event.createdAt),
        dateLabel: dateLabel(event.created_at || event.createdAt),
    };
}

function actionLabel(action, toStatus) {
    const labels = {
        accounting_request_taken: 'Solicitud tomada',
        automated_review_completed: 'Validación automática',
        expense_attachment_uploaded: 'Documento cargado',
        expense_authorization_rejected: 'Gasto rechazado',
        expense_authorized: 'Gasto autorizado',
        expense_cfdi_validated: 'Factura validada',
        expense_created: 'Gasto cargado',
        expense_created_from_frontend: 'Gasto cargado',
        expense_observation_added: 'Observación agregada',
        expense_ocr_extracted: 'OCR leído',
        expense_ocr_failed: 'OCR no leído',
        expense_removed_from_request: 'Gasto eliminado',
        expense_review_updated: 'Gasto editado',
        expense_updated: 'Gasto editado',
        expenses_imported: 'Gastos importados',
        payment_recorded: 'Pago registrado',
        reimbursement_excel_uploaded: 'Reembolso cargado',
        request_attachment_uploaded: 'Documento cargado',
        request_created: 'Solicitud cargada',
        request_created_from_frontend: 'Solicitud cargada',
        request_updated: 'Solicitud editada',
        sap_policy_placeholder_prepared: 'Póliza preparada',
    };

    if (action === 'request_status_changed') {
        return toStatus ? `Cambio a ${statusLabel(toStatus)}` : 'Cambio de estatus';
    }
    return labels[action] || humanize(action);
}

function actionGroup(action) {
    if ([
        'expense_created',
        'expense_created_from_frontend',
        'expenses_imported',
        'request_created',
        'request_created_from_frontend',
    ].includes(action)) return 'carga';
    if ([
        'automated_review_completed',
        'expense_cfdi_validated',
        'expense_ocr_extracted',
        'expense_ocr_failed',
    ].includes(action)) return 'validacion';
    if ([
        'expense_authorization_rejected',
        'expense_authorized',
    ].includes(action)) return 'autorizacion';
    if ([
        'expense_review_updated',
        'expense_updated',
        'request_updated',
    ].includes(action)) return 'edicion';
    if ([
        'expense_attachment_uploaded',
        'request_attachment_uploaded',
        'reimbursement_excel_uploaded',
    ].includes(action)) return 'documento';
    return 'flujo';
}

function eventDetail(event, payload) {
    const details = [];
    if (event.message) details.push(translateMessage(event.message));

    if (Array.isArray(payload.changed_fields) && payload.changed_fields.length) {
        details.push(`Campos editados: ${payload.changed_fields.map(fieldLabel).join(', ')}.`);
    }
    if (payload.original_merchant || payload.original_amount) {
        const merchant = payload.original_merchant ? `Proveedor: ${payload.original_merchant}.` : '';
        const amount = payload.original_amount ? `Monto: ${payload.original_amount}.` : '';
        details.push([merchant, amount].filter(Boolean).join(' '));
    }
    if (payload.uuid) details.push(`Folio fiscal: ${payload.uuid}.`);
    if (payload.reference) details.push(`Referencia: ${payload.reference}.`);
    if (payload.file_name || payload.filename) {
        details.push(`Archivo: ${payload.file_name || payload.filename}.`);
    }
    if (event.from_status || event.to_status || event.fromStatus || event.toStatus) {
        const fromStatus = event.from_status || event.fromStatus;
        const toStatus = event.to_status || event.toStatus;
        if (fromStatus || toStatus) {
            details.push(`${statusLabel(fromStatus) || 'Sin estatus'} -> ${statusLabel(toStatus) || 'Sin estatus'}.`);
        }
    }

    return details.filter(Boolean).join(' ') || 'Movimiento registrado sin detalle adicional.';
}

function translateMessage(message) {
    const messages = {
        'Accounting request opened by user.': 'Solicitud abierta por contabilidad.',
        'Automatic validation flow completed.': 'Validación automática completada.',
        'CFDI XML parsed, validated and stored.': 'Factura XML leída, validada y guardada.',
        'Expense updated.': 'Gasto actualizado.',
        'OCR extracted with AWS Textract.': 'OCR leído con Textract.',
        'OCR reused from validation preview.': 'OCR reutilizado desde la validación previa.',
        'Payment recorded.': 'Pago registrado.',
        'Reimbursement request created.': 'Solicitud creada.',
        'Reimbursement request created from frontend-compatible API.': 'Solicitud creada desde la app.',
        'Reimbursement request updated.': 'Solicitud actualizada.',
        'SAP policy placeholder prepared.': 'Póliza preparada.',
    };
    return messages[message] || message;
}

function actorName(actor, actorType, actorId) {
    if (actor?.full_name) return actor.full_name;
    if (actor?.nombre) return actor.nombre;
    if (actor?.email) return actor.email;
    if (actorType === 'system') return 'Sistema';
    return actorId ? `Usuario ${String(actorId).slice(0, 8)}` : 'Sistema';
}

function roleLabel(role) {
    const normalized = String(role || 'system').toLowerCase().trim();
    return ROLE_LABELS[normalized] || humanize(normalized);
}

function statusLabel(status) {
    if (!status) return '';
    return STATUS_LABELS[String(status).toLowerCase().trim()] || humanize(status);
}

function fieldLabel(field) {
    return FIELD_LABELS[field] || humanize(field);
}

function humanize(value) {
    return String(value || '')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function dateLabel(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Sin fecha';
    return new Intl.DateTimeFormat('es-MX', {
        dateStyle: 'short',
        timeStyle: 'short',
    }).format(date);
}

function todayDateInput() {
    return dateInputFromValue(new Date());
}

function dateInputFromValue(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

const styles = {
    container: {
        maxWidth: '1400px',
        margin: '0 auto',
        padding: '34px 28px 56px',
        color: '#252525',
    },
    header: {
        marginBottom: '22px',
        borderBottom: '1px solid var(--border, #f3c6cc)',
        paddingBottom: '20px',
    },
    kicker: {
        display: 'inline-block',
        color: 'var(--sb-primary, #e96f7d)',
        fontSize: '13px',
        fontWeight: 800,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        marginBottom: '10px',
    },
    title: {
        margin: 0,
        fontSize: '30px',
        lineHeight: 1,
        fontWeight: 600,
    },
    description: {
        margin: '12px 0 0',
        color: '#5f5f5f',
        fontSize: '14px',
        lineHeight: 1.55,
        fontWeight: 500,
    },
    toolbar: {
        display: 'flex',
        gap: '16px',
        flexWrap: 'wrap',
        alignItems: 'end',
        marginBottom: '18px',
    },
    filterLabel: {
        display: 'flex',
        flexDirection: 'column',
        gap: '7px',
        color: '#222',
        fontSize: '14px',
        fontWeight: 700,
    },
    select: {
        minWidth: '200px',
        height: '35px',
        border: '1px solid var(--border, #f3c6cc)',
        borderRadius: '8px',
        background: '#fff',
        color: '#333',
        padding: '0 12px',
        fontSize: '14px',
    },

    selectCal: {
        minWidth: '200px',
        height: '35px',
        border: '1px solid var(--border, #f3c6cc)',
        borderRadius: '8px',
        background: '#fff',
        color: '#333',
        padding: '0 12px',
        fontSize: '14px',

        // Forzar el tema claro para el calendario desplegable nativo
        colorScheme: 'light', 
        
        // Cambiar el color de acento/selección (puedes usar el rosa corporativo o el tono que gustes)
        accentColor: 'var(--sb-sendBtnBg)',

        cursor: 'pointer',
    },


    todayButton: {
        height: '35px',
        border: '1px solid var(--sb-btnBorder, #f0a4ae)',
        borderRadius: '10px',
        background: 'var(--sb-sendBtnBg)',
        color: 'var(--text-CBtn)',
        padding: '0 15px',
        fontSize: '14px',
        fontWeight: 800,
        cursor: 'pointer',
    },
    summaryGrid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '30px',
        marginBottom: '30px',
    },
    summaryCard: {
        border: '1px solid var(--border)',
        borderRadius: '10px',
        background: '#fffafa',
        padding: '15px',
    },
    summaryLabel: {
        display: 'block',
        color: '#3e3e3e',
        fontSize: '14px',
        fontWeight: 600,
    },
    summaryValue: {
        display: 'block',
        marginTop: '8px',
        color: '#222',
        fontSize: '30px',
        lineHeight: 1,
    },
    panel: {
        border: '1px solid var(--border, #f3c6cc)',
        borderRadius: '5px',
        background: '#fff',
        boxShadow: '0 10px 28px rgba(230, 112, 126, 0.08)',
        overflow: 'hidden',
    },
    
    tableWrap: {
        overflowX: 'auto',
        borderTop: '1px solid #f5d5da',
    },
    table: {
        width: '100%',
        borderCollapse: 'collapse',
        minWidth: '1120px',
    },
    th: {
        padding: '12px 14px',
        background: '#fff8f9',
        borderBottom: '1px solid var(--border)',
        color: '#333',
        fontSize: '14px',
        fontWeight: 700,
        textAlign: 'center',
        textTransform: 'uppercase',
        letterSpacing: '0.03em',
    },
    tr: {
        borderBottom: '1px solid #fed5db',
    },
    td: {
        padding: '14px',
        color: '#555',
        fontSize: '13px',
        verticalAlign: 'center',
    },
    tdStrong: {
        padding: '14px',
        color: '#222',
        fontSize: '13px',
        fontWeight: 600,
        verticalAlign: 'center',
    },
    detailTd: {
        padding: '14px',
        color: '#555',
        fontSize: '13px',
        lineHeight: 1.45,
        verticalAlign: 'center',
        textAlign: 'left',
        maxWidth: '340px',
    },
    badge: {
        display: 'inline-block',
        border: '1px solid #f0a4ae',
        borderRadius: '999px',
        color: '#d66b78',
        background: '#fff8f9',
        padding: '5px 10px',
        fontSize: '12px',
        fontWeight: 600,
        whiteSpace: 'nowrap',
    },
    message: {
        padding: '30px 24px',
        color: '#666',
        fontSize: '15px',
    },
    errorBox: {
        margin: '18px 24px 24px',
        padding: '14px 16px',
        border: '1px solid #f4b4b4',
        borderRadius: '8px',
        background: '#fff5f5',
        color: '#b42318',
        whiteSpace: 'pre-line',
    },
};

export default Bitacora;

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
    apiErrorMessage,
    currentToken,
    getManagementProductivityDashboard,
    getManagerProductivityDashboard,
    getTreasuryDashboard,
    getTreasuryProductivityDashboard,
} from '../lib/api';

function Dashboard({ currentRole }) {
    const role = String(currentRole || '').toLowerCase().trim();
    const canViewManagement = ['admin', 'direccion', 'gerencia'].includes(role);
    const canViewTeamProductivity = ['admin', 'direccion'].includes(role);
    const canViewTreasury = ['admin', 'direccion', 'gerencia', 'tesoreria'].includes(role);

    return (
        <>
            {canViewManagement && <ManagementProductivityDashboard />}
            {canViewTeamProductivity && <ManagerProductivityDashboard />}
            {canViewTeamProductivity && <TreasuryProductivityDashboard />}
            {canViewTreasury && <TreasuryBudgetDashboard />}
        </>
    );
}

function TreasuryBudgetDashboard() {
    const navigate = useNavigate();
    const [dashboard, setDashboard] = useState(null);
    const [selectedStoreId, setSelectedStoreId] = useState('all');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        let active = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                active = false;
            };
        }

        getTreasuryDashboard()
            .then((data) => {
                if (!active) return;
                setDashboard(data);
                setError('');
            })
            .catch((requestError) => {
                if (!active) return;
                setError(apiErrorMessage(requestError));
            })
            .finally(() => {
                if (active) setLoading(false);
            });

        return () => {
            active = false;
        };
    }, [navigate]);

    const years = useMemo(() => dashboard?.years || [], [dashboard]);
    const rows = useMemo(() => dashboard?.rows || [], [dashboard]);
    const visibleRows = useMemo(() => {
        if (selectedStoreId === 'all') return rows;
        return rows.filter((row) => String(row.storeId) === selectedStoreId);
    }, [rows, selectedStoreId]);

    const totalsByYear = useMemo(() => (
        years.map((year) => ({
            year,
            amount: visibleRows.reduce(
                (sum, row) => sum + valueForYear(row, year),
                0,
            ),
        }))
    ), [years, visibleRows]);

    const currentYearData = totalsByYear.at(-1) || { year: '', amount: 0 };
    const previousYearData = totalsByYear.at(-2) || { year: '', amount: 0 };
    const annualVariance = previousYearData.amount
        ? ((currentYearData.amount - previousYearData.amount) / previousYearData.amount) * 100
        : null;

    if (loading) {
        return <div style={styles.message}>Cargando dashboard...</div>;
    }

    if (error) {
        return <div style={styles.errorBox}>{error}</div>;
    }

    return (
        <div style={styles.container}>
            <h1 style={styles.title}>Análisis de Presupuestos</h1>

            <div style={styles.filterRow}>
                <label htmlFor="store-filter" style={styles.filterLabel}>Tienda: </label>
                <select
                    id="store-filter"
                    value={selectedStoreId}
                    onChange={(event) => setSelectedStoreId(event.target.value)}
                    style={styles.select}
                >
                    <option value="all">Todas</option>
                    {(dashboard?.stores || []).map((store) => (
                        <option key={store.id} value={store.id}>
                            {store.code} - {store.name}
                        </option>
                    ))}
                </select>
            </div>

            <section style={styles.section}>
                <p style={styles.sectionLabel}>KPI&apos;s</p>
                <div style={styles.kpiGrid}>
                    <KpiCard
                        label={`Acumulado ${currentYearData.year}`}
                        value={formatCurrency(currentYearData.amount)}
                    />
                    <KpiCard
                        label="% Variación anual"
                        value={annualVariance === null ? 'N/A' : formatPercent(annualVariance)}
                    />
                    <KpiCard
                        label={`Acumulado ${previousYearData.year}`}
                        value={formatCurrency(previousYearData.amount)}
                    />
                </div>
            </section>

            <section style={styles.chartSection}>
                <BarChart totalsByYear={totalsByYear} />
            </section>

            <section style={styles.tableSection}>
                <table style={styles.table}>
                    <thead>
                        <tr>
                            <th style={{ ...styles.th, ...styles.storeTh }}>Tienda</th>
                            {years.map((year) => (
                                <th key={year} style={styles.th}>{year}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {visibleRows.map((row) => (
                            <tr key={row.storeId}>
                                <td style={{ ...styles.td, ...styles.storeTd }}>
                                    <strong>{row.storeCode}</strong>
                                    <span style={styles.storeName}>{row.storeName}</span>
                                </td>
                                {years.map((year) => (
                                    <td key={year} style={styles.td}>
                                        {formatCurrency(valueForYear(row, year))}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        {visibleRows.length === 0 && (
                            <tr>
                                <td style={styles.emptyCell} colSpan={years.length + 1}>
                                    No hay información para mostrar.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </section>
        </div>
    );
}

function KpiCard({ label, value }) {
    return (
        <div style={styles.kpiCard}>
            <span style={styles.kpiLabel}>{label}</span>
            <strong style={styles.kpiValue}>{value}</strong>
        </div>
    );
}

function ManagementProductivityDashboard() {
    return (
        <ProductivityDashboard
            title="Análisis de Productividad"
            subjectLabel="Contador"
            monthlyTitle="TOTAL MENSUAL POR CONTADOR"
            emptyMessage="No hay contadores activos para mostrar."
            fetchDashboard={getManagementProductivityDashboard}
        />
    );
}

function ManagerProductivityDashboard() {
    return (
        <ProductivityDashboard
            title="Productividad de Gerencia"
            subjectLabel="Gerente"
            monthlyTitle="TOTAL MENSUAL POR GERENTE"
            emptyMessage="No hay gerentes activos para mostrar."
            fetchDashboard={getManagerProductivityDashboard}
        />
    );
}

function TreasuryProductivityDashboard() {
    return (
        <ProductivityDashboard
            title="Productividad de Tesorería"
            subjectLabel="Tesorero"
            monthlyTitle="TOTAL MENSUAL POR TESORERO"
            emptyMessage="No hay tesoreros activos para mostrar."
            fetchDashboard={getTreasuryProductivityDashboard}
        />
    );
}

function ProductivityDashboard({ title, subjectLabel, monthlyTitle, emptyMessage, fetchDashboard }) {
    const navigate = useNavigate();
    const [dashboard, setDashboard] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [selectedWeekStart, setSelectedWeekStart] = useState(() => startOfWeekInput(todayInputDate()));
    const [selectedMonth, setSelectedMonth] = useState(() => currentMonthInput());
    const [selectedYear, setSelectedYear] = useState(() => currentYearInput());

    useEffect(() => {
        let active = true;

        if (!currentToken()) {
            navigate('/login');
            return () => {
                active = false;
            };
        }

        setLoading(true);
        fetchDashboard({
            weekStart: selectedWeekStart,
            month: selectedMonth,
            year: selectedYear,
        })
            .then((data) => {
                if (!active) return;
                setDashboard(data);
                setError('');
            })
            .catch((requestError) => {
                if (!active) return;
                setError(apiErrorMessage(requestError));
            })
            .finally(() => {
                if (active) setLoading(false);
            });

        return () => {
            active = false;
        };
    }, [fetchDashboard, navigate, selectedMonth, selectedWeekStart, selectedYear]);

    const { days, actions, rows, monthlyRows, totals, totalsByAction, grandTotal } = useMemo(
        () => normalizeProductivityDashboard(dashboard),
        [dashboard],
    );
    const hasActions = actions.length > 0;
    const maxValue = Math.max(
        1,
        ...rows.flatMap((row) => days.map((day) => productivityValue(row, day))),
        ...days.map((day) => Number(totals[day] || 0)),
    );
    const footerRows = [
        ...(actions.length > 1
            ? actions.map((action) => ({
                key: action.key,
                label: action.label,
                actionKey: action.key,
                values: totalsByAction[action.key] || {},
            }))
            : []),
        { key: 'all', label: 'Total', actionKey: '', values: totals },
    ];

    if (loading) {
        return <div style={styles.message}>Cargando dashboard...</div>;
    }

    if (error) {
        return <div style={styles.errorBox}>{error}</div>;
    }

    return (
        <div style={styles.container}>
            <h1 style={styles.title}>{title}</h1>

            <section style={styles.productivityHeader}>
                <div>
                    <span style={styles.sectionLabel}>TABLA SEMANAL:  </span>
                    <span style={styles.weekLabel}>
                        {formatDateShort(dashboard?.weekStartsOn)} - {formatDateShort(dashboard?.weekEndsOn)}
                    </span>
                </div>
                <div style={styles.periodControls}>
                    <button
                        type="button"
                        style={styles.smallButton}
                        onClick={() => setSelectedWeekStart(addDaysToInput(selectedWeekStart, -7))}
                    >
                        ⫷
                    </button>
                    <input
                        type="date"
                        value={selectedWeekStart}
                        onChange={(event) => setSelectedWeekStart(startOfWeekInput(event.target.value))}
                        style={styles.dateInput}
                    />
                    <button
                        type="button"
                        style={styles.smallButton}
                        onClick={() => setSelectedWeekStart(addDaysToInput(selectedWeekStart, 7))}
                    >
                        ⫸
                    </button>
                </div>
            </section>

            <section style={styles.tableSection}>
                <table style={styles.table}>
                    <thead>
                        <tr>
                            <th style={{ ...styles.th, ...styles.storeTh, ...(hasActions ? styles.compactTh : {}) }}>{subjectLabel}</th>
                            {hasActions && (
                                <th style={{ ...styles.th, ...styles.storeTh, ...styles.compactTh }}>Acción</th>
                            )}
                            {days.map((day) => (
                                <th key={day} style={styles.heatmapTh}>{day}</th>
                            ))}
                            <th style={styles.heatmapTh}>Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, index) => (
                            <tr key={`${row.id}-${row.actionKey}`}>
                                {(index === 0 || rows[index - 1].id !== row.id) && (
                                    <td
                                        rowSpan={actions.length || 1}
                                        style={{ ...styles.td, ...styles.storeTd }}
                                    >
                                        <strong>{row.name}</strong>
                                    </td>
                                )}
                                {hasActions && (
                                    <td style={{ ...styles.td, ...styles.storeTd }}>
                                        <span style={{ ...styles.actionChip, ...actionStyle(row.actionKey).chip }}>
                                            {row.actionLabel}
                                        </span>
                                    </td>
                                )}
                                {days.map((day) => {
                                    const value = productivityValue(row, day);
                                    return (
                                        <td
                                            key={day}
                                            style={{
                                                ...styles.heatmapCell,
                                                background: heatmapColor(value, maxValue),
                                            }}
                                        >
                                            {value || '-'}
                                        </td>
                                    );
                                })}
                                <td style={styles.heatmapTotalCell}>{row.total}</td>
                            </tr>
                        ))}
                        {rows.length === 0 && (
                            <tr>
                                <td style={styles.emptyCell} colSpan={days.length + (hasActions ? 3 : 2)}>
                                    {emptyMessage}
                                </td>
                            </tr>
                        )}
                    </tbody>
                    <tfoot>
                        {footerRows.map((footerRow, footerIndex) => {
                            const isGrandTotal = footerRow.key === 'all';
                            const footerBorder = footerIndex === 0 ? {} : { borderTop: '1px solid #f1dada' };
                            return (
                                <tr key={footerRow.key}>
                                    <td
                                        colSpan={hasActions ? 2 : 1}
                                        style={{ ...styles.td, ...styles.storeTd, ...footerBorder }}
                                    >
                                        {isGrandTotal ? (
                                            <strong>{footerRow.label}</strong>
                                        ) : (
                                            <>
                                                <strong>Total </strong>
                                                <span style={{ ...styles.actionChip, ...actionStyle(footerRow.actionKey).chip }}>
                                                    {footerRow.label}
                                                </span>
                                            </>
                                        )}
                                    </td>
                                    {days.map((day) => {
                                        const value = Number(footerRow.values[day] || 0);
                                        return (
                                            <td
                                                key={day}
                                                style={{
                                                    ...styles.heatmapFooterCell,
                                                    ...footerBorder,
                                                    background: heatmapColor(value, maxValue),
                                                }}
                                            >
                                                {value || '-'}
                                            </td>
                                        );
                                    })}
                                    <td style={{ ...styles.heatmapGrandTotalCell, ...footerBorder }}>
                                        {isGrandTotal
                                            ? grandTotal
                                            : days.reduce((sum, day) => sum + Number(footerRow.values[day] || 0), 0)}
                                    </td>
                                </tr>
                            );
                        })}
                    </tfoot>
                </table>
            </section>

            <section style={styles.monthlySection}>
                <div style={styles.productivityHeader}>
                    <div>
                        <span style={styles.sectionLabel}>{monthlyTitle}</span>
                        <span style={styles.weekLabel}>
                            {formatMonthYear(dashboard?.month || selectedMonth, dashboard?.year || selectedYear)}
                        </span>
                    </div>
                    <div style={styles.periodControls}>
                        <select
                            value={selectedMonth}
                            onChange={(event) => setSelectedMonth(Number(event.target.value))}
                            style={styles.monthSelect}
                        >
                            {MONTH_OPTIONS.map((monthOption) => (
                                <option key={monthOption.value} value={monthOption.value}>
                                    {monthOption.label}
                                </option>
                            ))}
                        </select>
                        <input
                            type="number"
                            min="2020"
                            max="2100"
                            value={selectedYear}
                            onChange={(event) => setSelectedYear(Number(event.target.value) || currentYearInput())}
                            style={styles.yearInput}
                        />
                    </div>
                </div>
                <MonthlyProductivityBarChart
                    rows={monthlyRows}
                    actions={actions}
                    grandTotal={dashboard?.monthlyGrandTotal || 0}
                    emptyMessage={emptyMessage}
                />
            </section>
        </div>
    );
}

function MonthlyProductivityBarChart({ rows, actions, grandTotal, emptyMessage }) {
    const maxTotal = Math.max(1, ...rows.map((row) => Number(row.total || 0)));
    const multiAction = actions.length > 1;
    const groups = [];
    rows.forEach((row) => {
        const lastGroup = groups.at(-1);
        if (lastGroup && lastGroup.id === row.id) {
            lastGroup.items.push(row);
        } else {
            groups.push({ id: row.id, name: row.name, items: [row] });
        }
    });

    return (
        <div style={styles.monthlyChartContainer}>
            <div style={styles.monthlyChartHeader}>
                <span>Total del mes</span>
                <strong>{grandTotal}</strong>
            </div>
            {multiAction && (
                <div style={styles.legend}>
                    {actions.map((action) => (
                        <span key={action.key} style={{ ...styles.actionChip, ...actionStyle(action.key).chip }}>
                            {action.label}
                        </span>
                    ))}
                </div>
            )}
            <div style={styles.monthlyChart}>
                {groups.map((group) => (
                    <div
                        key={group.id}
                        style={{
                            ...styles.monthlyBarGroup,
                            width: multiAction ? `${group.items.length * 52 + 30}px` : undefined,
                            minWidth: multiAction ? `${group.items.length * 52 + 30}px` : undefined,
                        }}
                    >
                        <div style={multiAction ? styles.monthlyBarRow : styles.monthlyBarWrap}>
                            {group.items.map((item) => {
                                const total = Number(item.total || 0);
                                const height = Math.max((total / maxTotal) * 220, total > 0 ? 18 : 6);
                                return (
                                    <div
                                        key={item.actionKey || 'total'}
                                        style={multiAction ? styles.monthlyBarWrap : styles.monthlyBarSingle}
                                        title={item.actionLabel || undefined}
                                    >
                                        <span style={styles.monthlyBarValue}>{total}</span>
                                        <div
                                            style={{
                                                ...styles.monthlyBar,
                                                ...(multiAction ? styles.monthlyBarNarrow : {}),
                                                ...actionStyle(item.actionKey).bar,
                                                height,
                                            }}
                                        />
                                    </div>
                                );
                            })}
                        </div>
                        <span style={styles.monthlyBarName}>{group.name}</span>
                    </div>
                ))}
                {groups.length === 0 && (
                    <div style={styles.emptyChart}>
                        {emptyMessage}
                    </div>
                )}
            </div>
        </div>
    );
}

function BarChart({ totalsByYear }) {
    const maxAmount = Math.max(...totalsByYear.map((item) => item.amount), 1);

    return (
        <div style={styles.chartContainer}>
            {/* 🛠️ CAMBIO: Se agrega el contenedor de la cuadrícula / Grid horizontal */}
            <div style={styles.gridOverlay}>
                <div style={styles.gridLine} />
                <div style={styles.gridLine} />
                <div style={styles.gridLine} />
                <div style={styles.gridLine} />
            </div>
            <div style={styles.chart}>
                {totalsByYear.map((item) => {
                    const height = Math.max((item.amount / maxAmount) * 210, item.amount > 0 ? 18 : 6);
                    return (
                        <div key={item.year} style={styles.barGroup}>
                            <div style={styles.barWrap}>
                                <span style={styles.barValue}>{formatCurrencyCompact(item.amount)}</span>
                                <div style={{ ...styles.bar, height }} />
                            </div>
                            <div style={styles.barYearContainer}>
                                <span style={styles.barYear}>{item.year}</span>
                            </div>
                        </div>
                    );
                })} 
            </div>
        </div>
    );
}

const MONTH_OPTIONS = [
    { value: 1, label: 'Enero' },
    { value: 2, label: 'Febrero' },
    { value: 3, label: 'Marzo' },
    { value: 4, label: 'Abril' },
    { value: 5, label: 'Mayo' },
    { value: 6, label: 'Junio' },
    { value: 7, label: 'Julio' },
    { value: 8, label: 'Agosto' },
    { value: 9, label: 'Septiembre' },
    { value: 10, label: 'Octubre' },
    { value: 11, label: 'Noviembre' },
    { value: 12, label: 'Diciembre' },
];

function valueForYear(row, year) {
    return Number(row?.values?.[year] ?? row?.values?.[String(year)] ?? 0);
}

function productivityValue(row, day) {
    return Number(row?.values?.[day] || 0);
}

const DEFAULT_PRODUCTIVITY_DAYS = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi'];

const ACTION_STYLES = {
    send_to_treasury: {
        chip: {
            background: 'var(--sb-sendBtnBg)',
            border: '1px solid var(--sb-sendBtnBg)',
            color: '#ffffff',
        },
        bar: {
            background: 'linear-gradient(180deg, #fff8f8 0%, #ff9ca5 100%)',
        },
    },
    confirm_payment: {
        chip: {
            background: 'var(--sb-pagadaBg)',
            border: '1px solid var(--text-pagada)',
            color: '#2e7d1f',
        },
        bar: {
            border: '2px solid var(--text-pagada)',
            background: 'linear-gradient(180deg, #f3fcef 0%, #8fd37b 100%)',
        },
    },
    approve_payment: {
        chip: {
            background: 'var(--sb-aprobadaBg)',
            border: '1px solid var(--text-aprobada)',
            color: 'var(--text-aprobada)',
        },
        bar: {
            border: '2px solid var(--text-aprobada)',
            background: 'linear-gradient(180deg, #f1f7ff 0%, #8db8f0 100%)',
        },
    },
};

function actionStyle(actionKey) {
    return ACTION_STYLES[actionKey] || { chip: {}, bar: {} };
}

// Unifica la respuesta de contadores (accountantId/accountantName) con la de gerentes y tesoreros (userId/actionKey).
function normalizeProductivityDashboard(data) {
    const normalizeRow = (row) => ({
        id: row.userId || row.accountantId,
        name: row.userName || row.accountantName,
        actionKey: row.actionKey || '',
        actionLabel: row.actionLabel || '',
        values: row.values || {},
        total: Number(row.total || 0),
    });

    return {
        days: data?.days || DEFAULT_PRODUCTIVITY_DAYS,
        actions: data?.actions || [],
        rows: (data?.rows || []).map(normalizeRow),
        monthlyRows: (data?.monthlyRows || []).map(normalizeRow),
        totals: data?.totals || {},
        totalsByAction: data?.totalsByAction || {},
        grandTotal: data?.grandTotal || 0,
    };
}

function heatmapColor(value, maxValue) {
    if (!value) return '#ffffff';
    const intensity = Math.min(value / Math.max(maxValue, 1), 1);

    // Rangos de opacidad deseados
    const minAlpha = 0.10; // Opacidad mínima para valores bajos
    const maxAlpha = 0.60; // Opacidad máxima para el valor más alto
    
    // Aplica la fórmula proporcional
    const alpha = minAlpha + intensity * (maxAlpha - minAlpha);

    //const alpha = 0.18 + intensity * 0.52;
    return `rgba(255, 122, 122, ${alpha})`;
}

function formatDateShort(value) {
    if (!value) return '';
    const [year, month, day] = String(value).split('-');
    if (!year || !month || !day) return value;
    return `${day}/${month}/${year}`;
}

function todayInputDate() {
    return dateToInputValue(new Date());
}

function currentMonthInput() {
    return new Date().getMonth() + 1;
}

function currentYearInput() {
    return new Date().getFullYear();
}

function startOfWeekInput(value) {
    const date = dateFromInputValue(value) || new Date();
    const mondayOffset = (date.getDay() + 6) % 7;
    date.setDate(date.getDate() - mondayOffset);
    return dateToInputValue(date);
}

function addDaysToInput(value, days) {
    const date = dateFromInputValue(value) || new Date();
    date.setDate(date.getDate() + days);
    return startOfWeekInput(dateToInputValue(date));
}

function dateFromInputValue(value) {
    const [year, month, day] = String(value || '').split('-').map(Number);
    if (!year || !month || !day) return null;
    const date = new Date(year, month - 1, day);
    if (Number.isNaN(date.getTime())) return null;
    return date;
}

function dateToInputValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatMonthYear(month, year) {
    const monthName = MONTH_OPTIONS.find((item) => item.value === Number(month))?.label || '';
    return `${monthName} ${year || ''}`.trim();
}

function formatCurrency(value) {
    return new Intl.NumberFormat('es-MX', {
        style: 'currency',
        currency: 'MXN',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(value || 0));
}

function formatCurrencyCompact(value) {
    return new Intl.NumberFormat('es-MX', {
        style: 'currency',
        currency: 'MXN',
        notation: 'compact',
        maximumFractionDigits: 1,
    }).format(Number(value || 0));
}

function formatPercent(value) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
}

const styles = {
    container: {
        width: 'min(1080px, 100%)',
        margin: '0 auto',
        padding: '8px 0 36px',
        color: '#222',
    },
    title: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '30px',
    },
    filterRow: {
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        marginBottom: '34px',
        flexWrap: 'wrap',
    },
    filterLabel: {
        fontSize: '17px',
        fontWeight: '700',
    },
    periodControls: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: '10px',
        flexWrap: 'wrap',
    },
    smallButton: {
        minHeight: '38px',
        background: 'transparent', // Cambiado a transparente
        border: 'none',            // Elimina el borde nativo del botón
        outline: 'none',           // Elimina el contorno de enfoque/foco
        boxShadow: 'none',         // Elimina cualquier sombra predeterminada
        color: 'var(--sb-sendBtnBg)',
        padding: '0 5px',
        fontSize: '25px',
        fontWeight: '800',
        cursor: 'pointer',
    },
    dateInput: {
        width: '150px',
        height: '38px',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        background: '#fff',
        color: '#222',
        padding: '0 10px',
        fontSize: '14px',
        fontWeight: '700',
    },
    monthSelect: {
        width: '150px',
        height: '38px',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        background: '#fff',
        color: '#222',
        padding: '0 10px',
        fontSize: '14px',
        fontWeight: '700',
    },
    yearInput: {
        width: '96px',
        height: '38px',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        background: '#fff',
        color: '#222',
        padding: '0 10px',
        fontSize: '14px',
        fontWeight: '700',
    },
    select: {
        minWidth: '220px',
        maxWidth: '360px',
        height: '42px',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        background: '#fff',
        color: '#222',
        padding: '0 12px',
        fontSize: '15px',
        fontWeight: '600',
    },
    section: {
        marginBottom: '30px',
    },
    sectionLabel: {
        margin: '0 0 12px',
        fontSize: '16px',
        fontWeight: '700',
        color: '#000000',
    },
    productivityHeader: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        margin: '4px 0 18px',
        flexWrap: 'wrap',
    },
    weekLabel: {
        fontSize: '14px',
        fontWeight: '700',
        color: '#373737',
    },
    kpiGrid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '50px',
    },
    kpiCard: {
        minHeight: '80px',
        border: '2px solid var(--sb-btnBorder)',
        borderRadius: '10px',
        background: '#fff',
        boxShadow: 'var(--shadow)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '10px',
    },
    kpiLabel: {
        fontSize: '18px',
        fontWeight: '600',
        color: '#555555',
    },
    kpiValue: {
        fontSize: '30px',
        lineHeight: 1,
        color: '#000000',
    },
    chartSection: {
        margin: '34px 0',
        borderLeft: '0px solid #333',
        borderBottom: '0px solid #333',
        minHeight: '270px',
        padding: '30px 20px 0',
        overflowX: 'auto',
    },

    chartContainer: {
        position: 'relative',
        minWidth: '500px',
    },
    gridOverlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '232px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        pointerEvents: 'none',
        zIndex: 1,
    },
    gridLine: {
        width: '100%',
        borderBottom: '1px dashed #c9c9c9',
    },



    chart: {
        position: 'relative',
        zIndex: 2,
        minWidth: '500px',
        minHeight: '250px',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-around',
        gap: '36px',
        borderBottom: '2px solid #333',
        //minWidth: '500px',
        //minHeight: '250px',
        //display: 'flex',
        //alignItems: 'flex-end',
        //justifyContent: 'space-around',
        //gap: '36px',
    },
    barGroup: {
        width: '140px',
        minWidth: '100px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px',
    },
    barWrap: {
        height: '232px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-end',
        alignItems: 'center',
        gap: '10px',
    },
    barValue: {
        minHeight: '20px',
        fontSize: '15px',
        fontWeight: '700',
        color: '#3a3a3a',
    },
    bar: {
        width: '58px',
        border: '2px solid var(--sb-btnBorder)',
        borderRadius: '6px 6px 0 0',
        background: 'linear-gradient(180deg, #fff1f1 0%, #ffb6b6 100%)',
    },


    barYearContainer: {
        paddingTop: '12px',
        textAlign: 'center',
    },


    barYear: {
        fontSize: '18px',
        fontWeight: '700',
    },
    tableSection: {
        marginTop: '40px',
        overflowX: 'auto',
    },
    monthlySection: {
        marginTop: '42px',
        paddingTop: '28px',
        borderTop: '1px solid #f0d0d0',
    },
    monthlyChartContainer: {
        marginTop: '22px',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        background: '#fff',
        padding: '18px 20px 22px',
        overflowX: 'auto',
    },
    monthlyChartHeader: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '14px',
        marginBottom: '16px',
        fontSize: '15px',
        fontWeight: '800',
        color: '#3d2a2a',
    },
    monthlyChart: {
        minWidth: '620px',
        minHeight: '292px',
        display: 'flex',
        alignItems: 'flex-end',
        gap: '22px',
        borderBottom: '2px solid #333',
        padding: '0 4px 14px',
    },
    monthlyBarGroup: {
        width: '118px',
        minWidth: '118px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: '10px',
    },
    monthlyBarWrap: {
        height: '244px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: '8px',
    },
    monthlyBarValue: {
        minHeight: '18px',
        fontSize: '14px',
        fontWeight: '900',
        color: '#3a3a3a',
    },
    monthlyBar: {
        width: '54px',
        border: '2px solid var(--sb-btnBorder)',
        borderRadius: '6px 6px 0 0',
        background: 'linear-gradient(180deg, #fff8f8 0%, #ff9ca5 100%)',
    },
    monthlyBarName: {
        width: '100%',
        minHeight: '38px',
        fontSize: '12px',
        fontWeight: '800',
        color: '#4f4f4f',
        textAlign: 'center',
        lineHeight: 1.25,
        overflowWrap: 'anywhere',
    },
    emptyChart: {
        width: '100%',
        alignSelf: 'center',
        textAlign: 'center',
        color: '#666',
        fontWeight: '700',
    },
    table: {
        width: '100%',
        borderCollapse: 'collapse',
        background: '#fff',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        overflow: 'hidden',
    },
    th: {
        borderBottom: '1px solid var(--sb-btnBorder)',
        borderRight: '1px solid var(--sb-btnBorder)',
        padding: '13px 16px',
        textAlign: 'right',
        fontSize: '14px',
        background: '#fff8f8',
    },
    storeTh: {
        textAlign: 'left',
        minWidth: '220px',
    },
    compactTh: {
        minWidth: '120px',
    },
    heatmapTh: {
        borderBottom: '1px solid var(--sb-btnBorder)',
        borderRight: '1px solid var(--sb-btnBorder)',
        padding: '13px 16px',
        textAlign: 'center',
        fontSize: '13px',
        background: '#fff8f8',
        minWidth: '88px',
    },
    td: {
        borderTop: '1px solid #f1dada',
        borderRight: '1px solid #f1dada',
        padding: '13px 16px',
        textAlign: 'right',
        fontSize: '14px',
        whiteSpace: 'nowrap',
    },
    storeTd: {
        textAlign: 'left',
        whiteSpace: 'normal',
    },
    heatmapCell: {
        borderTop: '1px solid #f1dada',
        borderRight: '1px solid #f1dada',
        padding: '13px 16px',
        textAlign: 'center',
        fontSize: '14px',
        fontWeight: '800',
        color: '#3d2a2a',
    },
    heatmapTotalCell: {
        borderTop: '1px solid #f1dada',
        borderRight: '1px solid #f1dada',
        padding: '13px 16px',
        textAlign: 'center',
        fontSize: '15px',
        fontWeight: '900',
        background: '#fff8f8',
    },
    heatmapFooterCell: {
        borderTop: '2px solid var(--sb-btnBorder)',
        borderRight: '1px solid #f1dada',
        padding: '13px 16px',
        textAlign: 'center',
        fontSize: '15px',
        fontWeight: '900',
        color: '#3d2a2a',
    },
    heatmapGrandTotalCell: {
        borderTop: '2px solid var(--sb-btnBorder)',
        padding: '13px 16px',
        textAlign: 'center',
        fontSize: '16px',
        fontWeight: '900',
        background: '#ffeaea',
    },
    actionChip: {
        display: 'inline-block',
        padding: '3px 12px',
        borderRadius: '999px',
        fontSize: '12px',
        fontWeight: '800',
        whiteSpace: 'nowrap',
    },
    legend: {
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        flexWrap: 'wrap',
        marginBottom: '14px',
    },
    monthlyBarRow: {
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        gap: '8px',
    },
    monthlyBarSingle: {
        height: '244px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: '8px',
    },
    monthlyBarNarrow: {
        width: '38px',
    },
    storeName: {
        display: 'block',
        marginTop: '3px',
        color: '#666',
        fontSize: '12px',
        fontWeight: '500',
    },
    emptyCell: {
        padding: '22px',
        textAlign: 'center',
        color: '#666',
    },
    message: {
        padding: '32px',
        textAlign: 'center',
        color: '#555',
        fontWeight: '700',
    },
    errorBox: {
        margin: '20px auto',
        maxWidth: '760px',
        padding: '16px 18px',
        border: '1px solid #f0a6a6',
        borderRadius: '8px',
        background: '#fff4f4',
        color: '#9f2f2f',
        fontWeight: '700',
    },
};

export default Dashboard;

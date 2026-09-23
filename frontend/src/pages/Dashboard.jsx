import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiErrorMessage, currentToken, getTreasuryDashboard } from '../lib/api';

function Dashboard() {
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
            <h1 style={styles.title}>Presupuestos (Tesorería)</h1>

            <div style={styles.filterRow}>
                <label htmlFor="store-filter" style={styles.filterLabel}>Selecc. Tienda</label>
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
                        label={`Acum ${currentYearData.year}`}
                        value={formatCurrency(currentYearData.amount)}
                    />
                    <KpiCard
                        label="% variación anual"
                        value={annualVariance === null ? 'N/A' : formatPercent(annualVariance)}
                    />
                    <KpiCard
                        label={`Acum ${previousYearData.year}`}
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

function BarChart({ totalsByYear }) {
    const maxAmount = Math.max(...totalsByYear.map((item) => item.amount), 1);

    return (
        <div style={styles.chart}>
            {totalsByYear.map((item) => {
                const height = Math.max((item.amount / maxAmount) * 210, item.amount > 0 ? 18 : 6);
                return (
                    <div key={item.year} style={styles.barGroup}>
                        <div style={styles.barWrap}>
                            <span style={styles.barValue}>{formatCurrencyCompact(item.amount)}</span>
                            <div style={{ ...styles.bar, height }} />
                        </div>
                        <span style={styles.barYear}>{item.year}</span>
                    </div>
                );
            })}
        </div>
    );
}

function valueForYear(row, year) {
    return Number(row?.values?.[year] ?? row?.values?.[String(year)] ?? 0);
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
        margin: '0 auto 30px',
        width: 'fit-content',
        padding: '0 18px 8px',
        borderBottom: '2px solid var(--sb-btnBorder)',
        fontSize: '26px',
        fontWeight: '800',
        textAlign: 'center',
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
        fontSize: '15px',
        fontWeight: '800',
        color: '#333',
    },
    kpiGrid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '14px',
    },
    kpiCard: {
        minHeight: '94px',
        border: '1px solid var(--sb-btnBorder)',
        borderRadius: '8px',
        background: '#fff',
        boxShadow: 'var(--shadow)',
        padding: '18px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '10px',
    },
    kpiLabel: {
        fontSize: '14px',
        fontWeight: '800',
        color: '#444',
    },
    kpiValue: {
        fontSize: '27px',
        lineHeight: 1,
        color: '#111',
    },
    chartSection: {
        margin: '34px 0',
        borderLeft: '2px solid #333',
        borderBottom: '2px solid #333',
        minHeight: '270px',
        padding: '18px 20px 0',
        overflowX: 'auto',
    },
    chart: {
        minWidth: '520px',
        minHeight: '252px',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-around',
        gap: '36px',
    },
    barGroup: {
        width: '120px',
        minWidth: '90px',
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
        gap: '8px',
    },
    barValue: {
        minHeight: '20px',
        fontSize: '13px',
        fontWeight: '800',
        color: '#333',
    },
    bar: {
        width: '58px',
        border: '2px solid var(--sb-btnBorder)',
        borderRadius: '6px 6px 0 0',
        background: 'linear-gradient(180deg, #fff1f1 0%, #ffb6b6 100%)',
        boxShadow: '0 8px 16px rgba(255, 119, 119, 0.18)',
    },
    barYear: {
        fontSize: '15px',
        fontWeight: '800',
    },
    tableSection: {
        marginTop: '30px',
        overflowX: 'auto',
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

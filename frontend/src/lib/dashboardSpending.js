export function hasSpendingBreakdown(rows, years) {
    return rows.every((row) => typeof row.hasNormalData === 'boolean'
        && typeof row.hasExtemporaneousData === 'boolean'
        && row.normalValues && row.extemporaneousValues && years.every((year) => (
        Number.isFinite(row.normalValues?.[year]) && Number.isFinite(row.extemporaneousValues?.[year])
    )));
}

export function filterSpendingRows(rows, storeId = 'all', type = 'all') {
    if (!['all', 'normal', 'extemporaneous'].includes(type)) throw new Error('Tipo de gasto desconocido.');
    const selected = rows.filter((row) => {
        if (storeId !== 'all' && String(row.storeId) !== storeId) return false;
        // Unknown flags retain legacy rows; zero amounts never imply missing records.
        if (type === 'normal') return row.hasNormalData !== false;
        if (type === 'extemporaneous') return row.hasExtemporaneousData !== false;
        return row.hasNormalData !== false || row.hasExtemporaneousData !== false;
    });
    if (type === 'all') return selected;
    const field = type === 'normal' ? 'normalValues' : 'extemporaneousValues';
    return selected.map((row) => ({ ...row, values: row[field] }));
}

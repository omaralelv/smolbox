const manualAreaCategories = new Set([
    'PASAJES Y TAXIS', 'TAXIS', 'TAXI', 'NO DEDUCIBLE', 'NO DEDUCIBLES',
]);

export function categoryRequiresManualAuthorizationArea(category) {
    const normalized = String(category || '')
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .toUpperCase()
        .replace(/[^A-Z0-9]+/g, ' ')
        .trim();
    return manualAreaCategories.has(normalized);
}

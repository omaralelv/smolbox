export function formatoFechaGasto(value) {
    if (!value) return '—';

    const dateString = String(value);
    const isoDate = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(dateString);
    if (isoDate) {
        return `${isoDate[3]}/${isoDate[2]}/${isoDate[1]}`;
    }

    const localDate = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(dateString);
    if (localDate) {
        return `${localDate[1].padStart(2, '0')}/${localDate[2].padStart(2, '0')}/${localDate[3]}`;
    }

    return '—';
}

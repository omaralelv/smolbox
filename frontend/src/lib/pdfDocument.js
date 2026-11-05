export const PDF_FIELD_LABELS = { date: 'Fecha', total: 'Monto', folio: 'Folio fiscal' };

export function normalizePdfHighlights(highlights, pageCount) {
    if (!Array.isArray(highlights)) return [];
    return highlights.slice(0, 200).filter((item) => item && Object.hasOwn(PDF_FIELD_LABELS, item.field)
        && Number.isInteger(item.page) && item.page >= 1 && item.page <= pageCount
        && [item.left, item.top, item.width, item.height].every(Number.isFinite)
        && item.left >= 0 && item.left < 1 && item.top >= 0 && item.top < 1 && item.width > 0 && item.height > 0
        && item.left + item.width <= 1.001 && item.top + item.height <= 1.001
    ).map((item) => ({
        field: item.field, page: item.page, left: item.left, top: item.top,
        width: Math.min(item.width, 1 - item.left), height: Math.min(item.height, 1 - item.top),
    }));
}

export function pdfCanvasSize(width, height, pixelRatio = 1) {
    if (![width, height].every((value) => Number.isFinite(value) && value > 0)) return null;
    const ratio = Math.min(Number.isFinite(pixelRatio) && pixelRatio > 0 ? pixelRatio : 1,
        2, 8192 / Math.max(width, height), Math.sqrt(8_000_000 / (width * height)));
    const canvasWidth = Math.max(1, Math.floor(width * ratio));
    const canvasHeight = Math.max(1, Math.floor(height * ratio));
    return { width: canvasWidth, height: canvasHeight, transform: [canvasWidth / width, 0, 0, canvasHeight / height, 0, 0] };
}

export function pdfScale(mode, size, page) {
    if (typeof mode === 'number') return Math.min(4, Math.max(0.01, mode));
    const width = Math.max(1, size.width - 28) / page.width;
    return mode === 'page' ? Math.min(width, Math.max(1, size.height - 28) / page.height) : width;
}

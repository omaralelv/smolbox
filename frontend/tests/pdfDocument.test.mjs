import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizePdfHighlights, pdfCanvasSize, pdfScale } from '../src/lib/pdfDocument.js';

const valid = { field: 'folio', page: 2, left: .1, top: .2, width: .7, height: .03 };
test('document marks accept only known fields, valid pages and finite normalized bounds', () => {
    assert.deepEqual(normalizePdfHighlights([valid], 2), [valid]);
    for (const change of [{ field: 'other' }, { page: 3 }, { page: 0 }, { page: 1.1 },
        { left: -1 }, { top: NaN }, { width: Infinity }, { height: 0 }, { width: .99 }]) {
        assert.deepEqual(normalizePdfHighlights([{ ...valid, ...change }], 2), []);
    }
    assert.deepEqual(normalizePdfHighlights(null, 2), []);
    assert.deepEqual(normalizePdfHighlights([], 2), []);
    assert.deepEqual(normalizePdfHighlights([valid], 0), []);
});
test('PDF bitmap dimensions remain bounded at high zoom and device pixel ratios', () => {
    for (const [w, h] of [[612, 792], [10000, 20000], [50000, 500], [1, 1]]) {
        const size = pdfCanvasSize(w, h, 4);
        assert.ok(size.width * size.height <= 8_000_000);
        assert.ok(size.width <= 8192 && size.height <= 8192);
        assert.equal(size.transform[0], size.width / w);
        assert.equal(size.transform[3], size.height / h);
    }
    assert.equal(pdfCanvasSize(0, 1), null);
    assert.equal(pdfCanvasSize(Infinity, 1), null);
});
test('fit width and full-page zoom preserve aspect ratio, and manual zoom has limits', () => {
    const page = { width: 612, height: 792 }, size = { width: 400, height: 400 };
    assert.equal(pdfScale('width', size, page), 372 / 612);
    assert.equal(pdfScale('page', size, page), 372 / 792);
    assert.equal(pdfScale(2, size, page), 2);
    assert.equal(pdfScale(99, size, page), 4);
    assert.equal(pdfScale(0, size, page), .01);
});

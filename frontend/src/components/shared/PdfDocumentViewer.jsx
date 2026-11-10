import { useEffect, useId, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeftRight, ChevronLeft, ChevronRight, Download, Maximize2, Minimize2, Scan, ZoomIn, ZoomOut } from 'lucide-react';
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { normalizePdfHighlights, PDF_FIELD_LABELS, pdfCanvasSize, pdfScale } from '../../lib/pdfDocument';
import './PdfDocumentViewer.css';

GlobalWorkerOptions.workerSrc = workerUrl;
const assets = `${import.meta.env.BASE_URL}${import.meta.env.DEV ? 'node_modules/pdfjs-dist/' : 'pdfjs/'}`;

export default function PdfDocumentViewer({ file, highlights, auditCaptureId, ref }) {
    const viewerId = useId();
    const [documentState, setDocumentState] = useState({ pdf: null, nativeUrl: '', error: '' });
    const [pageNumber, setPageNumber] = useState(1);
    const [pageState, setPageState] = useState({ number: 0, page: null });
    const [zoom, setZoom] = useState('width');
    const [size, setSize] = useState({ width: 400, height: 600 });
    const [expanded, setExpanded] = useState(false);
    const [activeField, setActiveField] = useState(null);
    const [renderState, setRenderState] = useState('loading');
    const [paintedViewport, setPaintedViewport] = useState(null);
    const scroller = useRef(null);
    const canvas = useRef(null);
    const root = useRef(null);
    const expandButton = useRef(null);
    const renderTask = useRef(null);
    const pdf = documentState.pdf;
    const page = pageState.number === pageNumber ? pageState.page : null;
    const regions = useMemo(() => normalizePdfHighlights(highlights, pdf?.numPages || 0), [highlights, pdf]);
    const scale = page ? pdfScale(zoom, size, page.getViewport({ scale: 1 })) : 1;
    const viewport = useMemo(() => page?.getViewport({ scale }), [page, scale]);
    const ready = renderState === 'ready' && paintedViewport?.viewport === viewport && paintedViewport.expanded === expanded;

    useImperativeHandle(ref, () => ({
        focusField(field) {
            setActiveField(field);
            const region = regions.find((item) => item.field === field);
            if (region) setPageNumber(region.page);
        },
    }), [regions]);

    useEffect(() => {
        let stopped = false, task, nativeUrl;
        (async () => {
            const data = new Uint8Array(await file.arrayBuffer());
            if (stopped) return;
            task = getDocument({ data, isEvalSupported: false, enableXfa: false,
                cMapUrl: `${assets}cmaps/`, cMapPacked: true,
                standardFontDataUrl: `${assets}standard_fonts/`, wasmUrl: `${assets}wasm/` });
            const loaded = await task.promise;
            if (!stopped) setDocumentState({ pdf: loaded, nativeUrl: '', error: '' });
        })().catch(() => {
            if (stopped) return;
            nativeUrl = URL.createObjectURL(new Blob([file], { type: 'application/pdf' }));
            setDocumentState({ pdf: null, nativeUrl, error: 'Vista previa del PDF' });
        });
        return () => {
            stopped = true;
            if (task) void task.destroy().catch(() => {});
            if (nativeUrl) URL.revokeObjectURL(nativeUrl);
        };
    }, [file]);

    useEffect(() => {
        if (!pdf) return undefined;
        let stopped = false;
        pdf.getPage(pageNumber).then((loaded) => {
            if (!stopped) setPageState({ number: pageNumber, page: loaded });
        }).catch(() => { if (!stopped) setRenderState('error'); });
        return () => { stopped = true; };
    }, [pdf, pageNumber]);

    useEffect(() => {
        const element = scroller.current;
        if (!element) return undefined;
        const observer = new ResizeObserver(() => {
            const width = element.clientWidth, height = element.clientHeight;
            setSize((old) => old.width === width && old.height === height ? old : { width, height });
        });
        observer.observe(element);
        return () => observer.disconnect();
    }, [expanded, documentState.nativeUrl]);

    useEffect(() => {
        if (!page || !viewport || !canvas.current) return undefined;
        let stopped = false, currentTask;
        (async () => {
            const previous = renderTask.current;
            previous?.cancel();
            await previous?.promise.catch(() => {});
            if (stopped) return;
            setRenderState('loading');
            const dimensions = pdfCanvasSize(viewport.width, viewport.height, window.devicePixelRatio);
            const element = canvas.current;
            element.width = dimensions.width; element.height = dimensions.height;
            currentTask = page.render({ canvas: element, viewport, transform: dimensions.transform });
            renderTask.current = currentTask;
            await currentTask.promise;
            if (!stopped) {
                setPaintedViewport({ viewport, expanded });
                setRenderState('ready');
            }
        })().catch((error) => {
            if (!stopped && error.name !== 'RenderingCancelledException') setRenderState('error');
        });
        return () => { stopped = true; currentTask?.cancel(); };
    }, [page, viewport, expanded]);

    useEffect(() => {
        if (!activeField || !ready) return;
        const marker = root.current?.querySelector(`[data-pdf-highlight="${activeField}"]`);
        const container = scroller.current;
        if (marker && container) {
            const target = marker.getBoundingClientRect(), bounds = container.getBoundingClientRect();
            container.scrollTo({
                top: Math.max(0, container.scrollTop + target.top - bounds.top - container.clientHeight / 2),
                left: Math.max(0, container.scrollLeft + target.left - bounds.left - container.clientWidth / 2),
            });
        }
    }, [activeField, pageNumber, ready]);

    useEffect(() => {
        if (!expanded) return undefined;
        const application = document.getElementById('root');
        const oldInert = application?.inert;
        const overflow = document.body.style.overflow;
        if (application) application.inert = true;
        document.body.style.overflow = 'hidden';
        expandButton.current?.focus();
        const handleKeys = (event) => {
            if (event.key === 'Escape') { event.preventDefault(); setExpanded(false); }
            if (event.key === 'Tab') {
                const items = [...root.current.querySelectorAll('button:not(:disabled), input:not(:disabled), [tabindex="0"]')];
                const first = items[0], last = items.at(-1);
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
                else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            }
        };
        document.addEventListener('keydown', handleKeys);
        return () => {
            if (application) application.inert = oldInert;
            document.body.style.overflow = overflow;
            document.removeEventListener('keydown', handleKeys);
            requestAnimationFrame(() => document.getElementById(viewerId)?.querySelector('[data-pdf-expand]')?.focus());
        };
    }, [expanded, viewerId]);

    const tool = (Icon, label, action, disabled = false, extra = {}) => (
        <button type="button" title={label} aria-label={label} onClick={action} disabled={disabled} {...extra}><Icon size={18} aria-hidden="true" /></button>
    );
    const viewer = (
        <section id={viewerId} ref={root} className={`pdf-document-viewer${expanded ? ' is-expanded' : ''}`}
            data-audit-capture-id={auditCaptureId}
            role={expanded ? 'dialog' : 'region'} aria-modal={expanded || undefined}
            aria-label={expanded ? 'Comprobante PDF ampliado' : 'Vista previa del comprobante PDF'}>
            <header className="pdf-document-title"><span title={file.name}>{file.name}</span>
                {tool(Download, 'Descargar PDF', () => {
                    const url = URL.createObjectURL(file), link = document.createElement('a');
                    link.href = url; link.download = file.name; link.click();
                    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
                })}
                {tool(expanded ? Minimize2 : Maximize2, expanded ? 'Reducir visor' : 'Ampliar visor', () => setExpanded((old) => !old), false, { ref: expandButton, 'data-pdf-expand': '' })}
            </header>
            <div className="pdf-document-toolbar" role="toolbar" aria-label="Controles del PDF">
                <div className="pdf-page-controls">
                    {tool(ChevronLeft, 'P\u00e1gina anterior', () => setPageNumber((old) => old - 1), !pdf || pageNumber <= 1)}
                    <input type="number" aria-label={'P\u00e1gina del PDF'} min="1" max={pdf?.numPages || 1}
                        value={pageNumber} disabled={!pdf} onChange={(event) => {
                            const number = Number(event.target.value);
                            if (Number.isInteger(number) && number >= 1 && number <= pdf.numPages) setPageNumber(number);
                        }} />
                    <span>/ {pdf?.numPages || '\u2014'}</span>
                    {tool(ChevronRight, 'P\u00e1gina siguiente', () => setPageNumber((old) => old + 1), !pdf || pageNumber >= pdf.numPages)}
                </div>
                <div className="pdf-zoom-controls">
                    {tool(ZoomOut, 'Alejar PDF', () => setZoom(Math.max(.01, scale / 1.25)), !page || scale <= .01)}
                    <output aria-label="Zoom del PDF">{Math.round(scale * 100)}%</output>
                    {tool(ZoomIn, 'Acercar PDF', () => setZoom(Math.min(4, scale * 1.25)), !page || scale >= 4)}
                    {tool(ArrowLeftRight, 'Ajustar al ancho', () => setZoom('width'), !page)}
                    {tool(Scan, 'Mostrar p\u00e1gina completa', () => setZoom('page'), !page)}
                </div>
            </div>
            {documentState.nativeUrl ? <iframe src={documentState.nativeUrl} title="Comprobante PDF original" className="pdf-native-fallback" /> : (
                <div ref={scroller} className="pdf-document-scroll" tabIndex="0" aria-label="Documento PDF">
                    {!pdf && <div className="pdf-document-status" role="status">Cargando PDF...</div>}
                    {renderState === 'error' && <div className="pdf-document-status" role="status">{'No se pudo mostrar esta p\u00e1gina.'}</div>}
                    {viewport && <div className="pdf-sheet-track"><div className="pdf-document-sheet"
                        style={{ width: viewport.width, height: viewport.height }} aria-busy={!ready}>
                        <canvas ref={canvas} aria-label={`P\u00e1gina ${pageNumber} del comprobante`} />
                        {ready && regions.filter((item) => item.page === pageNumber).map((item, index) => (
                            <span key={`${item.field}-${index}`} data-pdf-highlight={item.field}
                                className={`pdf-field-highlight${activeField === item.field ? ' is-active' : ''}`}
                                title={PDF_FIELD_LABELS[item.field]} aria-label={`${PDF_FIELD_LABELS[item.field]} detectado`}
                                style={{ left: `${item.left * 100}%`, top: `${item.top * 100}%`, width: `${item.width * 100}%`, height: `${item.height * 100}%` }} />
                        ))}
                    </div></div>}
                </div>
            )}
        </section>
    );
    return expanded ? createPortal(<><div className="pdf-document-backdrop" onClick={() => setExpanded(false)} />{viewer}</>, document.body) : viewer;
}

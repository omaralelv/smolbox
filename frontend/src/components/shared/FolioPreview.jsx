import { useRef, useState } from 'react';
import './FolioPreview.css';

export default function FolioPreview({ preview }) {
    const dialog = useRef(null);
    const [failedSource, setFailedSource] = useState(null);
    const source = preview?.image_data_url;
    if (failedSource === source || typeof source !== 'string' || source.length > 270000
        || !source.startsWith('data:image/png;base64,')) return null;

    return (
        <div className="folio-preview">
            <button type="button" className="folio-preview-thumbnail"
                aria-label="Ampliar folio detectado" title="Ampliar folio detectado"
                onClick={() => dialog.current?.showModal()}>
                <img src={source} alt="Folio fiscal en el comprobante" onError={() => setFailedSource(source)} />
                <img className="folio-preview-expand" src="/Expand.png" alt="" aria-hidden="true" />
            </button>
            <dialog ref={dialog} className="folio-preview-modal" aria-label="Folio fiscal ampliado"
                onClick={(event) => { if (event.target === dialog.current) dialog.current.close(); }}>
                <header>
                    <h3>Folio fiscal <small>{'P\u00e1gina'} {preview.page}</small></h3>
                    <button type="button" aria-label="Cerrar folio ampliado" title="Cerrar"
                        onClick={() => dialog.current.close()}>&times;</button>
                </header>
                <img src={source} alt="Detalle del folio fiscal en el comprobante" />
            </dialog>
        </div>
    );
}

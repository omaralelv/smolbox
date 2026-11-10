import { useEffect, useRef, useState } from 'react';

import './ExpenseConfirmationDialog.css';

function ExpenseConfirmationDialog({ expense, formattedDate, busy, returnFocusRef, onCancel, onConfirm }) {
    const dialogRef = useRef(null);
    const [reviewed, setReviewed] = useState(false);
    const isInvoice = expense.tipoDocumento === 'factura';
    const documentLabel = isInvoice ? 'de la Factura' : expense.tipoDocumento === 'vale' ? 'del Vale' : 'del Recibo';
    const amount = new Intl.NumberFormat('es-MX', {
        style: 'currency', currency: 'MXN', minimumFractionDigits: 2,
    }).format(expense.monto);

    useEffect(() => {
        const dialog = dialogRef.current;
        const previousFocus = returnFocusRef.current || document.activeElement;
        dialog.showModal();
        return () => {
            dialog.close();
            previousFocus?.focus();
        };
    }, [returnFocusRef]);

    const handleKeyDown = (event) => {
        if (event.key !== 'Tab') return;
        const dialog = event.currentTarget;
        const controls = [...dialog.querySelectorAll('input:not(:disabled), button:not(:disabled)')];
        const first = controls[0];
        const last = controls.at(-1);
        if (!first) {
            event.preventDefault();
            dialog.focus();
        } else if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    };

    return (
        <dialog
            ref={dialogRef}
            className="expense-confirmation"
            aria-labelledby="expense-confirmation-title"
            aria-describedby="expense-confirmation-description"
            aria-busy={busy}
            tabIndex={-1}
            onKeyDown={handleKeyDown}
            onCancel={(event) => {
                event.preventDefault();
                if (!busy) onCancel();
            }}
        >
            <h2 id="expense-confirmation-title">RESUMEN DEL GASTO</h2>

            <dl className="expense-confirmation__summary">
                <div>
                    <dt>Fecha {documentLabel}:</dt>
                    <dd><mark>{formattedDate}</mark></dd>
                </div>
                <div>
                    <dt>Monto {documentLabel}:</dt>
                    <dd><mark>{amount}</mark></dd>
                </div>
                <div>
                    <dt>Folio Fiscal:</dt>
                    <dd><mark>{isInvoice ? expense.folio : 'No aplica'}</mark></dd>
                </div>
            </dl>

            <p id="expense-confirmation-description">
                Por favor verifica que los datos registrados corresponden al comprobante adjunto.
                En caso de no ser correctos, presiona <strong>Cancelar y Editar</strong> para ajustar
                los datos correspondientes.
            </p>

            <label className="expense-confirmation__check">
                <input
                    type="checkbox"
                    checked={reviewed}
                    disabled={busy}
                    onChange={(event) => setReviewed(event.target.checked)}
                    data-audit-label="Verificar los datos del resumen del gasto"
                />
                <span>
                    He validado que <strong>{isInvoice ? 'el monto, fecha y folio' : 'el monto y la fecha'}</strong> ingresados son correctos.
                </span>
            </label>

            <div className="expense-confirmation__actions">
                <button type="button" onClick={onCancel} disabled={busy}>
                    Cancelar y Editar
                </button>
                <button
                    type="button"
                    className="expense-confirmation__confirm"
                    disabled={!reviewed || busy}
                    onClick={() => { if (reviewed && !busy) onConfirm(); }}
                    data-audit-label={'Confirmar y A\u00f1adir'}
                >
                    {busy ? 'Guardando...' : 'Confirmar y A\u00f1adir'}
                </button>
            </div>
        </dialog>
    );
}

export default ExpenseConfirmationDialog;

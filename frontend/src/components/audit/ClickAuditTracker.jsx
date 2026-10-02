import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

import { currentToken, recordFrontendClick } from '../../lib/api';

const CLICKABLE_SELECTOR = [
    'button',
    'a[href]',
    '[role="button"]',
    'input[type="button"]',
    'input[type="submit"]',
    'input[type="file"]',
    'input[type="checkbox"]',
    'input[type="radio"]',
    'select',
    '[data-audit-label]',
    '[data-audit-action]',
].join(',');

function ClickAuditTracker() {
    const location = useLocation();
    const pathRef = useRef(currentPath(location));

    useEffect(() => {
        pathRef.current = currentPath(location);
    }, [location]);

    useEffect(() => {
        const handleClick = (event) => {
            if (!currentToken()) return;

            const target = event.target instanceof Element ? event.target : null;
            if (!target) return;

            const clickable = target.closest(CLICKABLE_SELECTOR);
            if (!clickable || clickable.closest('[data-audit-ignore="true"]')) return;

            const auditContext = clickable.closest('[data-audit-request-id]');
            const requestId = auditContext?.getAttribute('data-audit-request-id');
            if (!requestId) return;

            const buttonLabel = readableClickLabel(clickable);
            if (!buttonLabel) return;

            const expenseContext = clickable.closest('[data-audit-expense-id]');
            const actionKey = clickable.getAttribute('data-audit-action');

            recordFrontendClick(requestId, {
                buttonLabel,
                pagePath: pathRef.current,
                elementType: clickable.tagName.toLowerCase(),
                actionKey: actionKey || null,
                expenseId: expenseContext?.getAttribute('data-audit-expense-id') || null,
            }).catch(() => {});
        };

        document.addEventListener('click', handleClick, true);
        return () => document.removeEventListener('click', handleClick, true);
    }, []);

    return null;
}

function currentPath(location) {
    return `${location.pathname}${location.search || ''}`;
}

function readableClickLabel(element) {
    const label = [
        element.getAttribute('data-audit-label'),
        element.getAttribute('aria-label'),
        element.getAttribute('title'),
        inputLabel(element),
        element.textContent,
        element.querySelector?.('img')?.getAttribute('alt'),
    ]
        .find((value) => String(value || '').trim());

    return String(label || '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 160);
}

function inputLabel(element) {
    if (!(element instanceof HTMLInputElement)) return '';
    return element.value || element.name || element.type;
}

export default ClickAuditTracker;

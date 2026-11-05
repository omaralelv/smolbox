import assert from 'node:assert/strict';
import { test } from 'node:test';
import { categoryRequiresManualAuthorizationArea } from '../src/lib/expenseAuthorization.js';

test('taxis and non-deductible categories require selecting an authorization area', () => {
    for (const category of ['Pasajes y Taxis', 'Taxi', 'Taxis', 'No Deducibles', 'No Deducible', ' no deducible ']) {
        assert.equal(categoryRequiresManualAuthorizationArea(category), true, category);
    }
});

test('other categories keep their existing automatic authorization rules', () => {
    for (const category of [null, '', 'Papelería', 'Agua', 'Insumos', 'Servicio de Agua', 'Trasportación']) {
        assert.equal(categoryRequiresManualAuthorizationArea(category), false, category);
    }
});

# Datos de prueba Smolbox

Estos archivos son datos ficticios para probar Etapa 2 en local. No contienen datos reales
de empresa, SAT, bancos ni proveedores.

## Archivos incluidos

- `scenarios/hud-approval-flow.json`: escenario balanceado para recorrer todo el flujo normal.
- `scenarios/hud-reject-product-flow.json`: escenario para probar que autorizacion rechaza
  solo un producto/gasto y la solicitud sigue.
- `scenarios/hud-validation-errors.json`: escenario con errores intencionales para ver bloqueos.
- `csv/expenses-valid.csv`: gastos validos para importacion masiva.
- `csv/expenses-authorization.csv`: gastos importados con algunos que requieren autorizacion.
- `csv/expenses-invalid.csv`: archivo con errores para probar `dry_run=true`.
- `cfdi/factura_ejemplo_6.xml`: CFDI ficticio valido para un gasto de `1250.00 MXN`.
- `cfdi/factura_v3_1.xml`: CFDI ficticio que puedes usar contra otro monto para probar alertas.
- `receipts/receipt-demo.pdf`: PDF minimo para probar subida de comprobante.

## Forma facil: probar con el HUD

1. Levanta la app:

   ```bash
   docker compose up --build
   ```

2. Abre:

   ```text
   http://localhost:8000/docs
   ```

3. Busca:

   ```text
   POST /api/v1/dev-hud/seed-demo
   ```

4. Copia el contenido de uno de los archivos JSON de `scenarios/` en el cuerpo de la peticion.

5. Abre:

   ```text
   http://localhost:8000/test-hud
   ```

6. Usa `Crear escenario` para una sola solicitud o `Crear demo masivo` para crear varias
   solicitudes en diferentes estados.

7. Recorre los botones del flujo.

Con `Crear demo masivo`, el HUD genera datos ficticios para revisar bandejas de tienda,
autorizacion, contabilidad, gerente, tesoreria y direccion. Sirve para probar multiples
solicitudes sin usar datos reales. Tambien incluye un caso `rejected` donde todos los gastos
fueron rechazados y la solicitud queda sin monto reembolsable.

Para probar rechazo de producto, usa `hud-reject-product-flow.json` y luego:

```text
Enviar tienda
Revision autorizacion
Rechazar producto
Autorizar solicitud
```

El gasto rechazado debe quedar como `Rechazado`, el total activo debe bajar y la solicitud
debe poder avanzar.

## Importar CSV

Para importar un CSV:

1. Crea un escenario HUD.
2. En `GET /api/v1/dev-hud/status`, copia `scenario.request_id`.
3. En Swagger usa:

   ```text
   POST /api/v1/reimbursement-requests/{request_id}/expenses/import
   ```

4. Sube uno de estos archivos:

   ```text
   docs/test-data/csv/expenses-valid.csv
   docs/test-data/csv/expenses-authorization.csv
   docs/test-data/csv/expenses-invalid.csv
   ```

Primero prueba con `dry_run=true`. Eso valida el archivo sin guardarlo.

## Probar CFDI

Para validar un XML CFDI:

1. Crea un gasto con monto `1250.00`, moneda `MXN` y fecha dentro de agosto 2026.
2. Sube `receipts/receipt-demo.pdf` como comprobante del gasto.
3. Usa:

   ```text
   POST /api/v1/expenses/{expense_id}/cfdi/validate
   ```

4. Sube:

   ```text
   docs/test-data/cfdi/factura_ejemplo_6.xml
   ```

Para probar error de monto, sube:

```text
docs/test-data/cfdi/factura_v3_1.xml
```

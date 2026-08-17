# Generador de Pólizas SAP y Reembolsos (Backend API)

Esta es una API construida con **FastAPI** que automatiza la creación de pólizas contables para SAP y solicitudes de reembolso en formato Excel.

El sistema recibe un payload JSON con los gastos de una tienda, procesa las matemáticas financieras (usando `Decimal` para evitar errores binarios) y devuelve un archivo `.zip` que contiene dos archivos Excel formateados listos para descarga.

## 🚀 Requisitos Previos

- Python 3.10 o superior.
- Los siguientes archivos Excel (Bases de datos y plantillas) deben estar en el mismo directorio raíz que `main.py`:
  - `Copia de BASE DE TIENDAS.xlsx`
  - `TiposGastos.xlsx`
  - `COPIA FORMATO REEMBOLSO.xlsx`
  - `logoV.png` (Logo para el formato de reembolso)

## 🛠️ Instalación y Ejecución Local

1. **Crear y activar un entorno virtual:**
   ```bash
   python -m venv .venv
   # En Windows:
   .venv\Scripts\activate
   ```

2. **Instalar dependencias:**
   ```bash
   pip install fastapi uvicorn pandas openpyxl pillow
   ```

3. **Levantar el servidor de desarrollo:**
   ```bash
   uvicorn main:app --reload
   ```

4. **Probar la API:**
   Abre tu navegador y ve a `http://localhost:8000/docs` para ver la documentación interactiva de Swagger UI.

## 📦 Estructura del JSON (Payload Esperado)

El endpoint `POST /generar-polizas/` espera recibir la información con la siguiente estructura estricta.

**Consideraciones importantes:**
- Todas las fechas deben ir en formato `YYYY-MM-DD`.
- Los montos e IVA deben ser números (sin comas ni símbolos de peso).
- El `numero_tienda` debe existir exactamente igual en `Copia de BASE DE TIENDAS.xlsx`.
- Las `cuenta` de cada gasto deben existir exactamente igual en `TiposGastos.xlsx`.

### Ejemplo de Payload válido:

```json
{
  "numero_tienda": "V101",
  "fecha_poliza": "2026-08-17",
  "inicio_caja": "2026-08-01",
  "fin_caja": "2026-08-15",
  "inicio_ant": "2026-07-15",
  "fin_ant": "2026-07-31",
  "cantidad_reembolsada": 1500.50,
  "gastos": [
    {
      "uidd": "A1B2C3D4",
      "cuenta": "601001",
      "monto_base": 1160.00,
      "porcentaje_iva": 16.0
    },
    {
      "uidd": "E5F6G7H8",
      "cuenta": "601002",
      "monto_base": 580.00,
      "porcentaje_iva": 16.0
    }
  ]
}
```

## 📄 Archivos Generados

Al procesar la solicitud exitosamente, la API retorna un archivo `Polizas_{numero_tienda}.zip` que contiene:

1. **`{numero_tienda} CAJA CHICA.xlsx`:** Layout detallado para carga directa en SAP. Conserva los UUID y desglosa los gastos uno por uno.
2. **`{numero_tienda} Poliza Reembolso.xlsx`:** Plantilla visual de la empresa. Consolida (suma) los gastos de la misma cuenta contable en una sola fila e indica cuántas facturas ampara dicho renglón.

## ⚠️ Códigos de Error Comunes
- `404 Not Found`: El número de tienda enviado no está dado de alta en la base de datos local.
- `400 Bad Request`: Una o más cuentas contables enviadas no existen en el catálogo `TiposGastos.xlsx`.
- `400 Bad Request`: Fechas ilógicas (la fecha final es anterior a la inicial).
- `422 Unprocessable Entity`: Error nativo de Pydantic. El JSON viene mal formado (fechas inválidas, strings donde deberían ir números, etc.).

# Despliegue en VM Windows con IIS

Esta guia deja el front en IIS y el backend en el puerto `8000`.

Ejemplo de URLs finales:

- Front: `http://IP_DE_LA_VM`
- Backend: `http://IP_DE_LA_VM:8000`

## 1. Actualizar el codigo

En la VM:

```powershell
git pull
```

## 2. Backend

Crea o edita el archivo `.env` en la raiz del proyecto:

```env
APP_NAME=Smolbox
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://USUARIO:PASSWORD@HOST:5432/NOMBRE_DB
UPLOAD_DIR=C:\smolbox\uploads
MAX_UPLOAD_BYTES=10485760
AUTO_CREATE_SCHEMA=false
AUTH_TOKEN_SECRET=CAMBIA_ESTA_CLAVE_LARGA
AUTH_TOKEN_TTL_MINUTES=480
CORS_ALLOWED_ORIGINS=["http://IP_DE_LA_VM"]

TEXTRACT_ENABLED=false
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=

IMPORT_INITIAL_CATALOG=false
IMPORT_OPENING_CUTOFFS=false
IMPORT_SPENDING_BASELINES=false
```

Si vas a usar Textract, cambia `TEXTRACT_ENABLED=true` y llena las claves de AWS.

Para levantar el backend:

```powershell
python -m pip install .
alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Prueba en la misma VM:

```powershell
curl http://localhost:8000/api/v1/health
```

## 3. Front

Copia la plantilla:

```powershell
copy frontend\.env.production.example frontend\.env.production
```

Edita `frontend\.env.production`:

```env
VITE_API_BASE_URL=http://IP_DE_LA_VM:8000/api/v1
```

Compila:

```powershell
cd frontend
npm install
npm run build
cd ..
```

La carpeta a publicar en IIS es:

```text
frontend\dist
```

El archivo `web.config` se copia automaticamente al `dist` durante el build.

## 4. IIS

Instala o activa:

- IIS
- Static Content
- IIS URL Rewrite

En IIS Manager:

1. Crea un sitio nuevo.
2. Physical path: `RUTA_DEL_PROYECTO\frontend\dist`
3. Binding:
   - Type: `http`
   - IP Address: `All Unassigned` o la IP de la VM
   - Port: `80`

## 5. Firewall

Abre estos puertos en Windows Firewall:

```text
80
8000
```

Si la VM esta en AWS, VMware, Azure u otro proveedor, tambien abre esos puertos en la regla de red externa.

## 6. Probar desde otra computadora

Abre:

```text
http://IP_DE_LA_VM
```

Debe cargar el login. Si el login abre pero no entra, revisa:

- Que el backend este corriendo en `0.0.0.0:8000`.
- Que `VITE_API_BASE_URL` tenga la IP correcta.
- Que `CORS_ALLOWED_ORIGINS` tenga `http://IP_DE_LA_VM`.
- Que los puertos `80` y `8000` esten abiertos.

## 7. Cargas iniciales opcionales

Si necesitas cargar tiendas/usuarios:

```env
IMPORT_INITIAL_CATALOG=true
INITIAL_CATALOG_PASSWORD=TU_PASSWORD_TEMPORAL
```

Si necesitas cargar cortes iniciales e historico:

```env
IMPORT_OPENING_CUTOFFS=true
OPENING_CUTOFFS_STARTS_ON=2026-07-01
OPENING_CUTOFFS_ENDS_ON=2026-07-31
OPENING_CUTOFFS_AMOUNT=0.00
OPENING_CUTOFFS_UPDATE_EXISTING=false
IMPORT_SPENDING_BASELINES=true
```

Despues de que corran bien, regresa esas variables a `false`.

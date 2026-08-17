from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import create_database_schema
from app.dev_hud.page import TEST_HUD_HTML
from app.dev_hud.product_page import PRODUCT_VIEW_HTML

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    if settings.auto_create_schema:
        create_database_schema()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Smolbox Etapa 2 backend API.",
    lifespan=lifespan,
)

if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
        "test_hud": "/test-hud",
        "product_view": "/product-view",
    }


@app.get("/test-hud", response_class=HTMLResponse, include_in_schema=False)
def test_hud() -> HTMLResponse:
    if settings.environment.lower() == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return HTMLResponse(TEST_HUD_HTML)


@app.get("/product-view", response_class=HTMLResponse, include_in_schema=False)
def product_view() -> HTMLResponse:
    if settings.environment.lower() == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return HTMLResponse(PRODUCT_VIEW_HTML)

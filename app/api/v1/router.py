from fastapi import APIRouter

from app.api.v1.endpoints import attachments, cfdi, expenses, health, periods


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(periods.router, prefix="/periods", tags=["periods"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(attachments.router, prefix="/expenses", tags=["attachments"])
api_router.include_router(cfdi.router, tags=["cfdi"])

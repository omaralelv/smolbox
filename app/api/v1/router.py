from fastapi import APIRouter

from app.api.v1.endpoints import (
    attachment_files,
    attachments,
    auth,
    business_rules,
    cfdi,
    dev_hud,
    expenses,
    frontend,
    health,
    periods,
    reimbursement_requests,
    stores,
    users,
    work_queue,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(stores.router, prefix="/stores", tags=["stores"])
api_router.include_router(business_rules.router, prefix="/business-rules", tags=["business-rules"])
api_router.include_router(work_queue.router, prefix="/work-queue", tags=["work-queue"])
api_router.include_router(periods.router, prefix="/periods", tags=["periods"])
api_router.include_router(
    reimbursement_requests.router,
    prefix="/reimbursement-requests",
    tags=["reimbursement-requests"],
)
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(attachments.router, prefix="/expenses", tags=["attachments"])
api_router.include_router(attachment_files.router, prefix="/attachments", tags=["attachments"])
api_router.include_router(cfdi.router, tags=["cfdi"])
api_router.include_router(dev_hud.router, prefix="/dev-hud", tags=["dev-hud"])
api_router.include_router(frontend.router, prefix="/frontend", tags=["frontend"])

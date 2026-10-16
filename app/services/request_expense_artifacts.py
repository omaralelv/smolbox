from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.reimbursement_request import ReimbursementRequest
from app.services.storage import StorageService

if TYPE_CHECKING:
    from app.models.user import User

_PENDING_FILE_DELETIONS = "request_expense_artifact_file_deletions"


@event.listens_for(Session, "after_commit")
def _delete_invalidated_files_after_commit(db: Session) -> None:
    pending = db.info.pop(_PENDING_FILE_DELETIONS, [])
    for settings, storage_paths in pending:
        storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
        for storage_path in storage_paths:
            storage.delete(storage_path)


@event.listens_for(Session, "after_rollback")
def _discard_invalidated_file_deletions_after_rollback(db: Session) -> None:
    db.info.pop(_PENDING_FILE_DELETIONS, None)


def policy_is_current(request: ReimbursementRequest) -> bool:
    return request.policy_downloaded_revision == request.expense_content_revision


def reimbursement_is_current(request: ReimbursementRequest) -> bool:
    return request.reimbursement_excel_revision == request.expense_content_revision


def current_reimbursement_excel_attachment(
    db: Session,
    request: ReimbursementRequest,
) -> Attachment | None:
    if not reimbursement_is_current(request):
        return None
    attachments = _reimbursement_excel_attachments(db, request.id)
    return max(attachments, key=lambda item: item.uploaded_at, default=None)


def invalidate_request_expense_artifacts(
    db: Session,
    request: ReimbursementRequest,
    settings: Settings,
    *,
    actor: User | None = None,
    reason: str,
) -> None:
    old_revision = request.expense_content_revision
    had_current_artifacts = (
        policy_is_current(request) or reimbursement_is_current(request)
    )
    request.expense_content_revision = old_revision + 1
    request.artifacts_refresh_required = (
        request.artifacts_refresh_required or had_current_artifacts
    )
    request.policy_downloaded_revision = None
    request.reimbursement_excel_revision = None

    stale_attachments = _reimbursement_excel_attachments(db, request.id)
    for attachment in stale_attachments:
        db.delete(attachment)
    if stale_attachments:
        db.info.setdefault(_PENDING_FILE_DELETIONS, []).append(
            (settings, [attachment.storage_path for attachment in stale_attachments])
        )

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=actor.id if actor else None,
            actor_type=AuditActorType.user if actor else AuditActorType.system,
            action="request_expense_artifacts_invalidated",
            message=reason,
            event_payload={
                "previous_revision": old_revision,
                "current_revision": old_revision + 1,
                "refresh_required": request.artifacts_refresh_required,
                "deleted_reimbursement_attachment_ids": [
                    str(attachment.id) for attachment in stale_attachments
                ],
            },
        )
    )


def _reimbursement_excel_attachments(
    db: Session,
    request_id: UUID,
) -> list[Attachment]:
    upload_events = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.reimbursement_request_id == request_id,
                AuditLog.action == "reimbursement_excel_uploaded",
            )
            .order_by(AuditLog.created_at.desc())
        )
    )
    if not upload_events:
        return []

    attachments = list(
        db.scalars(
            select(Attachment).where(
                Attachment.reimbursement_request_id == request_id,
                Attachment.attachment_type == AttachmentType.cash_box_format,
            )
        )
    )
    unmatched = {attachment.id: attachment for attachment in attachments}
    matches: list[Attachment] = []

    for audit_event in upload_events:
        payload = audit_event.event_payload or {}
        attachment_id = payload.get("attachment_id")
        attachment = None
        if attachment_id:
            try:
                attachment = unmatched.get(UUID(str(attachment_id)))
            except ValueError:
                attachment = None
        if attachment is None:
            filename = payload.get("filename")
            candidates = [
                item for item in unmatched.values()
                if filename and item.filename == filename
            ]
            if candidates:
                attachment = min(
                    candidates,
                    key=lambda item: abs(
                        _timestamp_distance(item.uploaded_at, audit_event.created_at)
                    ),
                )
        if attachment is not None:
            matches.append(attachment)
            unmatched.pop(attachment.id, None)

    return matches


def _timestamp_distance(first: datetime, second: datetime) -> float:
    first_value = first.timestamp()
    second_value = second.timestamp()
    return abs(first_value - second_value)

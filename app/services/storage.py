import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile


class UploadTooLarge(ValueError):
    pass


class EmptyUpload(ValueError):
    pass


@dataclass(frozen=True)
class StoredAttachment:
    filename: str
    storage_path: str
    size_bytes: int
    checksum_sha256: str


class StorageService:
    def __init__(self, upload_dir: Path, max_bytes: int) -> None:
        self.upload_dir = upload_dir
        self.max_bytes = max_bytes

    async def save_upload(
        self,
        upload: UploadFile,
        *,
        expense_id: UUID | None = None,
        reimbursement_request_id: UUID | None = None,
    ) -> StoredAttachment:
        content = await read_upload_limited(upload, self.max_bytes)
        return self.save_bytes(
            content,
            filename=upload.filename or "upload",
            expense_id=expense_id,
            reimbursement_request_id=reimbursement_request_id,
        )

    def save_bytes(
        self,
        content: bytes,
        *,
        filename: str,
        expense_id: UUID | None = None,
        reimbursement_request_id: UUID | None = None,
    ) -> StoredAttachment:
        owner_id = expense_id or reimbursement_request_id
        if owner_id is None:
            raise ValueError("expense_id or reimbursement_request_id is required")
        if not content:
            raise EmptyUpload("Upload file is empty")
        if len(content) > self.max_bytes:
            raise UploadTooLarge(f"Upload exceeds {self.max_bytes} bytes")

        safe_filename = _sanitize_filename(filename)
        stored_filename = f"{uuid4().hex}_{safe_filename}"
        target_dir = self.upload_dir / str(owner_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / stored_filename

        try:
            with target_path.open("xb") as destination:
                destination.write(content)
        except Exception:
            target_path.unlink(missing_ok=True)
            raise

        return StoredAttachment(
            filename=safe_filename,
            storage_path=str(target_path.relative_to(self.upload_dir)),
            size_bytes=len(content),
            checksum_sha256=sha256(content).hexdigest(),
        )

    def delete(self, storage_path: str) -> None:
        root = self.upload_dir.resolve()
        target = (root / storage_path).resolve()
        if target == root or root not in target.parents:
            raise ValueError("Storage path escapes the configured upload directory")

        target.unlink(missing_ok=True)
        if target.parent != root:
            try:
                target.parent.rmdir()
            except OSError:
                pass


async def read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    content = bytearray()
    while chunk := await upload.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise UploadTooLarge(f"Upload exceeds {max_bytes} bytes")

    if not content:
        raise EmptyUpload("Upload file is empty")
    return bytes(content)


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return (sanitized or "upload")[:160]

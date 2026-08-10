from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
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
        owner_id = expense_id or reimbursement_request_id
        if owner_id is None:
            raise ValueError("expense_id or reimbursement_request_id is required")

        safe_filename = _sanitize_filename(upload.filename or "upload")
        stored_filename = f"{uuid4().hex}_{safe_filename}"
        target_dir = self.upload_dir / str(owner_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / stored_filename

        checksum = sha256()
        total = 0

        try:
            with target_path.open("xb") as destination:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise UploadTooLarge(f"Upload exceeds {self.max_bytes} bytes")
                    checksum.update(chunk)
                    destination.write(chunk)
        except Exception:
            target_path.unlink(missing_ok=True)
            raise

        if total == 0:
            target_path.unlink(missing_ok=True)
            raise EmptyUpload("Upload file is empty")

        return StoredAttachment(
            filename=safe_filename,
            storage_path=str(target_path.relative_to(self.upload_dir)),
            size_bytes=total,
            checksum_sha256=checksum.hexdigest(),
        )


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return (sanitized or "upload")[:160]

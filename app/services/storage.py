import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError


@dataclass
class StoredFile:
    storage_key: str
    file_path: Path
    checksum: str
    size_bytes: int


class LocalStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, upload: UploadFile) -> StoredFile:
        extension = Path(upload.filename or "").suffix.lower()
        storage_key = f"{uuid.uuid4()}{extension}"
        destination = self.settings.upload_dir / storage_key

        hasher = hashlib.sha256()
        size_bytes = 0
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024

        upload.file.seek(0)
        with destination.open("wb") as target:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    destination.unlink(missing_ok=True)
                    raise ValidationAppError(
                        "Uploaded file exceeds configured size limit.",
                        details={"max_upload_size_mb": self.settings.max_upload_size_mb},
                    )
                hasher.update(chunk)
                target.write(chunk)

        upload.file.seek(0)
        return StoredFile(
            storage_key=storage_key,
            file_path=destination,
            checksum=hasher.hexdigest(),
            size_bytes=size_bytes,
        )

    def delete_upload(self, storage_key: str) -> None:
        target = self.settings.upload_dir / storage_key
        target.unlink(missing_ok=True)

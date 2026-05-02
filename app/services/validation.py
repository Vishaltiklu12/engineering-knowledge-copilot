from io import SEEK_END, SEEK_SET
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_allowed_upload_extensions, get_allowed_upload_mime_types, get_settings
from app.core.exceptions import ValidationAppError


class DocumentUploadValidator:
    def __init__(
        self,
        allowed_extensions: set[str] | None = None,
        allowed_mime_types: set[str] | None = None,
    ) -> None:
        settings = get_settings()
        self.allowed_extensions = allowed_extensions or get_allowed_upload_extensions(settings)
        self.allowed_mime_types = allowed_mime_types or get_allowed_upload_mime_types(settings)

    def validate(self, upload: UploadFile) -> None:
        filename = (upload.filename or "").strip()
        if not filename:
            raise ValidationAppError("Uploaded file must include a filename.")

        extension = Path(filename).suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationAppError(
                "Unsupported document type.",
                details={
                    "filename": filename,
                    "allowed_extensions": sorted(self.allowed_extensions),
                },
            )

        content_type = (upload.content_type or "").strip().lower()
        if content_type and content_type not in self.allowed_mime_types and content_type != "application/octet-stream":
            raise ValidationAppError(
                "Unsupported document content type.",
                details={
                    "content_type": content_type,
                    "allowed_mime_types": sorted(self.allowed_mime_types),
                },
            )

        file_size = self._measure_size(upload)
        if file_size == 0:
            raise ValidationAppError("Uploaded file is empty.")

    @staticmethod
    def _measure_size(upload: UploadFile) -> int | None:
        try:
            current_position = upload.file.tell()
            upload.file.seek(0, SEEK_END)
            size_bytes = upload.file.tell()
            upload.file.seek(current_position, SEEK_SET)
            return size_bytes
        except (AttributeError, OSError):
            return None

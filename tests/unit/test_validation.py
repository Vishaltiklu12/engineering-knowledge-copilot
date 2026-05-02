from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import ValidationAppError
from app.services.validation import DocumentUploadValidator


def build_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_document_upload_validator_accepts_supported_file() -> None:
    validator = DocumentUploadValidator(
        allowed_extensions={".md", ".txt"},
        allowed_mime_types={"text/plain", "text/markdown"},
    )

    validator.validate(build_upload("runbook.md", b"hello world", "text/markdown"))


def test_document_upload_validator_rejects_unsupported_extension() -> None:
    validator = DocumentUploadValidator(
        allowed_extensions={".md"},
        allowed_mime_types={"text/markdown"},
    )

    with pytest.raises(ValidationAppError):
        validator.validate(build_upload("diagram.png", b"binary", "image/png"))


def test_document_upload_validator_rejects_empty_file() -> None:
    validator = DocumentUploadValidator(
        allowed_extensions={".txt"},
        allowed_mime_types={"text/plain"},
    )

    with pytest.raises(ValidationAppError):
        validator.validate(build_upload("empty.txt", b"", "text/plain"))

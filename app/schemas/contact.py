import re

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ErrorBody, MetaBody

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^[0-9+\-().\s]{7,25}$")


class ContactRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    company: str | None = Field(default=None, max_length=120)
    subject: str = Field(min_length=4, max_length=160)
    message: str = Field(min_length=20, max_length=4000)

    @field_validator("name", "subject", "message")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("Field cannot be empty.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Enter a valid phone number.")
        return normalized

    @field_validator("company")
    @classmethod
    def normalize_company(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None

    @model_validator(mode="after")
    def ensure_email_or_phone(self):
        if not self.email and not self.phone:
            raise ValueError("Provide either an email address or a phone number.")
        return self


class ContactResponseData(BaseModel):
    delivery_mode: str
    message: str


class ContactResponse(BaseModel):
    data: ContactResponseData
    meta: MetaBody
    error: ErrorBody | None = None

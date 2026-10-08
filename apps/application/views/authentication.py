from __future__ import annotations

import re

from pydantic import BaseModel, Field, SecretStr, field_validator


class AccountUserView(BaseModel):
    id: str
    email: str
    display_name: str


class AccountSessionView(BaseModel):
    authenticated: bool
    user: AccountUserView | None = None


class LoginAccountInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+", value):
            raise ValueError("valid email address required")
        if any(ord(character) < 32 for character in value):
            raise ValueError("valid email address required")
        return value


class RegisterAccountInput(LoginAccountInput):
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise ValueError("display name required")
        return value

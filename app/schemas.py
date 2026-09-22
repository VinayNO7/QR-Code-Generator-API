from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class Credentials(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=10, max_length=128)]


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class QRCodeRequest(BaseModel):
    url: HttpUrl
    foreground: str = "#000000"
    background: str = "#FFFFFF"
    size: Annotated[int, Field(ge=2, le=30)] = 10
    border: Annotated[int, Field(ge=0, le=10)] = 4
    error_correction: Literal["L", "M", "Q", "H"] = "M"

    @field_validator("foreground", "background")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not HEX_COLOR.fullmatch(value):
            raise ValueError("must be a six-digit hexadecimal color, for example #1A2B3C")
        return value.upper()


class QRCodeItem(BaseModel):
    id: str
    url: str
    foreground: str
    background: str
    size: int
    border: int
    error_correction: str
    created_at: datetime
    download_url: str


class QRCodePage(BaseModel):
    items: list[QRCodeItem]
    total: int

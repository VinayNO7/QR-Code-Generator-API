from __future__ import annotations

import io
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import qrcode
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from .database import Database
from .schemas import Credentials, QRCodeItem, QRCodePage, QRCodeRequest, Token
from .security import create_token, hash_password, verify_password, verify_token
from .settings import Settings, get_settings

settings = get_settings()
database = Database(settings.database_path)
# This makes Swagger UI present an OAuth2 username/password form rather than a
# raw Authorization-header input. The username value is the account email.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
ERROR_LEVELS = {"L": qrcode.constants.ERROR_CORRECT_L, "M": qrcode.constants.ERROR_CORRECT_M, "Q": qrcode.constants.ERROR_CORRECT_Q, "H": qrcode.constants.ERROR_CORRECT_H}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("ENVIRONMENT") == "production" and settings.secret == "development-only-change-me":
        raise RuntimeError("QR_API_SECRET must be set in production")
    database.initialize()
    yield


app = FastAPI(title="QR Code Generator API", version="1.0.0", lifespan=lifespan)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> int:
    user_id = verify_token(token, settings.secret)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    with database.connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user_id


CurrentUser = Annotated[int, Depends(get_current_user)]


def serialize_qr(row, request: Request) -> QRCodeItem:
    return QRCodeItem(
        **{key: row[key] for key in ("id", "url", "foreground", "background", "size", "border", "error_correction", "created_at")},
        download_url=str(request.url_for("download_qr", qr_id=row["id"])),
    )


def render_qr(row) -> bytes:
    code = qrcode.QRCode(error_correction=ERROR_LEVELS[row["error_correction"]], box_size=row["size"], border=row["border"])
    code.add_data(row["url"])
    code.make(fit=True)
    image = code.make_image(fill_color=row["foreground"], back_color=row["background"])
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED, tags=["authentication"])
def register(credentials: Credentials) -> Token:
    try:
        with database.connection() as conn:
            cursor = conn.execute("INSERT INTO users(email, password_hash) VALUES (?, ?)", (str(credentials.email), hash_password(credentials.password)))
            user_id = cursor.lastrowid
    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from error
        raise
    return Token(access_token=create_token(user_id, settings.secret, settings.token_ttl_minutes))


@app.post("/auth/token", response_model=Token, tags=["authentication"])
def issue_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """OAuth2 password grant. Enter the registered email in the `username` field."""
    with database.connection() as conn:
        user = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (form_data.username,)).fetchone()
    if user is None or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return Token(access_token=create_token(user["id"], settings.secret, settings.token_ttl_minutes))


@app.post("/qrcodes", response_model=QRCodeItem, status_code=status.HTTP_201_CREATED, tags=["QR codes"])
def generate_qr(payload: QRCodeRequest, request: Request, user_id: CurrentUser) -> QRCodeItem:
    qr_id = str(uuid.uuid4())
    with database.connection() as conn:
        conn.execute(
            """INSERT INTO qr_codes(id, user_id, url, foreground, background, size, border, error_correction)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (qr_id, user_id, str(payload.url), payload.foreground, payload.background, payload.size, payload.border, payload.error_correction),
        )
        row = conn.execute("SELECT * FROM qr_codes WHERE id = ?", (qr_id,)).fetchone()
    return serialize_qr(row, request)


@app.get("/qrcodes", response_model=QRCodePage, tags=["QR codes"])
def list_qrs(request: Request, user_id: CurrentUser, limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0) -> QRCodePage:
    with database.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM qr_codes WHERE user_id = ?", (user_id,)).fetchone()[0]
        rows = conn.execute("SELECT * FROM qr_codes WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", (user_id, limit, offset)).fetchall()
    return QRCodePage(items=[serialize_qr(row, request) for row in rows], total=total)


def owned_qr(qr_id: str, user_id: int):
    with database.connection() as conn:
        row = conn.execute("SELECT * FROM qr_codes WHERE id = ? AND user_id = ?", (qr_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found")
    return row


@app.get("/qrcodes/{qr_id}/download", name="download_qr", tags=["QR codes"])
def download_qr(qr_id: str, user_id: CurrentUser) -> Response:
    row = owned_qr(qr_id, user_id)
    return Response(
        content=render_qr(row),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="qr-{qr_id}.png"', "Cache-Control": "private, max-age=3600"},
    )


@app.delete("/qrcodes/{qr_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["QR codes"])
def delete_qr(qr_id: str, user_id: CurrentUser) -> Response:
    with database.connection() as conn:
        cursor = conn.execute("DELETE FROM qr_codes WHERE id = ? AND user_id = ?", (qr_id, user_id))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

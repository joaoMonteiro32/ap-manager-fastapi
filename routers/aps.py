import logging
import os
import re
import uuid
from io import BytesIO
from pathlib import Path
from mimetypes import guess_type

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import AP, User
from ..deps import get_current_user, require_admin
from ..services.ocr import extract_mac_from_bytes, normalize_mac

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aps", tags=["aps"])

MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_IMAGE_WIDTH = 6000
MAX_IMAGE_HEIGHT = 6000

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

MAX_QUARTO_LENGTH = 20
QUARTO_PATTERN = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z0-9\-/ ]{1,20}$")


def safe_remove_file(path: Path) -> None:
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        logger.exception("Falha ao remover ficheiro", extra={"path": str(path)})


def validate_quarto(quarto: str) -> str:
    quarto = quarto.strip()

    if not quarto:
        raise HTTPException(status_code=400, detail="Quarto obrigatório.")

    if len(quarto) > MAX_QUARTO_LENGTH:
        raise HTTPException(status_code=400, detail="Quarto demasiado longo.")

    if not QUARTO_PATTERN.fullmatch(quarto):
        raise HTTPException(status_code=400, detail="Quarto inválido.")

    quarto = " ".join(quarto.split())
    quarto = quarto.title()
    return quarto


def validate_image_upload(photo: UploadFile, file_bytes: bytes) -> None:
    if not photo.filename:
        raise HTTPException(status_code=400, detail="Ficheiro sem nome.")

    ext = Path(photo.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato inválido. Usa JPG ou PNG.")

    if photo.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de ficheiro inválido. Usa JPG ou PNG.")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Ficheiro vazio.")

    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Imagem demasiado grande. Máximo permitido: 5 MB."
        )

    try:
        img = Image.open(BytesIO(file_bytes))
        img.verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=400,
            detail="O ficheiro enviado não é uma imagem válida."
        )

    try:
        img = Image.open(BytesIO(file_bytes))
        width, height = img.size
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível ler a imagem.")

    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="Imagem inválida.")

    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise HTTPException(
            status_code=400,
            detail="Imagem demasiado grande em dimensões."
        )


@router.post("/upload")
async def upload_ap(
    quarto: str = Form(...),
    ocr_debug: bool = Form(False),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    quarto = validate_quarto(quarto)

    file_bytes = await photo.read()
    validate_image_upload(photo, file_bytes)

    ext = Path(photo.filename).suffix.lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOADS_DIR / filename

    try:
        mac = extract_mac_from_bytes(file_bytes)

        logger.info(
            "Upload recebido para extração de MAC",
            extra={
                "quarto": quarto,
                "user_id": user.id,
                "original_filename": photo.filename,
                "content_type": photo.content_type,
            },
        )

        if not mac:
            return {
                "success": False,
                "message": "MAC inválido ou não encontrado.",
            }

        mac = normalize_mac(mac)
        if not mac:
            return {
                "success": False,
                "message": "MAC inválido ou não encontrado.",
            }

        existing = db.query(AP).filter(
            or_(AP.mac == mac, AP.quarto == quarto)
        ).first()

        if existing:
            if existing.mac == mac:
                return {
                    "success": False,
                    "message": f"MAC {mac} já registado no quarto {existing.quarto}",
                }

            return {
                "success": False,
                "message": f"Já existe um AP registado no quarto {quarto}",
            }

        with open(filepath, "wb") as f:
            f.write(file_bytes)

        ap = AP(mac=mac, quarto=quarto, foto_path=filename)
        db.add(ap)

        try:
            db.commit()
            db.refresh(ap)
        except IntegrityError:
            db.rollback()
            safe_remove_file(filepath)
            raise HTTPException(
                status_code=400,
                detail="Já existe um AP com esse MAC ou já existe um registo para esse quarto."
            )

        response = {
            "success": True,
            "id": ap.id,
            "mac": ap.mac,
            "quarto": ap.quarto,
            "foto": f"/aps/{ap.id}/foto",
        }

        if ocr_debug:
            response["debug"] = {
                "ocr_debug_enabled": True,
                "stored_filename": filename,
                "normalized_mac": mac,
            }

        logger.info(
            "AP registado com sucesso",
            extra={
                "ap_id": ap.id,
                "quarto": ap.quarto,
                "mac": ap.mac,
                "user_id": user.id,
            },
        )

        return response

    except HTTPException:
        raise
    except Exception:
        safe_remove_file(filepath)
        logger.exception(
            "Erro inesperado ao processar upload de AP",
            extra={
                "quarto": quarto,
                "stored_filename": filename,
                "user_id": user.id,
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar o upload."
        )


@router.get("/{ap_id}/foto")
def get_ap_photo(
    ap_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ap = db.query(AP).filter(AP.id == ap_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="AP não encontrado.")

    if not ap.foto_path:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")

    file_path = UPLOADS_DIR / ap.foto_path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Foto não encontrada.")

    media_type, _ = guess_type(str(file_path))

    return FileResponse(
        path=str(file_path),
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
    )


@router.get("/search")
def search_ap(
    quarto: str | None = None,
    mac: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if not quarto and not mac:
        raise HTTPException(
            status_code=400,
            detail="Indica pelo menos um critério de pesquisa."
        )

    if limit < 1:
        limit = 1
    if limit > 20:
        limit = 20
    if offset < 0:
        offset = 0

    query = db.query(AP)

    if quarto:
        quarto = quarto.strip()
        if quarto:
            query = query.filter(AP.quarto.ilike(f"%{quarto}%"))

    if mac:
        mac_search = mac.strip().upper().replace(":", "").replace("-", "").replace(" ", "")
        if not mac_search:
            raise HTTPException(status_code=400, detail="MAC de pesquisa inválido.")

        formatted_mac_search = "-".join(
            mac_search[i:i+2] for i in range(0, len(mac_search), 2)
        )

        query = query.filter(
            or_(
                AP.mac.ilike(f"%{mac_search}%"),
                AP.mac.ilike(f"%{formatted_mac_search}%")
            )
        )

    query = query.order_by(AP.id.desc())

    rows = query.offset(offset).limit(limit + 1).all()
    has_more = len(rows) > limit
    results = rows[:limit]

    return {
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "results": [
            {
                "id": r.id,
                "quarto": r.quarto,
                "mac": r.mac,
                "foto": f"/aps/{r.id}/foto" if r.foto_path else None,
            }
            for r in results
        ],
    }


@router.delete("/{ap_id}")
def delete_ap(
    ap_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    ap = db.query(AP).filter(AP.id == ap_id).first()

    if not ap:
        raise HTTPException(status_code=404, detail="AP não encontrado.")

    if ap.foto_path:
        foto_path = UPLOADS_DIR / ap.foto_path
        safe_remove_file(foto_path)

    db.delete(ap)
    db.commit()

    logger.info(
        "AP apagado com sucesso",
        extra={
            "ap_id": ap_id,
            "user_id": user.id,
        },
    )

    return {
        "success": True,
        "message": f"AP com ID {ap_id} apagado com sucesso",
    }
import io
import uuid
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from PIL import Image

import auth
import models
import storage
from database import get_db

router = APIRouter(prefix="/api/photos", tags=["photos"])

ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _resolution(img: Image.Image) -> str:
    w, h = img.size
    return f"{w} x {h} px"


# Tags EXIF de data/hora, em ordem de preferência:
# 36867 DateTimeOriginal (instante do disparo)  ← o que queremos
# 36868 DateTimeDigitized
#   306 DateTime (última modificação do arquivo)
_EXIF_IFD = 0x8769
_DATE_TAGS = (36867, 36868)


def _exif_datetime(img: Image.Image) -> Tuple[Optional[str], Optional[str]]:
    """Lê o instante do disparo do EXIF.

    Devolve ("AAAA-MM-DD", "HH:MM") ou (None, None) se a foto não tiver EXIF —
    caso de prints, imagens editadas ou arquivos já processados por outro software.

    IMPORTANTE: precisa ser chamado antes de reprocessar a imagem, porque salvar
    de novo descarta o EXIF (o que, por sinal, também remove as coordenadas de GPS).
    """
    try:
        exif = img.getexif()
        if not exif:
            return None, None

        raw = None
        # DateTimeOriginal vive no sub-IFD de EXIF, não no IFD principal.
        try:
            sub = exif.get_ifd(_EXIF_IFD)
            for tag in _DATE_TAGS:
                if sub.get(tag):
                    raw = sub[tag]
                    break
        except Exception:
            pass
        if not raw:
            raw = exif.get(306)
        if not raw:
            return None, None

        if isinstance(raw, bytes):
            raw = raw.decode("ascii", "ignore")
        dt = datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        return None, None


def _photo_dict(photo: models.Photo, *, include_plate: bool = False, db=None) -> dict:
    d = {
        "id": photo.id,
        "title": photo.title,
        "car": photo.car,
        "brand": photo.brand,
        "model": photo.model,
        "color": photo.color,
        "event": photo.event,
        "location": photo.location,
        "event_date": photo.event_date,
        "event_time": photo.event_time,
        "price": photo.price,
        "description": photo.description,
        "is_public": photo.is_public,
        "is_for_sale": photo.is_for_sale,
        "resolution": photo.resolution,
        "photographer_id": photo.photographer_id,
        "photographer_name": photo.photographer.name if photo.photographer else None,
        "photographer_nickname": photo.photographer.nickname if photo.photographer else None,
        "preview_url": f"/api/photos/{photo.id}/preview",
        "created_at": photo.created_at.isoformat() if photo.created_at else None,
    }
    if db is not None:
        d["like_count"] = db.query(models.Like).filter(models.Like.photo_id == photo.id).count()
        d["comment_count"] = db.query(models.Comment).filter(models.Comment.photo_id == photo.id).count()
        d["save_count"] = db.query(models.Save).filter(models.Save.photo_id == photo.id).count()
    else:
        d["like_count"] = 0
        d["comment_count"] = 0
        d["save_count"] = 0
    if include_plate:
        d["plate"] = photo.plate
    return d


def _to_jpeg_bytes(img: Image.Image, quality: int = 88) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


@router.get("")
def list_photos(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    color: Optional[str] = None,
    location: Optional[str] = None,
    event: Optional[str] = None,
    plate: Optional[str] = None,
    photographer_id: Optional[int] = None,
    event_time: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user_optional),
):
    query = db.query(models.Photo)

    if q:
        for word in q.strip().split():
            like = f"%{word}%"
            query = query.filter(or_(
                models.Photo.title.ilike(like),
                models.Photo.car.ilike(like),
                models.Photo.brand.ilike(like),
                models.Photo.model.ilike(like),
                models.Photo.color.ilike(like),
                models.Photo.location.ilike(like),
            ))

    if brand:
        query = query.filter(models.Photo.brand.ilike(f"%{brand}%"))
    if model:
        query = query.filter(models.Photo.model.ilike(f"%{model}%"))
    if color:
        query = query.filter(models.Photo.color.ilike(f"%{color}%"))
    if location:
        query = query.filter(models.Photo.location.ilike(f"%{location}%"))
    if event:
        query = query.filter(models.Photo.event.ilike(f"%{event}%"))
    if event_time:
        query = query.filter(models.Photo.event_time == event_time)
    if photographer_id:
        query = query.filter(models.Photo.photographer_id == photographer_id)
    if plate:
        query = query.filter(models.Photo.plate.ilike(plate.strip().upper()))

    all_photos = query.order_by(models.Photo.created_at.desc()).all()

    result = []
    for p in all_photos:
        is_owner = current_user and current_user.id == p.photographer_id
        if p.is_public or p.is_for_sale or is_owner:
            result.append(_photo_dict(p, include_plate=bool(is_owner), db=db))

    return result


@router.post("")
async def upload_photo(
    file: UploadFile = File(...),
    title: str = Form(...),
    car: str = Form(default=""),
    brand: str = Form(default=""),
    model_name: str = Form(default=""),
    color: str = Form(default=""),
    plate: str = Form(default=""),
    event: str = Form(default=""),
    location: str = Form(default=""),
    event_date: str = Form(default=""),
    event_time: str = Form(default=""),
    price: Optional[float] = Form(default=None),
    description: str = Form(default=""),
    is_public: bool = Form(default=True),
    is_for_sale: bool = Form(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.account_type != "photographer":
        raise HTTPException(status_code=403, detail="Apenas fotógrafos podem fazer upload de fotos")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use JPEG, PNG ou WebP.")

    raw = await file.read()
    img = Image.open(io.BytesIO(raw))
    resolution = _resolution(img)

    # Lido antes de reprocessar a imagem — o re-save descarta o EXIF.
    exif_date, exif_time = _exif_datetime(img)

    # Upload original
    original_bytes = _to_jpeg_bytes(img, quality=92)
    original_url = storage.upload_photo(original_bytes, ".jpg")

    # Watermark para fotos exclusivamente à venda
    watermarked_url = original_url
    if is_for_sale and not is_public:
        try:
            from utils.watermark import add_watermark_pil
            wm_img = add_watermark_pil(img)
            wm_bytes = _to_jpeg_bytes(wm_img, quality=85)
            watermarked_url = storage.upload_watermarked(wm_bytes, ".jpg")
        except Exception:
            watermarked_url = original_url

    photo = models.Photo(
        photographer_id=current_user.id,
        title=title.strip(),
        car=car.strip() or title.strip(),
        brand=brand.strip(),
        model=model_name.strip(),
        color=color.strip(),
        plate=plate.strip().upper(),
        event=event.strip(),
        location=location.strip(),
        # O que o fotógrafo digitou tem prioridade; o EXIF preenche o que ficou vazio.
        event_date=event_date.strip() or exif_date or "",
        event_time=event_time.strip() or exif_time or None,
        price=price,
        description=description.strip(),
        is_public=is_public,
        is_for_sale=is_for_sale,
        original_path=original_url,
        watermarked_path=watermarked_url,
        resolution=resolution,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return _photo_dict(photo, include_plate=True, db=db)


@router.get("/{photo_id}/preview")
def get_preview(photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    if not photo.is_public and not photo.is_for_sale:
        raise HTTPException(status_code=403, detail="Foto privada")

    # Redireciona para URL pública no Supabase Storage
    url = photo.watermarked_path if (photo.is_for_sale and not photo.is_public and photo.watermarked_path) else photo.original_path
    if not url:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return RedirectResponse(url=url)


@router.get("/{photo_id}/original")
def get_original(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    if photo.photographer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    if not photo.original_path:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return RedirectResponse(url=photo.original_path)


@router.get("/{photo_id}")
def get_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user_optional),
):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")

    is_owner = current_user and current_user.id == photo.photographer_id
    if not photo.is_public and not photo.is_for_sale and not is_owner:
        raise HTTPException(status_code=403, detail="Foto privada")

    return _photo_dict(photo, include_plate=bool(is_owner), db=db)


@router.put("/{photo_id}")
def update_photo(
    photo_id: int,
    title: Optional[str] = Form(default=None),
    car: Optional[str] = Form(default=None),
    brand: Optional[str] = Form(default=None),
    model_name: Optional[str] = Form(default=None),
    color: Optional[str] = Form(default=None),
    plate: Optional[str] = Form(default=None),
    event: Optional[str] = Form(default=None),
    location: Optional[str] = Form(default=None),
    event_time: Optional[str] = Form(default=None),
    price: Optional[float] = Form(default=None),
    description: Optional[str] = Form(default=None),
    is_public: Optional[bool] = Form(default=None),
    is_for_sale: Optional[bool] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    if photo.photographer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    if title is not None:
        photo.title = title.strip()
    if car is not None:
        photo.car = car.strip()
    if brand is not None:
        photo.brand = brand.strip()
    if model_name is not None:
        photo.model = model_name.strip()
    if color is not None:
        photo.color = color.strip()
    if plate is not None:
        photo.plate = plate.strip().upper()
    if event is not None:
        photo.event = event.strip()
    if location is not None:
        photo.location = location.strip()
    if event_time is not None:
        photo.event_time = event_time.strip() or None
    if price is not None:
        photo.price = price
    if description is not None:
        photo.description = description.strip()
    if is_public is not None:
        photo.is_public = is_public
    if is_for_sale is not None:
        photo.is_for_sale = is_for_sale

    db.commit()
    db.refresh(photo)
    return _photo_dict(photo, include_plate=True, db=db)


@router.delete("/{photo_id}")
def delete_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    if photo.photographer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")

    storage.delete_file(storage.BUCKET_PHOTOS, photo.original_path or "")
    if photo.watermarked_path and photo.watermarked_path != photo.original_path:
        storage.delete_file(storage.BUCKET_PHOTOS, photo.watermarked_path)

    db.delete(photo)
    db.commit()
    return {"ok": True}

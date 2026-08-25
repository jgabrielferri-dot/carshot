from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth
import models
from database import get_db

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


# ── Likes ──────────────────────────────────────────────────────────────────

@router.post("/likes/{photo_id}")
def toggle_like(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    existing = db.query(models.Like).filter(
        models.Like.user_id == current_user.id,
        models.Like.photo_id == photo_id,
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        count = db.query(models.Like).filter(models.Like.photo_id == photo_id).count()
        return {"liked": False, "like_count": count}
    like = models.Like(user_id=current_user.id, photo_id=photo_id)
    db.add(like)
    db.commit()
    count = db.query(models.Like).filter(models.Like.photo_id == photo_id).count()
    return {"liked": True, "like_count": count}


@router.get("/likes/mine")
def my_likes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    rows = db.query(models.Like.photo_id).filter(models.Like.user_id == current_user.id).all()
    return [r.photo_id for r in rows]


@router.get("/likes/mine/photos")
def my_liked_photos(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Returns photo dicts for all photos liked by current user."""
    from routes.photo_routes import _photo_dict
    likes = db.query(models.Like).filter(models.Like.user_id == current_user.id).order_by(models.Like.created_at.desc()).all()
    result = []
    for lk in likes:
        photo = db.query(models.Photo).filter(models.Photo.id == lk.photo_id).first()
        # Mesma regra de visibilidade da listagem de fotos: uma foto só à venda
        # continua visível (com marca d'água), então precisa aparecer aqui também.
        if photo and (photo.is_public or photo.is_for_sale):
            result.append(_photo_dict(photo, db=db))
    return result


# ── Saves ──────────────────────────────────────────────────────────────────

@router.post("/saves/{photo_id}")
def toggle_save(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    existing = db.query(models.Save).filter(
        models.Save.user_id == current_user.id,
        models.Save.photo_id == photo_id,
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"saved": False}
    save = models.Save(user_id=current_user.id, photo_id=photo_id)
    db.add(save)
    db.commit()
    return {"saved": True}


@router.get("/saves/mine")
def my_saves(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    rows = db.query(models.Save.photo_id).filter(models.Save.user_id == current_user.id).all()
    return [r.photo_id for r in rows]


@router.get("/saves/mine/photos")
def my_saved_photos(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Returns photo dicts for all photos saved by current user."""
    from routes.photo_routes import _photo_dict
    saves = db.query(models.Save).filter(models.Save.user_id == current_user.id).order_by(models.Save.created_at.desc()).all()
    result = []
    for sv in saves:
        photo = db.query(models.Photo).filter(models.Photo.id == sv.photo_id).first()
        # Idem: fotos só à venda também entram nos salvos.
        if photo and (photo.is_public or photo.is_for_sale):
            result.append(_photo_dict(photo, db=db))
    return result


# ── Comments ───────────────────────────────────────────────────────────────

class CommentRequest(BaseModel):
    text: str


@router.get("/comments/{photo_id}")
def list_comments(photo_id: int, db: Session = Depends(get_db)):
    comments = (
        db.query(models.Comment)
        .filter(models.Comment.photo_id == photo_id)
        .order_by(models.Comment.created_at.asc())
        .all()
    )
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "user_name": (c.user.nickname or c.user.name) if c.user else "Usuário",
            "text": c.text,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ]


@router.post("/comments/{photo_id}")
def add_comment(
    photo_id: int,
    req: CommentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Comentário não pode ser vazio")
    comment = models.Comment(
        user_id=current_user.id,
        photo_id=photo_id,
        text=req.text.strip(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {
        "id": comment.id,
        "user_id": comment.user_id,
        "user_name": current_user.nickname or current_user.name,
        "text": comment.text,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }

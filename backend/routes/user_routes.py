import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

import auth
import models
import storage
from database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_dict(user: models.User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "nickname": user.nickname,
        "account_type": user.account_type,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "phone": user.phone,
        "contact_email": user.contact_email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/search")
def search_users(q: str = "", db: Session = Depends(get_db)):
    if not q or len(q.strip()) < 2:
        users = (
            db.query(models.User)
            .filter(models.User.account_type == "photographer")
            .limit(12)
            .all()
        )
    else:
        term = f"%{q.strip()}%"
        users = (
            db.query(models.User)
            .filter(
                models.User.account_type == "photographer",
                (models.User.name.ilike(term)) | (models.User.nickname.ilike(term)),
            )
            .limit(20)
            .all()
        )
    return [_user_dict(u) for u in users]


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return _user_dict(user)


@router.put("/me/profile")
async def update_profile(
    name: Optional[str] = Form(default=None),
    nickname: Optional[str] = Form(default=None),
    bio: Optional[str] = Form(default=None),
    cpf: Optional[str] = Form(default=None),
    phone: Optional[str] = Form(default=None),
    contact_email: Optional[str] = Form(default=None),
    avatar: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if name:
        current_user.name = name.strip()
    if nickname is not None:
        current_user.nickname = nickname.strip() or None
    if bio is not None:
        current_user.bio = bio.strip()
    if cpf is not None:
        current_user.cpf = cpf.strip() or None
    if phone is not None:
        current_user.phone = phone.strip() or None
    if contact_email is not None:
        current_user.contact_email = contact_email.strip() or None

    if avatar and avatar.filename:
        import os
        ext = os.path.splitext(avatar.filename)[1].lower() or ".jpg"
        raw = await avatar.read()
        avatar_url = storage.upload_avatar(raw, ext)
        current_user.avatar_url = avatar_url

    db.commit()
    db.refresh(current_user)
    return _user_dict(current_user)


@router.put("/me/password")
def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    import bcrypt
    if not bcrypt.checkpw(current_password.encode(), current_user.password_hash.encode()):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 4 caracteres")
    current_user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.commit()
    return {"ok": True}

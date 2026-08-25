from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth
import models
from database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    account_type: str  # "buyer" or "photographer"
    phone: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


def _only_digits(value: str) -> str:
    return "".join(c for c in (value or "") if c.isdigit())


def _user_dict(user: models.User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "nickname": user.nickname,
        "account_type": user.account_type,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "cpf": user.cpf,
        "phone": user.phone,
        "is_admin": auth.is_admin(user),
    }


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if req.account_type not in ("buyer", "photographer"):
        raise HTTPException(status_code=400, detail="Tipo de conta inválido")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Senha deve ter ao menos 6 caracteres")
    if db.query(models.User).filter(models.User.email == req.email.lower()).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    phone = (req.phone or "").strip()
    if len(_only_digits(phone)) < 10:
        raise HTTPException(status_code=400, detail="Informe um celular válido com DDD")

    user = models.User(
        email=req.email.lower().strip(),
        name=req.name.strip(),
        password_hash=auth.hash_password(req.password),
        account_type=req.account_type,
        phone=phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": auth.create_access_token(user.id), "user": _user_dict(user)}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email.lower().strip()).first()
    if not user or not auth.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    return {"access_token": auth.create_access_token(user.id), "user": _user_dict(user)}


@router.get("/me")
def me(current_user: models.User = Depends(auth.get_current_user)):
    return _user_dict(current_user)

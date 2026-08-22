from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import auth
import models
from database import get_db

router = APIRouter(prefix="/api/follow", tags=["follow"])


@router.post("/{user_id}")
def follow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode se seguir")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    existing = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.followed_id == user_id,
    ).first()
    if existing:
        return {"ok": True, "following": True}
    follow = models.Follow(follower_id=current_user.id, followed_id=user_id)
    db.add(follow)
    db.commit()
    return {"ok": True, "following": True}


@router.delete("/{user_id}")
def unfollow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    row = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.followed_id == user_id,
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True, "following": False}


@router.get("/following/details")
def get_following_details(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Returns full user objects for all users the current user follows."""
    rows = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id
    ).all()
    result = []
    for row in rows:
        user = db.query(models.User).filter(models.User.id == row.followed_id).first()
        if user:
            result.append({
                "id": user.id,
                "name": user.name,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "bio": user.bio,
            })
    return result


@router.get("/following")
def get_following(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Returns list of user IDs the current user follows."""
    rows = db.query(models.Follow.followed_id).filter(
        models.Follow.follower_id == current_user.id
    ).all()
    return [r.followed_id for r in rows]


@router.get("/count/{user_id}")
def follower_count(user_id: int, db: Session = Depends(get_db)):
    count = db.query(models.Follow).filter(models.Follow.followed_id == user_id).count()
    return {"followers": count}

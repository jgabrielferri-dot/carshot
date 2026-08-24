import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

import auth
import models
from database import get_db

router = APIRouter(prefix="/api/orders", tags=["orders"])

# Percentual retido pela plataforma em cada venda (0.20 = 20%)
COMMISSION_RATE = float(os.getenv("PLATFORM_COMMISSION", "0.20"))

STATUSES = {"pending", "paid", "cancelled"}


def _order_dict(o: models.Order, *, for_admin: bool = False) -> dict:
    photo = o.photo
    d = {
        "id": o.id,
        "photo_id": o.photo_id,
        "photo_title": photo.title if photo else None,
        "photo_plate": photo.plate if (photo and for_admin) else None,
        "photo_brand": photo.brand if photo else None,
        "photo_model": photo.model if photo else None,
        "photo_location": photo.location if photo else None,
        "photo_resolution": photo.resolution if photo else None,
        "preview_url": f"/api/photos/{o.photo_id}/preview",
        "price": o.price,
        "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "downloaded_at": o.downloaded_at.isoformat() if o.downloaded_at else None,
        "photographer_id": o.photographer_id,
        "photographer_name": o.photographer.name if o.photographer else None,
    }
    if for_admin:
        d.update({
            "commission": o.commission,
            "payout": o.payout,
            "note": o.note,
            "buyer_id": o.buyer_id,
            "buyer_name": o.buyer.name if o.buyer else None,
            "buyer_email": o.buyer.email if o.buyer else None,
            "buyer_phone": o.buyer.phone if o.buyer else None,
            "photographer_email": o.photographer.email if o.photographer else None,
            "photographer_phone": o.photographer.phone if o.photographer else None,
        })
    return d


@router.post("")
def create_order(
    photo_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Abre um pedido de compra. Idempotente: se já existe um pedido em aberto
    para esta foto e este comprador, devolve o mesmo pedido."""
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    if not photo.is_for_sale:
        raise HTTPException(status_code=400, detail="Esta foto não está à venda")
    if photo.photographer_id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode comprar sua própria foto")

    existing = (
        db.query(models.Order)
        .filter(
            models.Order.photo_id == photo_id,
            models.Order.buyer_id == current_user.id,
            models.Order.status.in_(["pending", "paid"]),
        )
        .order_by(models.Order.id.desc())
        .first()
    )
    if existing:
        return _order_dict(existing)

    price = float(photo.price or 0)
    commission = round(price * COMMISSION_RATE, 2)

    order = models.Order(
        photo_id=photo.id,
        buyer_id=current_user.id,
        photographer_id=photo.photographer_id,
        price=price,
        commission=commission,
        payout=round(price - commission, 2),
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_dict(order)


@router.get("/me")
def my_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Pedidos feitos pelo comprador logado."""
    orders = (
        db.query(models.Order)
        .filter(models.Order.buyer_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return [_order_dict(o) for o in orders]


@router.get("/sales")
def my_sales(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Vendas das fotos do fotógrafo logado."""
    orders = (
        db.query(models.Order)
        .filter(models.Order.photographer_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    result = []
    for o in orders:
        d = _order_dict(o)
        d["payout"] = o.payout
        d["commission"] = o.commission
        d["buyer_name"] = o.buyer.name if o.buyer else None
        result.append(d)
    return result


@router.get("/admin")
def admin_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(auth.get_admin_user),
):
    """Todos os pedidos, com dados de contato — só para o administrador."""
    query = db.query(models.Order)
    if status:
        if status not in STATUSES:
            raise HTTPException(status_code=400, detail="Status inválido")
        query = query.filter(models.Order.status == status)
    orders = query.order_by(models.Order.created_at.desc()).all()

    totals = {
        "pending": sum(1 for o in orders if o.status == "pending"),
        "paid": sum(1 for o in orders if o.status == "paid"),
        "revenue": round(sum(o.commission for o in orders if o.status == "paid"), 2),
        "payouts": round(sum(o.payout for o in orders if o.status == "paid"), 2),
    }
    return {"totals": totals, "orders": [_order_dict(o, for_admin=True) for o in orders]}


@router.put("/{order_id}/status")
def update_order_status(
    order_id: int,
    status: str = Form(...),
    note: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(auth.get_admin_user),
):
    """Administrador marca o pedido como pago ou cancelado."""
    if status not in STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    order.status = status
    order.paid_at = datetime.utcnow() if status == "paid" else None
    if note is not None:
        order.note = note.strip() or None

    db.commit()
    db.refresh(order)
    return _order_dict(order, for_admin=True)


@router.get("/{order_id}/download")
def download_purchase(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Libera o arquivo original para o comprador de um pedido pago."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if order.buyer_id != current_user.id and not auth.is_admin(current_user):
        raise HTTPException(status_code=403, detail="Este pedido não é seu")
    if order.status != "paid":
        raise HTTPException(status_code=402, detail="Pagamento ainda não confirmado")

    photo = order.photo
    if not photo or not photo.original_path:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    if not order.downloaded_at:
        order.downloaded_at = datetime.utcnow()
        db.commit()

    return RedirectResponse(url=photo.original_path)

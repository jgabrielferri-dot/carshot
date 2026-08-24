from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    nickname = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    account_type = Column(String, nullable=False)  # "buyer" or "photographer"
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    cpf = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    photos = relationship("Photo", back_populates="photographer", cascade="all, delete-orphan")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    photographer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    car = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    model = Column(String, nullable=True)
    color = Column(String, nullable=True)
    plate = Column(String, nullable=True)
    event = Column(String, nullable=True)
    location = Column(String, nullable=True)
    event_date = Column(String, nullable=True)
    event_time = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=True)
    is_for_sale = Column(Boolean, default=False)
    original_path = Column(String, nullable=False)
    watermarked_path = Column(String, nullable=True)
    resolution = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    photographer = relationship("User", back_populates="photos")


class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    followed_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Save(Base):
    __tablename__ = "saves"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])


class Order(Base):
    """Pedido de compra de uma foto.

    O fluxo hoje é manual: o comprador abre o pedido pelo site, negocia o
    pagamento pelo WhatsApp e o administrador marca como pago. A partir daí
    o download do arquivo original é liberado para o comprador.
    """

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    photographer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    price = Column(Float, nullable=False, default=0.0)
    commission = Column(Float, nullable=False, default=0.0)   # fica com a plataforma
    payout = Column(Float, nullable=False, default=0.0)       # repasse ao fotógrafo

    # "pending" (aguardando pagamento) | "paid" (liberado) | "cancelled"
    status = Column(String, nullable=False, default="pending", index=True)
    note = Column(Text, nullable=True)                        # anotação interna do admin

    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)

    photo = relationship("Photo", foreign_keys=[photo_id])
    buyer = relationship("User", foreign_keys=[buyer_id])
    photographer = relationship("User", foreign_keys=[photographer_id])

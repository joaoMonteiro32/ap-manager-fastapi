from sqlalchemy import Column, Integer, String, DateTime, func
from .database import Base


class AP(Base):
    __tablename__ = "aps"

    id = Column(Integer, primary_key=True, index=True)
    mac = Column(String(17), unique=True, nullable=False, index=True)
    quarto = Column(String(20), nullable=False, unique=True, index=True)  # <-- corrigido
    foto_path = Column(String(255), nullable=True)
    data_registo = Column(DateTime, server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="tecnico")
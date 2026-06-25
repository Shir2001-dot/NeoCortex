from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.database import Base


# ORM model
class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    specialty: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    license_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)


# Pydantic schemas
class DoctorCreate(BaseModel):
    name: str
    specialty: str
    email: EmailStr
    phone: Optional[str] = None
    license_number: str


class DoctorResponse(DoctorCreate):
    id: int

    class Config:
        from_attributes = True

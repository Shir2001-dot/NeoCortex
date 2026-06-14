import os

from sqlalchemy import JSON, Column, DateTime, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.models import PatientRecord

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///neocortex.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


class PatientRecordRow(Base):
    __tablename__ = "patient_records"

    patient_id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False)


Base.metadata.create_all(engine)


def save_record(record: PatientRecord) -> None:
    with SessionLocal() as session:
        session.merge(
            PatientRecordRow(
                patient_id=record.patient_id,
                data=record.model_dump(mode="json"),
                created_at=record.created_at,
            )
        )
        session.commit()


def get_record(patient_id: str) -> PatientRecord | None:
    with SessionLocal() as session:
        row = session.get(PatientRecordRow, patient_id)
        if row is None:
            return None
        return PatientRecord(**row.data)

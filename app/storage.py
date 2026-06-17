import json
import os

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.models import PatientMaster, PatientRecord, PatientTransaction

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///neocortex.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


class PatientRecordRow(Base):
    __tablename__ = "patient_records"

    patient_id = Column(String, primary_key=True)
    data = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class PatientMasterRow(Base):
    __tablename__ = "patient_master"

    patient_id = Column(String, primary_key=True)
    full_name = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True)
    gender = Column(String, nullable=True)


class PatientTransactionRow(Base):
    __tablename__ = "patient_transactions"

    transaction_id = Column(String, primary_key=True)
    patient_id = Column(String, ForeignKey("patient_master.patient_id"), nullable=False)
    date = Column(String, nullable=False)
    transaction_type = Column(String, nullable=False, default="referral")
    raw_text = Column(Text, nullable=False, default="")
    extracted_json = Column(Text, nullable=False)


Base.metadata.create_all(engine)


def save_record(record: PatientRecord) -> None:
    with SessionLocal() as session:
        session.merge(
            PatientRecordRow(
                patient_id=record.patient_id,
                data=record.model_dump_json(),
                created_at=record.created_at,
            )
        )
        session.commit()


def _parse(data) -> dict:
    """Handle both str (Text column) and dict (JSON column) from DB."""
    if isinstance(data, dict):
        return data
    return json.loads(data)


def get_record(patient_id: str) -> PatientRecord | None:
    with SessionLocal() as session:
        row = session.get(PatientRecordRow, patient_id)
        if row is None:
            return None
        return PatientRecord(**_parse(row.data))


def upsert_master(patient_id: str, full_name: str | None, dob: str | None, gender: str | None) -> None:
    with SessionLocal() as session:
        existing = session.get(PatientMasterRow, patient_id)
        if existing:
            if full_name: existing.full_name = full_name
            if dob: existing.date_of_birth = dob
            if gender: existing.gender = gender
        else:
            session.add(PatientMasterRow(
                patient_id=patient_id,
                full_name=full_name,
                date_of_birth=dob,
                gender=gender,
            ))
        session.commit()


def save_transaction(tx: PatientTransaction) -> None:
    with SessionLocal() as session:
        row = PatientTransactionRow(
            transaction_id=tx.transaction_id,
            patient_id=tx.patient_id,
            date=tx.date,
            transaction_type=tx.transaction_type.value,
            raw_text=tx.raw_text,
            extracted_json=tx.extracted.model_dump_json(),
        )
        session.merge(row)
        session.commit()


def get_transactions(patient_id: str) -> list[PatientTransaction]:
    with SessionLocal() as session:
        rows = session.query(PatientTransactionRow).filter_by(patient_id=patient_id).order_by(PatientTransactionRow.date.desc()).all()
        result = []
        for row in rows:
            extracted = PatientRecord(**_parse(row.extracted_json))
            result.append(PatientTransaction(
                transaction_id=row.transaction_id,
                patient_id=row.patient_id,
                date=row.date,
                transaction_type=row.transaction_type,
                raw_text=row.raw_text,
                extracted=extracted,
            ))
        return result


def get_master(patient_id: str) -> PatientMaster | None:
    with SessionLocal() as session:
        row = session.get(PatientMasterRow, patient_id)
        if row is None:
            return None
        transactions = get_transactions(patient_id)
        return PatientMaster(
            patient_id=row.patient_id,
            full_name=row.full_name,
            date_of_birth=row.date_of_birth,
            gender=row.gender,
            transactions=transactions,
        )


def list_patients() -> list[PatientMaster]:
    with SessionLocal() as session:
        rows = session.query(PatientMasterRow).all()
        return [
            PatientMaster(
                patient_id=row.patient_id,
                full_name=row.full_name,
                date_of_birth=row.date_of_birth,
                gender=row.gender,
                transactions=[],
            )
            for row in rows
        ]

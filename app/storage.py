import json
import os
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.models import PatientMaster, PatientRecord, PatientTransaction

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///neocortex.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


class ClinicRow(Base):
    __tablename__ = "clinics"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserRow(Base):
    __tablename__ = "users"
    id_number = Column(String, primary_key=True)
    full_name = Column(String, nullable=False)
    specialty = Column(String, nullable=True)
    role = Column(String, nullable=False)
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    hashed_password = Column(String, nullable=False)
    permissions = Column(Text, nullable=True)  # JSON list of permission strings
    created_at = Column(DateTime, default=datetime.utcnow)


# Default permissions per role
ROLE_DEFAULT_PERMISSIONS = {
    "admin": [],  # admin has all via role check
    "doctor": ["view_records", "edit_records", "prescribe", "clinical_analysis", "session_summary", "drug_interactions"],
    "secretary": ["view_records"],
}


class PatientRecordRow(Base):
    __tablename__ = "patient_records"

    patient_id = Column(String, primary_key=True)
    data = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    clinic_id = Column(String, nullable=True)
    doctor_id_number = Column(String, nullable=True)
    specialty = Column(String, nullable=True)


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
    clinic_id = Column(String, nullable=True)
    doctor_id_number = Column(String, nullable=True)


Base.metadata.create_all(engine)


def _run_migrations() -> None:
    """Add missing columns to existing tables (safe to run on every startup)."""
    migrations = [
        "ALTER TABLE patient_records ADD COLUMN IF NOT EXISTS clinic_id VARCHAR",
        "ALTER TABLE patient_records ADD COLUMN IF NOT EXISTS doctor_id_number VARCHAR",
        "ALTER TABLE patient_records ADD COLUMN IF NOT EXISTS specialty VARCHAR",
        "ALTER TABLE patient_master ADD COLUMN IF NOT EXISTS clinic_id VARCHAR",
        "ALTER TABLE patient_master ADD COLUMN IF NOT EXISTS doctor_id_number VARCHAR",
        "ALTER TABLE patient_master ADD COLUMN IF NOT EXISTS specialty VARCHAR",
        "ALTER TABLE patient_transactions ADD COLUMN IF NOT EXISTS clinic_id VARCHAR",
        "ALTER TABLE patient_transactions ADD COLUMN IF NOT EXISTS doctor_id_number VARCHAR",
        "ALTER TABLE patient_transactions ADD COLUMN IF NOT EXISTS specialty VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions TEXT",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass

        # Backfill permissions for existing users that have NULL
        for role, perms in ROLE_DEFAULT_PERMISSIONS.items():
            if role == "admin":
                continue
            try:
                conn.execute(text(
                    "UPDATE users SET permissions = :p WHERE role = :r AND permissions IS NULL"
                ), {"p": json.dumps(perms), "r": role})
            except Exception:
                pass

        conn.commit()


_run_migrations()


def seed_demo_data(session) -> None:
    """Create demo clinic and users if they don't already exist."""
    from app.auth import hash_password

    # Check if already seeded
    if session.get(UserRow, "000000000"):
        return

    # Create demo clinic
    clinic = session.get(ClinicRow, "clinic-demo")
    if not clinic:
        session.add(ClinicRow(id="clinic-demo", name="קליניקת הדגמה"))

    # Admin
    session.add(UserRow(
        id_number="000000000",
        full_name="מנהל מערכת",
        specialty=None,
        role="admin",
        clinic_id="clinic-demo",
        hashed_password=hash_password("admin123"),
        permissions=json.dumps([]),
    ))

    # Doctor — full permissions
    session.add(UserRow(
        id_number="123456789",
        full_name='ד"ר כהן',
        specialty="פסיכיאטריה",
        role="doctor",
        clinic_id="clinic-demo",
        hashed_password=hash_password("doctor123"),
        permissions=json.dumps(ROLE_DEFAULT_PERMISSIONS["doctor"]),
    ))

    # Secretary — read only
    session.add(UserRow(
        id_number="987654321",
        full_name="שרה לוי",
        specialty=None,
        role="secretary",
        clinic_id="clinic-demo",
        hashed_password=hash_password("secretary123"),
        permissions=json.dumps(ROLE_DEFAULT_PERMISSIONS["secretary"]),
    ))

    session.commit()


def get_user_by_id(session, id_number: str) -> UserRow | None:
    return session.get(UserRow, id_number)


def get_users_by_clinic(session, clinic_id: str) -> list:
    return session.query(UserRow).filter_by(clinic_id=clinic_id).all()


def create_user(session, id_number: str, full_name: str, specialty: str | None,
                role: str, clinic_id: str, hashed_password: str,
                permissions: list | None = None) -> UserRow:
    perms = permissions if permissions is not None else ROLE_DEFAULT_PERMISSIONS.get(role, [])
    user = UserRow(
        id_number=id_number,
        full_name=full_name,
        specialty=specialty,
        role=role,
        clinic_id=clinic_id,
        hashed_password=hashed_password,
        permissions=json.dumps(perms),
    )
    session.add(user)
    session.commit()
    return user


def delete_user(session, id_number: str) -> bool:
    user = session.get(UserRow, id_number)
    if user is None:
        return False
    session.delete(user)
    session.commit()
    return True


def get_clinic(session, clinic_id: str) -> ClinicRow | None:
    return session.get(ClinicRow, clinic_id)


def get_patients_by_clinic(session, clinic_id: str) -> list:
    from sqlalchemy import or_
    return (session.query(PatientRecordRow)
            .filter(or_(PatientRecordRow.clinic_id == clinic_id,
                        PatientRecordRow.clinic_id == None))
            .all())


def save_record(record: PatientRecord, clinic_id: str | None = None,
                doctor_id_number: str | None = None, specialty: str | None = None) -> None:
    with SessionLocal() as session:
        session.merge(
            PatientRecordRow(
                patient_id=record.patient_id,
                data=record.model_dump_json(),
                created_at=record.created_at,
                clinic_id=clinic_id,
                doctor_id_number=doctor_id_number,
                specialty=specialty,
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


def save_transaction(tx: PatientTransaction, clinic_id: str | None = None,
                     doctor_id_number: str | None = None) -> None:
    with SessionLocal() as session:
        row = PatientTransactionRow(
            transaction_id=tx.transaction_id,
            patient_id=tx.patient_id,
            date=tx.date,
            transaction_type=tx.transaction_type.value,
            raw_text=tx.raw_text,
            extracted_json=tx.extracted.model_dump_json(),
            clinic_id=clinic_id,
            doctor_id_number=doctor_id_number,
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

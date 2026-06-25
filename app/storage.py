import base64
import json
import os
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.models import PatientMaster, PatientRecord, PatientTransaction

# ─── Field-level encryption ───
_raw_key = os.environ.get("ENCRYPTION_KEY", "")
if _raw_key:
    _fernet = Fernet(_raw_key.encode() if len(_raw_key) == 44 else base64.urlsafe_b64encode(_raw_key.encode()[:32].ljust(32, b"\0")))
else:
    # Dev mode: generate a temporary in-process key (data is NOT persisted encrypted across restarts)
    _fernet = Fernet(Fernet.generate_key())

def _encrypt(value: str) -> str:
    if not value:
        return value
    return _fernet.encrypt(value.encode()).decode()

def _decrypt(value: str) -> str:
    if not value:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return value  # already plaintext (legacy row)

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
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordResetTokenRow(Base):
    __tablename__ = "password_reset_tokens"
    token = Column(String, primary_key=True)
    id_number = Column(String, ForeignKey("users.id_number"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(String, default="0")


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


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(String, nullable=False)
    user_name = Column(String, nullable=True)
    clinic_id = Column(String, nullable=True)
    action = Column(String, nullable=False)   # e.g. "view_patient", "ingest", "decision"
    patient_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)


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
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR",
        # Fix: convert JSON columns to TEXT to support encrypted data
        "ALTER TABLE patient_records ALTER COLUMN data TYPE TEXT USING data::TEXT",
        "ALTER TABLE patient_transactions ALTER COLUMN extracted_json TYPE TEXT USING extracted_json::TEXT",
        "ALTER TABLE patient_transactions ALTER COLUMN raw_text TYPE TEXT USING raw_text::TEXT",
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

    # Demo patient
    demo_patient_id = "555555555"
    existing_master = session.query(PatientMasterRow).filter_by(patient_id=demo_patient_id).first()
    if not existing_master:
        import uuid as _uuid
        internal_id = str(_uuid.uuid4())
        record = PatientRecord(
            patient_id=demo_patient_id,
            internal_id=internal_id,
            full_name="דוד לוי",
            date_of_birth="1968-03-15",
            gender="זכר",
            chief_complaint="חרדה מוגברת, קשיי שינה, ודיכאון מתמשך",
            symptoms=["חרדה", "נדודי שינה", "מצב רוח ירוד", "עייפות", "קשיי ריכוז"],
            medical_history=[
                {"name": "הפרעת חרדה מוכללת", "active": True, "onset_date": "2018-01-01"},
                {"name": "דיכאון מז'ורי", "active": True, "onset_date": "2019-06-01"},
                {"name": "יתר לחץ דם", "active": True, "onset_date": "2020-03-01"},
            ],
            medications=[
                "קלונקס (קלונאזפאם) 0.5 מ\"ג - פעמיים ביום",
                "ציפרלקס (אסציטאלופרם) 20 מ\"ג - פעם ביום",
                "אנאפריל (פרופרנולול) 40 מ\"ג - פעמיים ביום",
                "זולפידם 10 מ\"ג - לפני שינה",
            ],
            allergies=["פניצילין"],
            lab_results=[
                {"name": "TSH", "value": "2.1", "unit": "mIU/L", "reference_range": "0.4-4.0", "flag": None},
                {"name": "סוכר בצום", "value": "98", "unit": "mg/dL", "reference_range": "70-100", "flag": None},
                {"name": "נתרן", "value": "138", "unit": "mEq/L", "reference_range": "136-145", "flag": None},
            ],
            vitals={"heart_rate": 88, "blood_pressure_systolic": 142, "blood_pressure_diastolic": 91, "temperature_celsius": 36.7, "respiratory_rate": 16, "spo2_percent": 98},
            referral_reason="המשך מעקב פסיכיאטרי. המטופל מדווח על החמרה בחרדה בחודש האחרון. נדרשת הערכת תרופות.",
            referral_date="2026-06-20",
            source="text",
            raw_text="מטופל דוד לוי, יליד 15.3.1968. מעקב פסיכיאטרי.",
        )
        master = PatientMaster(
            patient_id=demo_patient_id,
            full_name="דוד לוי",
            date_of_birth="1968-03-15",
            gender="זכר",
            transactions=[],
        )
        session.add(PatientMasterRow(
            patient_id=demo_patient_id,
            clinic_id="clinic-demo",
            data=_encrypt(master.model_dump_json()),
        ))
        session.add(PatientRecordRow(
            internal_id=internal_id,
            patient_id=demo_patient_id,
            clinic_id="clinic-demo",
            data=_encrypt(record.model_dump_json()),
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


def get_user_by_email(session, email: str) -> UserRow | None:
    return session.query(UserRow).filter_by(email=email).first()


def update_user_password(session, id_number: str, new_hashed: str) -> bool:
    user = session.get(UserRow, id_number)
    if not user:
        return False
    user.hashed_password = new_hashed
    session.commit()
    return True


def update_user_email(session, id_number: str, email: str) -> bool:
    user = session.get(UserRow, id_number)
    if not user:
        return False
    user.email = email
    session.commit()
    return True


def create_reset_token(session, id_number: str) -> str:
    import secrets
    from datetime import timedelta
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=1)
    session.add(PasswordResetTokenRow(token=token, id_number=id_number, expires_at=expires))
    session.commit()
    return token


def get_reset_token(session, token: str) -> PasswordResetTokenRow | None:
    row = session.get(PasswordResetTokenRow, token)
    if not row or row.used == "1" or row.expires_at < datetime.utcnow():
        return None
    return row


def consume_reset_token(session, token: str) -> bool:
    row = session.get(PasswordResetTokenRow, token)
    if not row:
        return False
    row.used = "1"
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


def search_patients_by_clinic(session, clinic_id: str, query: str) -> list[dict]:
    """Search patients by name, medication, or diagnosis. Returns decrypted matching records."""
    rows = get_patients_by_clinic(session, clinic_id)
    q = query.strip().lower()
    results = []
    for row in rows:
        try:
            data = json.loads(_decrypt(row.data) if row.data else "{}")
        except Exception:
            continue
        # Search in name
        name = (data.get("full_name") or "").lower()
        # Search in medications
        meds = " ".join(data.get("medications") or []).lower()
        # Search in medical_history (conditions)
        history = data.get("medical_history") or []
        conditions = " ".join(
            (c.get("name") if isinstance(c, dict) else str(c)) for c in history
        ).lower()
        # Search in chief_complaint and symptoms
        complaint = (data.get("chief_complaint") or "").lower()
        symptoms = " ".join(data.get("symptoms") or []).lower()

        if q in name or q in meds or q in conditions or q in complaint or q in symptoms:
            results.append({
                "patient_id": data.get("patient_id", row.patient_id),
                "internal_id": data.get("internal_id"),
                "full_name": data.get("full_name"),
                "date_of_birth": data.get("date_of_birth"),
                "gender": data.get("gender"),
                "medications": data.get("medications", []),
                "medical_history": history,
                "chief_complaint": data.get("chief_complaint"),
            })
    return results


def get_all_records_for_export(session, clinic_id: str) -> list[dict]:
    """Return all decrypted patient records for Excel export."""
    rows = get_patients_by_clinic(session, clinic_id)
    results = []
    for row in rows:
        try:
            data = json.loads(_decrypt(row.data) if row.data else "{}")
            results.append(data)
        except Exception:
            continue
    return results


def save_record(record: PatientRecord, clinic_id: str | None = None,
                doctor_id_number: str | None = None, specialty: str | None = None) -> None:
    with SessionLocal() as session:
        session.merge(
            PatientRecordRow(
                patient_id=record.patient_id,
                data=_encrypt(record.model_dump_json()),
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


def _migrate_record_dict(data: dict) -> dict:
    mh = data.get("medical_history", [])
    if mh and isinstance(mh[0], str):
        data["medical_history"] = [{"name": s, "active": True, "onset_date": None} for s in mh]
    return data


def get_record(patient_id: str) -> PatientRecord | None:
    with SessionLocal() as session:
        row = session.get(PatientRecordRow, patient_id)
        if row is None:
            return None
        return PatientRecord(**_migrate_record_dict(_parse(_decrypt(row.data))))


def get_record_by_internal_id(internal_id: str) -> PatientRecord | None:
    with SessionLocal() as session:
        rows = session.query(PatientRecordRow).all()
        for row in rows:
            try:
                data = _parse(_decrypt(row.data))
                if data.get("internal_id") == internal_id:
                    return PatientRecord(**_migrate_record_dict(data))
            except Exception:
                continue
        return None


def upsert_master(patient_id: str, full_name: str | None, dob: str | None, gender: str | None) -> None:
    with SessionLocal() as session:
        existing = session.get(PatientMasterRow, patient_id)
        if existing:
            if full_name: existing.full_name = _encrypt(full_name)
            if dob: existing.date_of_birth = _encrypt(dob)
            if gender: existing.gender = _encrypt(gender)
        else:
            session.add(PatientMasterRow(
                patient_id=patient_id,
                full_name=_encrypt(full_name) if full_name else None,
                date_of_birth=_encrypt(dob) if dob else None,
                gender=_encrypt(gender) if gender else None,
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
            raw_text=_encrypt(tx.raw_text),
            extracted_json=_encrypt(tx.extracted.model_dump_json()),
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
            extracted = PatientRecord(**_migrate_record_dict(_parse(_decrypt(row.extracted_json))))
            result.append(PatientTransaction(
                transaction_id=row.transaction_id,
                patient_id=row.patient_id,
                date=row.date,
                transaction_type=row.transaction_type,
                raw_text=_decrypt(row.raw_text),
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
            full_name=_decrypt(row.full_name) if row.full_name else None,
            date_of_birth=_decrypt(row.date_of_birth) if row.date_of_birth else None,
            gender=_decrypt(row.gender) if row.gender else None,
            transactions=transactions,
        )


def list_patients() -> list[PatientMaster]:
    with SessionLocal() as session:
        rows = session.query(PatientMasterRow).all()
        return [
            PatientMaster(
                patient_id=row.patient_id,
                full_name=_decrypt(row.full_name) if row.full_name else None,
                date_of_birth=_decrypt(row.date_of_birth) if row.date_of_birth else None,
                gender=_decrypt(row.gender) if row.gender else None,
                transactions=[],
            )
            for row in rows
        ]


def log_action(user_id: str, action: str, user_name: str | None = None,
               clinic_id: str | None = None, patient_id: str | None = None,
               detail: str | None = None) -> None:
    import uuid
    today = datetime.utcnow().date().isoformat()
    with SessionLocal() as session:
        # For view_patient: only log once per doctor+patient per day
        if action == "view_patient" and patient_id:
            existing = (session.query(AuditLogRow)
                        .filter_by(user_id=user_id, action="view_patient", patient_id=patient_id)
                        .filter(AuditLogRow.detail == today)
                        .first())
            if existing:
                return
        session.add(AuditLogRow(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_name=user_name,
            clinic_id=clinic_id,
            action=action,
            patient_id=patient_id,
            detail=today if action == "view_patient" else detail,
        ))
        session.commit()


def get_audit_log(clinic_id: str, limit: int = 200) -> list[dict]:
    with SessionLocal() as session:
        rows = (session.query(AuditLogRow)
                .filter_by(clinic_id=clinic_id)
                .order_by(AuditLogRow.timestamp.desc())
                .limit(limit)
                .all())
        return [
            {
                "timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M"),
                "user_name": row.user_name or row.user_id,
                "action": row.action,
                "patient_id": row.patient_id or "—",
                "detail": row.detail or "",
            }
            for row in rows
        ]

"""Seed initial doctors into the SQLite database."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, engine, Base
from app.models.doctor import Doctor

Base.metadata.create_all(bind=engine)

DOCTORS = [
    {
        "name": "Dr. Sarah Levi",
        "specialty": "Neurology",
        "email": "sarah.levi@neocortex.health",
        "phone": "+972-50-1001001",
        "license_number": "IL-NEU-001",
    },
    {
        "name": "Dr. Alex Goren",
        "specialty": "Internal Medicine",
        "email": "alex.goren@neocortex.health",
        "phone": "+972-50-2002002",
        "license_number": "IL-INT-002",
    },
    {
        "name": "Dr. Dana Cohen",
        "specialty": "Cardiology",
        "email": "dana.cohen@neocortex.health",
        "phone": "+972-50-3003003",
        "license_number": "IL-CAR-003",
    },
]


def seed():
    db = SessionLocal()
    added = []
    skipped = []
    try:
        for data in DOCTORS:
            existing = db.query(Doctor).filter(Doctor.email == data["email"]).first()
            if existing:
                skipped.append(data["name"])
                continue
            db.add(Doctor(**data))
            added.append(data["name"])
        db.commit()
    finally:
        db.close()

    if added:
        print(f"Added: {', '.join(added)}")
    if skipped:
        print(f"Skipped (already exist): {', '.join(skipped)}")

    # Verify
    db = SessionLocal()
    try:
        doctors = db.query(Doctor).all()
        print(f"\nDatabase now contains {len(doctors)} doctor(s):")
        for d in doctors:
            print(f"  [{d.id}] {d.name} — {d.specialty} ({d.email})")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

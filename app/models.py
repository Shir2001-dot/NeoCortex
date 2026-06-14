from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VitalSigns(BaseModel):
    heart_rate: Optional[float] = Field(None, description="Beats per minute")
    blood_pressure_systolic: Optional[float] = None
    blood_pressure_diastolic: Optional[float] = None
    temperature_celsius: Optional[float] = None
    respiratory_rate: Optional[float] = None
    spo2_percent: Optional[float] = None


class LabResult(BaseModel):
    name: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = Field(None, description="e.g. 'high', 'low', 'critical'")


class PatientRecord(BaseModel):
    patient_id: str
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None

    chief_complaint: Optional[str] = None
    symptoms: list[str] = Field(default_factory=list)
    medical_history: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    vitals: Optional[VitalSigns] = None
    referral_reason: Optional[str] = None

    source: str = Field(description="e.g. 'pdf', 'text', 'wearable'")
    raw_text: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IngestTextRequest(BaseModel):
    patient_id: str
    text: str


class DecisionFlag(BaseModel):
    severity: str = Field(description="'info', 'warning', or 'critical'")
    message: str


class DecisionResult(BaseModel):
    patient_id: str
    flags: list[DecisionFlag] = Field(default_factory=list)
    differential_diagnosis: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

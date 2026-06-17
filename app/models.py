from datetime import datetime
from enum import Enum
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


class IngestPdfRequest(BaseModel):
    patient_id: str
    pdf_base64: str


class VitalsUpdateRequest(BaseModel):
    heart_rate: Optional[float] = None
    blood_pressure_systolic: Optional[float] = None
    blood_pressure_diastolic: Optional[float] = None
    temperature_celsius: Optional[float] = None
    respiratory_rate: Optional[float] = None
    spo2_percent: Optional[float] = None


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


class TransactionType(str, Enum):
    referral = "referral"
    hospitalization = "hospitalization"
    visit = "visit"
    test = "test"


class PatientTransaction(BaseModel):
    transaction_id: str
    patient_id: str
    date: str
    transaction_type: TransactionType = TransactionType.referral
    raw_text: str = ""
    extracted: PatientRecord


class SessionSummaryRequest(BaseModel):
    notes: str


class SessionSummaryResult(BaseModel):
    patient_id: str
    summary: str


class SaveSummaryRequest(BaseModel):
    summary: str
    doctor_name: Optional[str] = None


class PatientMaster(BaseModel):
    patient_id: str
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    transactions: list[PatientTransaction] = []


class DrugInteraction(BaseModel):
    drugs: list[str]
    severity: str
    description: str


class InteractionsResult(BaseModel):
    patient_id: str
    interactions: list[DrugInteraction] = []


class CreateUserRequest(BaseModel):
    id_number: str
    full_name: str
    specialty: Optional[str] = None
    role: str  # "doctor", "secretary", "admin"
    password: str


class UserInfo(BaseModel):
    id_number: str
    full_name: str
    specialty: Optional[str]
    role: str
    clinic_id: str

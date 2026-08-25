"""
Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TriageSeverityEnum(str, Enum):
    RESUSCITATION = "1_resuscitation"
    EMERGENT = "2_emergent"
    URGENT = "3_urgent"
    MINOR = "4_minor"
    FAST_TRACK = "5_fast_track"


class VitalSignsRequest(BaseModel):
    """Vital signs input"""
    temperature_celsius: Optional[float] = Field(None, ge=-5, le=45)
    heart_rate: Optional[int] = Field(None, ge=0, le=300)
    respiratory_rate: Optional[int] = Field(None, ge=0, le=60)
    systolic_bp: Optional[int] = Field(None, ge=0, le=300)
    diastolic_bp: Optional[int] = Field(None, ge=0, le=200)
    oxygen_saturation: Optional[float] = Field(None, ge=50, le=100)
    pain_score: Optional[int] = Field(None, ge=0, le=10)
    consciousness_alert: bool = True
    chief_complaint: Optional[str] = Field(None, max_length=500)


class PatientIntakeRequest(BaseModel):
    """Patient intake/registration"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: datetime  # ISO format: 1990-05-15
    gender: str = Field(..., min_length=1, max_length=20)
    mrn: Optional[str] = Field(None, max_length=50)  # Medical Record Number
    vitals: VitalSignsRequest
    chief_complaint: str = Field(..., min_length=1, max_length=500)


class TriageScoreResponse(BaseModel):
    """Triage scoring response"""
    decision_id: str
    patient_id: str
    severity_level: TriageSeverityEnum
    confidence_score: float = Field(..., ge=0, le=1)
    reasoning: List[str]
    escalation_flags: List[str]
    data_quality_warning: bool
    data_completeness: dict = Field(...)
    wait_time_at_decision: int  # seconds
    timestamp: datetime


class TriageOverrideRequest(BaseModel):
    """Clinician override of triage score"""
    decision_id: str
    overridden_severity: TriageSeverityEnum
    override_reason: Optional[str] = Field(None, max_length=500)
    clinician_id: str = Field(..., min_length=1, max_length=50)
    clinician_name: str = Field(..., min_length=1, max_length=100)


class TriageOverrideResponse(BaseModel):
    """Response to override"""
    override_id: str
    decision_id: str
    patient_id: str
    original_severity: TriageSeverityEnum
    overridden_severity: TriageSeverityEnum
    clinician_id: str
    clinician_name: str
    override_reason: Optional[str]
    timestamp: datetime


class AuditLogEntry(BaseModel):
    """Single audit log entry"""
    log_id: str
    event_type: str
    event_description: str
    event_payload: dict
    clinician_id: Optional[str]
    clinician_name: Optional[str]
    patient_id: Optional[str]
    timestamp: datetime


class PatientTriageQueueResponse(BaseModel):
    """Patient summary in triage queue"""
    patient_id: str
    first_name: str
    last_name: str
    age_years: float
    chief_complaint: str
    severity_level: TriageSeverityEnum
    confidence_score: float
    wait_time_minutes: int
    data_quality_warning: bool
    triage_timestamp: datetime
    has_override: bool


class SurgeMetricsResponse(BaseModel):
    """System metrics during surge"""
    current_queue_size: int
    avg_wait_time_minutes: float
    patients_per_severity: dict
    system_load_percentage: float
    estimated_throughput_per_hour: float
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None

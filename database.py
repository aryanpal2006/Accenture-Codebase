from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime, 
    Boolean, Text, ForeignKey, Index, Enum, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://triage_user:triage_secure_pass_2024@localhost:5432/triage_db"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TriageSeverityLevel(str, enum.Enum):
    """5-level ESI triage severity scale"""
    RESUSCITATION = "1_resuscitation"      # Immediate life threat
    EMERGENT = "2_emergent"                # High-risk or severe pain
    URGENT = "3_urgent"                    # Moderate risk or pain
    MINOR = "4_minor"                      # Low risk, minimal pain
    FAST_TRACK = "5_fast_track"            # Minor injury/illness, no monitoring needed


class AgeGroup(str, enum.Enum):
    """Age groups for threshold calibration"""
    PEDIATRIC = "pediatric"  # 0-12 years
    ADOLESCENT = "adolescent"  # 13-17 years
    ADULT = "adult"  # 18-64 years
    GERIATRIC = "geriatric"  # 65+ years


class Patient(Base):
    __tablename__ = "patients"
    
    patient_id = Column(String(36), primary_key=True, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(20))
    mrn = Column(String(50), unique=True, nullable=True, index=True)  # Medical Record Number
    is_returning_patient = Column(Boolean, default=False)
    chief_complaint = Column(Text)
    
    # Relationships
    vitals = relationship("VitalSigns", back_populates="patient", cascade="all, delete-orphan")
    triage_records = relationship("TriageDecision", back_populates="patient", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="patient", cascade="all, delete-orphan")
    
    arrival_timestamp = Column(DateTime, server_default=func.now(), index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VitalSigns(Base):
    __tablename__ = "vital_signs"
    
    vital_id = Column(String(36), primary_key=True, index=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), index=True)
    
    temperature_celsius = Column(Float, nullable=True)  # Core temp
    heart_rate = Column(Integer, nullable=True)  # beats per minute
    respiratory_rate = Column(Integer, nullable=True)  # breaths per minute
    systolic_bp = Column(Integer, nullable=True)  # mmHg
    diastolic_bp = Column(Integer, nullable=True)  # mmHg
    oxygen_saturation = Column(Float, nullable=True)  # %
    pain_score = Column(Integer, nullable=True)  # 0-10 numeric rating
    consciousness_alert = Column(Boolean, default=True)  # Altered mental status?
    
    measured_at = Column(DateTime, server_default=func.now(), index=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship
    patient = relationship("Patient", back_populates="vitals")
    
    __table_args__ = (
        Index('idx_patient_measured', 'patient_id', 'measured_at'),
    )


class TriageDecision(Base):
    __tablename__ = "triage_decisions"
    
    decision_id = Column(String(36), primary_key=True, index=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), index=True)
    
    # Triage scoring
    severity_score = Column(Enum(TriageSeverityLevel), nullable=False, index=True)
    confidence_score = Column(Float)  # 0.0-1.0, how confident is the model?
    reasoning = Column(Text)  # JSON serialized list of decision factors
    
    # Data completeness metrics
    data_completeness_vitals = Column(Float)  # % of vital fields populated
    data_completeness_history = Column(Float)  # % of historical data available
    
    # Waiting state
    wait_time_at_decision = Column(Integer)  # seconds
    triage_timestamp = Column(DateTime, server_default=func.now(), index=True)
    
    # Relationship
    patient = relationship("Patient", back_populates="triage_records")
    overrides = relationship("ClinicalOverride", back_populates="triage_decision", cascade="all, delete-orphan")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_patient_severity', 'patient_id', 'severity_score'),
        Index('idx_triage_timestamp', 'triage_timestamp'),
    )


class ClinicalOverride(Base):
    __tablename__ = "clinical_overrides"
    
    override_id = Column(String(36), primary_key=True, index=True)
    decision_id = Column(String(36), ForeignKey("triage_decisions.decision_id"), index=True)
    
    original_severity = Column(Enum(TriageSeverityLevel))
    overridden_severity = Column(Enum(TriageSeverityLevel))
    
    clinician_id = Column(String(50), index=True)  # User who made override
    clinician_name = Column(String(100))
    override_reason = Column(Text, nullable=True)
    
    override_timestamp = Column(DateTime, server_default=func.now(), index=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship
    triage_decision = relationship("TriageDecision", back_populates="overrides")
    
    __table_args__ = (
        Index('idx_clinician_override', 'clinician_id', 'override_timestamp'),
    )


class AuditLog(Base):
    """
    Immutable audit trail. Every triage event is logged here.
    This table is append-only for compliance & liability.
    """
    __tablename__ = "audit_logs"
    
    log_id = Column(String(36), primary_key=True, index=True)
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), nullable=True, index=True)
    
    event_type = Column(String(50), index=True)  # e.g., "patient_intake", "triage_score", "override", "re_triage"
    event_description = Column(Text)  # Human-readable summary
    
    # Full event payload (JSON serialized)
    event_payload = Column(Text)
    
    # Security & compliance
    clinician_id = Column(String(50), nullable=True, index=True)
    clinician_name = Column(String(100), nullable=True)
    data_classification = Column(String(50), default="confidential")  # HIPAA classification
    
    event_timestamp = Column(DateTime, server_default=func.now(), index=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Immutability indicators
    is_tamper_checked = Column(Boolean, default=False)
    checksum = Column(String(64), nullable=True)  # SHA256 of event payload
    
    # Relationship
    patient = relationship("Patient", back_populates="audit_logs")
    
    __table_args__ = (
        Index('idx_event_type_timestamp', 'event_type', 'event_timestamp'),
        Index('idx_clinician_timestamp', 'clinician_id', 'event_timestamp'),
    )


def get_db():
    """Dependency injection for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database schema"""
    Base.metadata.create_all(bind=engine)
    print("✓ Database schema initialized")

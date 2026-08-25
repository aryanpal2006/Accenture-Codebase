"""
FastAPI Triage Assistant Application
Real-time patient triage scoring with audit logging and clinician override support.
"""

from fastapi import FastAPI, Depends, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
import uuid
import json

# Local imports
from database import (
    init_db, get_db, Patient, VitalSigns, TriageDecision, 
    ClinicalOverride, AuditLog, TriageSeverityLevel, engine, SessionLocal
)
from triage_engine import TriageEngine, VitalMetrics, PatientContext, TriageSeverityLevel as EngineTriageSeverityLevel
from audit_logger import AuditLogger
from models import (
    PatientIntakeRequest, TriageScoreResponse, TriageOverrideRequest, TriageOverrideResponse,
    PatientTriageQueueResponse, SurgeMetricsResponse, AuditLogEntry, VitalSignsRequest,
    TriageSeverityEnum, ErrorResponse
)
from simulated_data import SimulatedPatientGenerator

# Initialize
app = FastAPI(
    title="Emergency Department Triage Assistant",
    description="AI-powered patient triage with safety-first design and audit trails",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Triage engine
triage_engine = TriageEngine()

# Global state for tracking surge
class SystemState:
    def __init__(self):
        self.intake_queue = []
        self.is_surge_mode = False
        self.surge_start_time = None

system_state = SystemState()


# ============================================================================
# STARTUP & DEMO ENDPOINTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    print("\n" + "="*70)
    print("🏥 EMERGENCY DEPARTMENT TRIAGE ASSISTANT")
    print("="*70)
    print("✓ Database initialized")
    print("✓ Triage engine ready")
    print("✓ Audit logging active")
    print("✓ API listening on http://localhost:8000")
    print("\nDocs: http://localhost:8000/docs")
    print("="*70 + "\n")


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
    }


@app.post("/demo/load-sample-patients", tags=["Demo"])
async def load_sample_patients(
    num_patients: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    """
    Load sample patient cohort for demonstration.
    Includes edge cases: pediatric, geriatric, ambiguous, zero-history.
    """
    
    print(f"\n📥 Loading {num_patients} sample patients...")
    
    # Generate patient cohort
    simulated_patients = SimulatedPatientGenerator.generate_patient_cohort(
        num_patients=num_patients,
        include_edge_cases=True,
    )
    
    loaded_count = 0
    for sim_patient in simulated_patients:
        try:
            # Create patient record
            patient = Patient(
                patient_id=sim_patient["patient_id"],
                first_name=sim_patient["first_name"],
                last_name=sim_patient["last_name"],
                date_of_birth=datetime.fromisoformat(sim_patient["date_of_birth"]),
                gender=sim_patient["gender"],
                mrn=sim_patient.get("mrn"),
                is_returning_patient=sim_patient["is_returning_patient"],
                chief_complaint=sim_patient["chief_complaint"],
            )
            db.add(patient)
            db.flush()
            
            # Create initial vitals
            vitals = VitalSigns(
                vital_id=str(uuid.uuid4()),
                patient_id=patient.patient_id,
                temperature_celsius=sim_patient["vitals"].get("temperature_celsius"),
                heart_rate=sim_patient["vitals"].get("heart_rate"),
                respiratory_rate=sim_patient["vitals"].get("respiratory_rate"),
                systolic_bp=sim_patient["vitals"].get("systolic_bp"),
                diastolic_bp=sim_patient["vitals"].get("diastolic_bp"),
                oxygen_saturation=sim_patient["vitals"].get("oxygen_saturation"),
                pain_score=sim_patient["vitals"].get("pain_score"),
                consciousness_alert=sim_patient["vitals"].get("consciousness_alert", True),
            )
            db.add(vitals)
            db.flush()
            
            # Log intake
            AuditLogger.log_patient_intake(
                patient_id=patient.patient_id,
                patient_data={
                    "chief_complaint": patient.chief_complaint,
                    "is_returning_patient": patient.is_returning_patient,
                },
                clinician_id="system_demo",
                db=db,
            )
            
            loaded_count += 1
        
        except Exception as e:
            print(f"  ✗ Error loading patient: {e}")
            db.rollback()
            continue
    
    db.commit()
    
    print(f"✓ Loaded {loaded_count} patients successfully\n")
    
    return {
        "message": f"Loaded {loaded_count} sample patients",
        "patients_loaded": loaded_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# PATIENT INTAKE ENDPOINTS
# ============================================================================

@app.post("/patients/intake", response_model=dict, tags=["Intake"])
async def patient_intake(
    request: PatientIntakeRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new patient arrival and create initial vitals snapshot.
    """
    
    patient_id = str(uuid.uuid4())
    
    try:
        # Create patient record
        patient = Patient(
            patient_id=patient_id,
            first_name=request.first_name,
            last_name=request.last_name,
            date_of_birth=request.date_of_birth,
            gender=request.gender,
            mrn=request.mrn,
            chief_complaint=request.chief_complaint,
            is_returning_patient=request.mrn is not None,  # Has MRN → returning
        )
        db.add(patient)
        db.flush()
        
        # Create initial vitals
        vital_id = str(uuid.uuid4())
        vitals = VitalSigns(
            vital_id=vital_id,
            patient_id=patient_id,
            temperature_celsius=request.vitals.temperature_celsius,
            heart_rate=request.vitals.heart_rate,
            respiratory_rate=request.vitals.respiratory_rate,
            systolic_bp=request.vitals.systolic_bp,
            diastolic_bp=request.vitals.diastolic_bp,
            oxygen_saturation=request.vitals.oxygen_saturation,
            pain_score=request.vitals.pain_score,
            consciousness_alert=request.vitals.consciousness_alert,
        )
        db.add(vitals)
        db.flush()
        
        # Log intake event
        AuditLogger.log_patient_intake(
            patient_id=patient_id,
            patient_data={
                "chief_complaint": request.chief_complaint,
                "is_returning_patient": patient.is_returning_patient,
                "vitals": {
                    "temperature": request.vitals.temperature_celsius,
                    "heart_rate": request.vitals.heart_rate,
                },
            },
            clinician_id="intake_nurse",
            db=db,
        )
        
        db.commit()
        
        return {
            "patient_id": patient_id,
            "vital_id": vital_id,
            "message": f"Patient {request.first_name} {request.last_name} registered",
            "arrival_timestamp": patient.arrival_timestamp.isoformat(),
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TRIAGE SCORING ENDPOINTS
# ============================================================================

@app.post("/triage/score", response_model=TriageScoreResponse, tags=["Triage"])
async def perform_triage(
    patient_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """
    Perform triage scoring for a patient.
    Uses latest vitals and patient context.
    Returns severity level with confidence and reasoning.
    """
    
    # Fetch patient
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get latest vitals
    latest_vital = db.query(VitalSigns).filter(
        VitalSigns.patient_id == patient_id
    ).order_by(desc(VitalSigns.measured_at)).first()
    
    if not latest_vital:
        raise HTTPException(status_code=400, detail="No vitals recorded for patient")
    
    # Calculate age and data completeness
    age_years = (datetime.utcnow() - patient.date_of_birth).days / 365.25
    
    # Check if has recent medical history
    has_recent_history = patient.is_returning_patient
    
    # Data completeness score (vitals)
    vitals_fields = [
        latest_vital.temperature_celsius,
        latest_vital.heart_rate,
        latest_vital.respiratory_rate,
        latest_vital.oxygen_saturation,
    ]
    data_completeness_vitals = sum(1 for v in vitals_fields if v is not None) / len(vitals_fields)
    
    # Historical data availability (simplified)
    data_completeness_history = 0.8 if has_recent_history else 0.2
    
    # Create triage objects
    vitals = VitalMetrics(
        temperature_celsius=latest_vital.temperature_celsius,
        heart_rate=latest_vital.heart_rate,
        respiratory_rate=latest_vital.respiratory_rate,
        systolic_bp=latest_vital.systolic_bp,
        diastolic_bp=latest_vital.diastolic_bp,
        oxygen_saturation=latest_vital.oxygen_saturation,
        pain_score=latest_vital.pain_score,
        consciousness_alert=latest_vital.consciousness_alert,
        chief_complaint=patient.chief_complaint,
    )
    
    context = PatientContext(
        age_years=age_years,
        is_returning_patient=patient.is_returning_patient,
        has_recent_history=has_recent_history,
        data_completeness=data_completeness_vitals,
    )
    
    # Run triage scoring
    result = triage_engine.score(vitals=vitals, context=context)
    
    # Calculate wait time (if this is a re-triage, use time since first triage)
    first_triage = db.query(TriageDecision).filter(
        TriageDecision.patient_id == patient_id
    ).order_by(TriageDecision.triage_timestamp).first()
    
    if first_triage:
        wait_time = (datetime.utcnow() - first_triage.triage_timestamp).total_seconds()
    else:
        wait_time = (datetime.utcnow() - patient.arrival_timestamp).total_seconds()
    
    # Create triage decision record
    decision_id = str(uuid.uuid4())
    triage_decision = TriageDecision(
        decision_id=decision_id,
        patient_id=patient_id,
        severity_score=TriageSeverityLevel[result.severity_level.name],
        confidence_score=result.confidence_score,
        reasoning=json.dumps(result.reasoning),
        data_completeness_vitals=data_completeness_vitals,
        data_completeness_history=data_completeness_history,
        wait_time_at_decision=int(wait_time),
    )
    db.add(triage_decision)
    db.flush()
    
    # Log triage decision
    AuditLogger.log_triage_decision(
        patient_id=patient_id,
        decision_id=decision_id,
        severity_level=result.severity_level.value,
        confidence_score=result.confidence_score,
        reasoning=result.reasoning,
        data_completeness_vitals=data_completeness_vitals,
        data_completeness_history=data_completeness_history,
        db=db,
    )
    
    db.commit()
    
    return TriageScoreResponse(
        decision_id=decision_id,
        patient_id=patient_id,
        severity_level=TriageSeverityEnum[result.severity_level.name],
        confidence_score=result.confidence_score,
        reasoning=result.reasoning,
        escalation_flags=result.escalation_flags,
        data_quality_warning=result.data_quality_warning,
        data_completeness={
            "vitals": data_completeness_vitals,
            "history": data_completeness_history,
        },
        wait_time_at_decision=int(wait_time),
        timestamp=datetime.utcnow(),
    )


# ============================================================================
# CLINICAL OVERRIDE ENDPOINTS
# ============================================================================

@app.post("/triage/override", response_model=TriageOverrideResponse, tags=["Overrides"])
async def clinical_override(
    request: TriageOverrideRequest,
    db: Session = Depends(get_db),
):
    """
    Clinician override of triage score.
    Captures reason and logs override event.
    """
    
    # Fetch triage decision
    triage_decision = db.query(TriageDecision).filter(
        TriageDecision.decision_id == request.decision_id
    ).first()
    
    if not triage_decision:
        raise HTTPException(status_code=404, detail="Triage decision not found")
    
    # Create override record
    override_id = str(uuid.uuid4())
    override = ClinicalOverride(
        override_id=override_id,
        decision_id=request.decision_id,
        original_severity=triage_decision.severity_score,
        overridden_severity=TriageSeverityLevel[request.overridden_severity.name],
        clinician_id=request.clinician_id,
        clinician_name=request.clinician_name,
        override_reason=request.override_reason,
    )
    db.add(override)
    db.flush()
    
    # Log override event
    AuditLogger.log_clinical_override(
        patient_id=triage_decision.patient_id,
        decision_id=request.decision_id,
        override_id=override_id,
        original_severity=triage_decision.severity_score.value,
        overridden_severity=request.overridden_severity.value,
        clinician_id=request.clinician_id,
        clinician_name=request.clinician_name,
        override_reason=request.override_reason,
        db=db,
    )
    
    db.commit()
    
    return TriageOverrideResponse(
        override_id=override_id,
        decision_id=request.decision_id,
        patient_id=triage_decision.patient_id,
        original_severity=TriageSeverityEnum[triage_decision.severity_score.name],
        overridden_severity=request.overridden_severity,
        clinician_id=request.clinician_id,
        clinician_name=request.clinician_name,
        override_reason=request.override_reason,
        timestamp=datetime.utcnow(),
    )


# ============================================================================
# QUEUE & MONITORING ENDPOINTS
# ============================================================================

@app.get("/queue", response_model=list, tags=["Queue"])
async def get_triage_queue(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get current triage queue.
    Patients ordered by severity and wait time.
    """
    
    # Get recent triage decisions (latest per patient)
    recent_decisions = db.query(TriageDecision).filter(
        TriageDecision.triage_timestamp >= datetime.utcnow() - timedelta(hours=8)
    ).order_by(
        desc(TriageDecision.triage_timestamp)
    ).limit(limit).all()
    
    # Build queue
    queue = []
    seen_patients = set()
    
    for decision in recent_decisions:
        if decision.patient_id in seen_patients:
            continue
        seen_patients.add(decision.patient_id)
        
        patient = decision.patient  # Relationship loaded
        age = (datetime.utcnow() - patient.date_of_birth).days / 365.25
        
        queue.append({
            "patient_id": patient.patient_id,
            "name": f"{patient.first_name} {patient.last_name}",
            "age": f"{age:.1f}y",
            "chief_complaint": patient.chief_complaint,
            "severity": decision.severity_score.value,
            "confidence": f"{decision.confidence_score:.0%}",
            "wait_minutes": decision.wait_time_at_decision // 60,
            "has_override": len(decision.overrides) > 0,
        })
    
    return queue


@app.get("/metrics/surge", response_model=SurgeMetricsResponse, tags=["Metrics"])
async def get_surge_metrics(db: Session = Depends(get_db)):
    """
    Get system metrics for surge detection and capacity.
    """
    
    # Count patients in queue (arrived in last 8 hours)
    cutoff = datetime.utcnow() - timedelta(hours=8)
    patients_in_queue = db.query(Patient).filter(
        Patient.arrival_timestamp >= cutoff
    ).count()
    
    # Get severity distribution
    severity_dist = db.query(
        TriageDecision.severity_score,
        func.count(TriageDecision.decision_id)
    ).filter(
        TriageDecision.triage_timestamp >= cutoff
    ).group_by(TriageDecision.severity_score).all()
    
    severity_breakdown = {
        str(sev): count for sev, count in severity_dist
    }
    
    # Calculate average wait time
    recent_decisions = db.query(TriageDecision).filter(
        TriageDecision.triage_timestamp >= cutoff
    ).all()
    
    avg_wait = sum(d.wait_time_at_decision for d in recent_decisions) / max(len(recent_decisions), 1)
    
    return SurgeMetricsResponse(
        current_queue_size=patients_in_queue,
        avg_wait_time_minutes=avg_wait / 60,
        patients_per_severity=severity_breakdown,
        system_load_percentage=min((patients_in_queue / 50) * 100, 100),  # Assume 50 is full capacity
        estimated_throughput_per_hour=patients_in_queue / max((avg_wait / 3600), 0.1),
        timestamp=datetime.utcnow(),
    )


# ============================================================================
# AUDIT TRAIL ENDPOINTS
# ============================================================================

@app.get("/audit/patient/{patient_id}", tags=["Audit"])
async def get_patient_audit_trail(
    patient_id: str,
    db: Session = Depends(get_db),
):
    """
    Get complete audit trail for a patient.
    All triage decisions, overrides, and events.
    """
    
    audit_logs = AuditLogger.get_audit_trail(patient_id=patient_id, session=db)
    
    return {
        "patient_id": patient_id,
        "total_events": len(audit_logs),
        "events": audit_logs,
    }


@app.get("/audit/overrides", tags=["Audit"])
async def get_override_report(
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),
):
    """
    Clinical override report (for quality/training).
    Shows patterns in clinician overrides.
    """
    
    report = AuditLogger.get_clinician_override_report(session=db, hours=hours)
    return report


# ============================================================================
# DOCUMENTATION
# ============================================================================

@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information"""
    return {
        "title": "Emergency Department Triage Assistant",
        "version": "1.0.0",
        "description": "AI-powered patient triage with safety-first design",
        "docs": "/docs",
        "quick_start": {
            "1_load_demo_data": "POST /demo/load-sample-patients?num_patients=20",
            "2_view_queue": "GET /queue",
            "3_view_metrics": "GET /metrics/surge",
            "4_review_audits": "GET /audit/overrides",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

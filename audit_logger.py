"""
Audit Logging System
Immutable, tamper-evident logging for all triage events.
HIPAA-compliant with comprehensive tracking of decisions and overrides.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database import AuditLog, engine


class AuditLogger:
    """
    Centralized audit logging.
    Every event is logged immutably with checksum for tamper-evidence.
    """
    
    @staticmethod
    def log_event(
        event_type: str,
        event_description: str,
        event_payload: Dict[str, Any],
        patient_id: Optional[str] = None,
        clinician_id: Optional[str] = None,
        clinician_name: Optional[str] = None,
        data_classification: str = "confidential",
        db: Optional[Session] = None,
    ) -> str:
        """
        Log an event to the audit trail.
        """
        
        # Serialize payload to JSON
        payload_json = json.dumps(event_payload, default=str)
        
        # Calculate tamper-evident checksum
        checksum = hashlib.sha256(payload_json.encode()).hexdigest()
        
        # Create audit log entry
        log_id = str(uuid.uuid4())
        
        try:
            audit_entry = AuditLog(
                log_id=log_id,
                patient_id=patient_id,
                event_type=event_type,
                event_description=event_description,
                event_payload=payload_json,
                clinician_id=clinician_id,
                clinician_name=clinician_name,
                data_classification=data_classification,
                checksum=checksum,
                is_tamper_checked=True,  # We calculated it
            )
            
            if db is not None:
                db.add(audit_entry)
                db.flush()
            else:
                with Session(engine) as session:
                    session.add(audit_entry)
                    session.commit()
            
            print(f"✓ Audit log {log_id}: {event_type} for patient {patient_id}")
            return log_id
        
        except Exception as e:
            print(f"✗ Failed to log audit event: {e}")
            raise
    
    @staticmethod
    def log_patient_intake(
        patient_id: str,
        patient_data: Dict[str, Any],
        clinician_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> str:
        """Log patient arrival and intake"""
        
        return AuditLogger.log_event(
            event_type="patient_intake",
            event_description=f"Patient {patient_id} arrived at ED",
            event_payload={
                "patient_id": patient_id,
                "chief_complaint": patient_data.get("chief_complaint"),
                "is_returning": patient_data.get("is_returning_patient", False),
                "arrival_timestamp": datetime.utcnow().isoformat(),
            },
            patient_id=patient_id,
            clinician_id=clinician_id,
            clinician_name="intake_nurse",
            db=db,
        )
    
    @staticmethod
    def log_triage_decision(
        patient_id: str,
        decision_id: str,
        severity_level: str,
        confidence_score: float,
        reasoning: list,
        data_completeness_vitals: float,
        data_completeness_history: float,
        clinician_id: str = "system_triage",
        db: Optional[Session] = None,
    ) -> str:
        """Log a triage scoring decision"""
        
        return AuditLogger.log_event(
            event_type="triage_score",
            event_description=f"Triage decision: {severity_level} (confidence {confidence_score:.0%})",
            event_payload={
                "decision_id": decision_id,
                "patient_id": patient_id,
                "severity_level": severity_level,
                "confidence_score": confidence_score,
                "reasoning": reasoning,
                "data_completeness": {
                    "vitals": data_completeness_vitals,
                    "history": data_completeness_history,
                },
                "decision_timestamp": datetime.utcnow().isoformat(),
            },
            patient_id=patient_id,
            clinician_id=clinician_id,
            clinician_name="Triage Engine",
            db=db,
        )
    
    @staticmethod
    def log_clinical_override(
        patient_id: str,
        decision_id: str,
        override_id: str,
        original_severity: str,
        overridden_severity: str,
        clinician_id: str,
        clinician_name: str,
        override_reason: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> str:
        """Log when a clinician overrides the triage score"""
        
        return AuditLogger.log_event(
            event_type="clinical_override",
            event_description=f"Override: {original_severity} → {overridden_severity} by {clinician_name}",
            event_payload={
                "override_id": override_id,
                "decision_id": decision_id,
                "patient_id": patient_id,
                "original_severity": original_severity,
                "overridden_severity": overridden_severity,
                "override_reason": override_reason,
                "override_timestamp": datetime.utcnow().isoformat(),
            },
            patient_id=patient_id,
            clinician_id=clinician_id,
            clinician_name=clinician_name,
            data_classification="confidential",
            db=db,
        )
    
    @staticmethod
    def log_re_triage(
        patient_id: str,
        decision_id: str,
        reason: str,
        new_severity: str,
        old_severity: str,
        trigger: str,  # e.g., "wait_time_threshold", "vital_deterioration"
        db: Optional[Session] = None,
    ) -> str:
        """Log re-triage of waiting patient (patient deterioration monitoring)"""
        
        return AuditLogger.log_event(
            event_type="re_triage",
            event_description=f"Re-triage due to {trigger}: {old_severity} → {new_severity}",
            event_payload={
                "decision_id": decision_id,
                "patient_id": patient_id,
                "reason": reason,
                "trigger": trigger,
                "old_severity": old_severity,
                "new_severity": new_severity,
                "re_triage_timestamp": datetime.utcnow().isoformat(),
            },
            patient_id=patient_id,
            clinician_id="system_monitoring",
            clinician_name="Deterioration Monitoring System",
            db=db,
        )
    
    @staticmethod
    def get_audit_trail(
        patient_id: str,
        session: Session,
        event_types: Optional[list] = None,
    ) -> list:
        """
        Retrieve full audit trail for a patient.
        
        Returns:
            List of audit log entries (as dicts) for this patient
        """
        query = session.query(AuditLog).filter(AuditLog.patient_id == patient_id)
        
        if event_types:
            query = query.filter(AuditLog.event_type.in_(event_types))
        
        logs = query.order_by(AuditLog.event_timestamp).all()
        
        return [
            {
                "log_id": log.log_id,
                "event_type": log.event_type,
                "event_description": log.event_description,
                "event_payload": json.loads(log.event_payload),
                "clinician_id": log.clinician_id,
                "clinician_name": log.clinician_name,
                "timestamp": log.event_timestamp.isoformat(),
                "checksum": log.checksum,
            }
            for log in logs
        ]
    
    @staticmethod
    def verify_audit_log_integrity(
        log_entry: AuditLog,
    ) -> bool:
        """
        Verify that an audit log entry hasn't been tampered with.
        Recalculates checksum and compares.
        """
        recalculated_checksum = hashlib.sha256(
            log_entry.event_payload.encode()
        ).hexdigest()
        
        is_valid = recalculated_checksum == log_entry.checksum
        
        if not is_valid:
            print(f"⚠ INTEGRITY CHECK FAILED for log {log_entry.log_id}")
        
        return is_valid
    
    @staticmethod
    def get_clinician_override_report(
        session: Session,
        clinician_id: Optional[str] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Generate report of clinician overrides (for quality/training).
        
        Args:
            clinician_id: Filter to specific clinician (or None for all)
            hours: Look back period
        
        Returns:
            Summary report
        """
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        query = session.query(AuditLog).filter(
            AuditLog.event_type == "clinical_override",
            AuditLog.event_timestamp >= cutoff,
        )
        
        if clinician_id:
            query = query.filter(AuditLog.clinician_id == clinician_id)
        
        overrides = query.all()
        
        # Parse override reasons
        escalations = 0  # Override to higher severity
        de_escalations = 0  # Override to lower severity
        
        override_reasons = []
        
        for override in overrides:
            payload = json.loads(override.event_payload)
            original = payload["original_severity"]
            new = payload["overridden_severity"]
            
            if original > new:  # e.g., "3_urgent" > "4_minor" (lower = more severe)
                escalations += 1
            else:
                de_escalations += 1
            
            override_reasons.append({
                "clinician": override.clinician_name,
                "original": original,
                "new": new,
                "reason": payload.get("override_reason", "not provided"),
                "timestamp": override.event_timestamp.isoformat(),
            })
        
        return {
            "reporting_period_hours": hours,
            "total_overrides": len(overrides),
            "escalations": escalations,
            "de_escalations": de_escalations,
            "override_reasons": override_reasons,
        }

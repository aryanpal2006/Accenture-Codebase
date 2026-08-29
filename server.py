import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from src.schemas import PatientIntake, TriageResult, NurseOverrideRequest, AuditLogEntry
from src.llm_extractor import extract_features_with_gemini
from src.model import TriageModelPipeline
from src.simulated_patients import SIMULATED_PATIENTS
from src.handoff_generator import generate_physician_handoff_summary

app = FastAPI(
    title="patientTriage Clinical AI Agent",
    description="Full-stack AI patient triage system with LLM extraction, XGBoost ESI scoring, Hard Safety Nets, SHAP explanations, and HITL nurse workflow.",
    version="2.0.0"
)

# Initialize pipeline
pipeline = TriageModelPipeline()
pipeline.train()

# In-memory storage for active session state
PATIENTS_STORE: Dict[int, Dict[str, Any]] = {}
TRIAGE_RESULTS_STORE: Dict[int, Dict[str, Any]] = {}
NURSE_DECISIONS_STORE: Dict[int, Dict[str, Any]] = {}
AUDIT_LOGS: List[Dict[str, Any]] = []

SURGE_MODE: bool = False

# Populate initial simulated patients
def _init_simulated_data():
    for p in SIMULATED_PATIENTS:
        stay_id = p["stay_id"]
        PATIENTS_STORE[stay_id] = p
        
        # Run triage for each pre-populated patient
        # Pass any available numeric pain score as a hint for LLM extraction
        pain_hint = None
        raw_pain = p.get("pain")
        if raw_pain is not None:
            try:
                pain_hint = float(raw_pain)
            except (ValueError, TypeError):
                pass
        extracted = extract_features_with_gemini(p["chiefcomplaint"], pain_score_hint=pain_hint)
        t_result = pipeline.predict_patient(
            stay_id=p["stay_id"],
            subject_id=p.get("subject_id", stay_id),
            patient_name=p["name"],
            age=p["age"],
            gender=p["gender"],
            temperature=p.get("temperature"),
            heartrate=p.get("heartrate"),
            resprate=p.get("resprate"),
            o2sat=p.get("o2sat"),
            sbp=p.get("sbp"),
            dbp=p.get("dbp"),
            chief_complaint=p["chiefcomplaint"],
            extracted_features=extracted
        )
        TRIAGE_RESULTS_STORE[stay_id] = t_result.model_dump()

_init_simulated_data()

@app.get("/api/patients")
def get_patients():
    """Returns list of patients with their current triage status and ESI score."""
    patient_list = []
    for stay_id, p in PATIENTS_STORE.items():
        res = TRIAGE_RESULTS_STORE.get(stay_id, {})
        nurse_dec = NURSE_DECISIONS_STORE.get(stay_id)
        
        final_acuity = res.get("recommended_acuity", 3)
        if nurse_dec and nurse_dec.get("was_overridden"):
            final_acuity = nurse_dec.get("final_acuity")

        item = {
            "stay_id": stay_id,
            "subject_id": p.get("subject_id"),
            "name": p.get("name"),
            "age": p.get("age"),
            "gender": p.get("gender"),
            "temperature": p.get("temperature"),
            "heartrate": p.get("heartrate"),
            "resprate": p.get("resprate"),
            "o2sat": p.get("o2sat"),
            "sbp": p.get("sbp"),
            "dbp": p.get("dbp"),
            "chiefcomplaint": p.get("chiefcomplaint"),
            "is_returning_patient": p.get("is_returning_patient", False),
            "recommended_acuity": final_acuity,
            "ai_recommended_acuity": res.get("recommended_acuity"),
            "confidence_score": res.get("confidence_score"),
            "is_low_confidence": res.get("is_low_confidence", False),
            "safety_net_triggered": res.get("safety_net_triggered", False),
            "nurse_verified": nurse_dec is not None,
            "was_overridden": nurse_dec.get("was_overridden", False) if nurse_dec else False
        }
        patient_list.append(item)

    # Sort queue: If SURGE_MODE, prioritize ESI 1 and 2 aggressively
    if SURGE_MODE:
        patient_list.sort(key=lambda x: (x["recommended_acuity"], -x.get("stay_id", 0)))
    else:
        patient_list.sort(key=lambda x: x["recommended_acuity"])

    return {
        "surge_mode": SURGE_MODE,
        "patient_count": len(patient_list),
        "patients": patient_list
    }

@app.get("/api/patient/{stay_id}")
def get_patient_detail(stay_id: int):
    """Returns full triage details for a specific patient including SHAP explanations."""
    if stay_id not in PATIENTS_STORE:
        raise HTTPException(status_code=404, detail="Patient stay_id not found")
    
    patient = PATIENTS_STORE[stay_id]
    triage = TRIAGE_RESULTS_STORE.get(stay_id)
    nurse_dec = NURSE_DECISIONS_STORE.get(stay_id)

    return {
        "patient": patient,
        "triage_result": triage,
        "nurse_decision": nurse_dec
    }

PATIENT_HISTORY_LOG = []

@app.post("/api/clear-history")
def clear_patient_history():
    """Clears all patient records, audit logs, and history for a fresh shift slate."""
    PATIENTS_STORE.clear()
    TRIAGE_RESULTS_STORE.clear()
    NURSE_DECISIONS_STORE.clear()
    AUDIT_LOGS.clear()
    PATIENT_HISTORY_LOG.clear()
    return {
        "status": "success",
        "message": "Patient queue and history cleared successfully."
    }

@app.post("/api/triage")
def perform_triage(intake: PatientIntake):
    """Processes new patient intake or updates existing patient triage, automatically appending to history."""
    stay_id = intake.stay_id or int(time.time() * 1000) % 100000
    subject_id = intake.subject_id or int(time.time() * 100) % 10000
    p_name = (intake.name or f"Patient #{stay_id}").strip()

    # Check for past patient visits by name to maintain chronological medical history
    past_visits = [p for p in PATIENT_HISTORY_LOG if p["name"].lower() == p_name.lower() and p["stay_id"] != stay_id]
    
    if past_visits:
        is_returning = True
        visit_num = len(past_visits) + 1
        last_visit = past_visits[-1]
        prior_history = (
            f"Returning Patient (Visit #{visit_num} this shift). "
            f"Previous Visit #{last_visit['stay_id']}: '{last_visit['chiefcomplaint'][:50]}...' "
            f"[Assigned ESI {last_visit.get('acuity', 'N/A')}]"
        )
    else:
        is_returning = intake.is_returning_patient
        prior_history = intake.prior_medical_history or "First-Time Arrival (New Intake Recorded)"

    patient_dict = {
        "stay_id": stay_id,
        "subject_id": subject_id,
        "name": p_name,
        "age": intake.age or 45,
        "gender": intake.gender or "Unspecified",
        "temperature": intake.temperature,
        "heartrate": intake.heartrate,
        "resprate": intake.resprate,
        "o2sat": intake.o2sat,
        "sbp": intake.sbp,
        "dbp": intake.dbp,
        "chiefcomplaint": intake.chiefcomplaint,
        "is_returning_patient": is_returning,
        "prior_medical_history": prior_history
    }
    PATIENTS_STORE[stay_id] = patient_dict

    # Step 1: Gemini LLM Feature Extraction (no pain hint at inference — LLM infers from language)
    extracted = extract_features_with_gemini(intake.chiefcomplaint)

    # Step 2: XGBoost Acuity Prediction + Safety Net + SHAP
    t_result = pipeline.predict_patient(
        stay_id=stay_id,
        subject_id=subject_id,
        patient_name=patient_dict["name"],
        age=patient_dict["age"],
        gender=patient_dict["gender"],
        temperature=intake.temperature,
        heartrate=intake.heartrate,
        resprate=intake.resprate,
        o2sat=intake.o2sat,
        sbp=intake.sbp,
        dbp=intake.dbp,
        chief_complaint=intake.chiefcomplaint,
        extracted_features=extracted
    )

    t_dict = t_result.model_dump()
    TRIAGE_RESULTS_STORE[stay_id] = t_dict

    # Append to chronological shift history log
    PATIENT_HISTORY_LOG.append({
        "stay_id": stay_id,
        "subject_id": subject_id,
        "name": p_name,
        "age": patient_dict["age"],
        "gender": patient_dict["gender"],
        "chiefcomplaint": intake.chiefcomplaint,
        "acuity": t_result.recommended_acuity,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return {
        "status": "success",
        "stay_id": stay_id,
        "triage_result": t_dict
    }

@app.post("/api/override")
def nurse_override(req: NurseOverrideRequest):
    """Captures nurse approval or ESI override decision with audit trail logging."""
    stay_id = req.stay_id
    if stay_id not in TRIAGE_RESULTS_STORE:
        raise HTTPException(status_code=404, detail="Patient stay_id not found")

    t_result = TRIAGE_RESULTS_STORE[stay_id]
    ai_acuity = t_result["recommended_acuity"]
    was_overridden = (req.nurse_acuity != ai_acuity)

    decision_info = {
        "stay_id": stay_id,
        "ai_acuity": ai_acuity,
        "final_acuity": req.nurse_acuity,
        "was_overridden": was_overridden,
        "override_reason": req.override_reason if was_overridden else "Approved AI recommendation without changes",
        "nurse_name": req.nurse_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    NURSE_DECISIONS_STORE[stay_id] = decision_info

    # Log entry
    log_entry = AuditLogEntry(
        timestamp=decision_info["timestamp"],
        stay_id=stay_id,
        patient_name=t_result.get("patient_name", f"Patient #{stay_id}"),
        ai_acuity=ai_acuity,
        final_acuity=req.nurse_acuity,
        was_overridden=was_overridden,
        override_reason=decision_info["override_reason"],
        nurse_name=req.nurse_name
    ).model_dump()
    
    AUDIT_LOGS.insert(0, log_entry)

    return {
        "status": "recorded",
        "decision": decision_info
    }

@app.get("/api/handoff/{stay_id}")
def get_physician_handoff(stay_id: int):
    """Generates structured physician handoff text and structured EMR chart data."""
    if stay_id not in TRIAGE_RESULTS_STORE:
        raise HTTPException(status_code=404, detail="Patient stay_id not found")

    t_result = TRIAGE_RESULTS_STORE[stay_id]
    nurse_info = NURSE_DECISIONS_STORE.get(stay_id)
    patient_info = PATIENTS_STORE.get(stay_id, {})

    summary_text = generate_physician_handoff_summary(t_result, nurse_info)
    return JSONResponse(content={
        "summary_text": summary_text,
        "triage_result": t_result,
        "nurse_info": nurse_info,
        "patient_info": patient_info
    })

@app.get("/api/audit_logs")
def get_audit_logs():
    """Returns audit log history of nurse reviews and overrides."""
    return {"audit_logs": AUDIT_LOGS}

@app.post("/api/surge")
def toggle_surge(req: Dict[str, Any] = Body(...)):
    """Toggles Surge Mode (3x patient volume simulation)."""
    global SURGE_MODE
    SURGE_MODE = bool(req.get("surge_mode", not SURGE_MODE))
    return {
        "status": "updated",
        "surge_mode": SURGE_MODE,
        "message": "ED Surge Mode ACTIVE: Queue re-prioritized for high-acuity priority triage." if SURGE_MODE else "Normal Operation Mode restored."
    }

# Serve static frontend files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>patientTriage Backend Active</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

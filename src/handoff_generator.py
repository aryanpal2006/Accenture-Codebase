from typing import Dict, Any, Optional
from datetime import datetime

def generate_physician_handoff_summary(
    triage_result: Dict[str, Any],
    nurse_override_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates a structured clinical physician handoff summary conforming to Stage 7 of the Tech Spec.
    """
    patient_name = triage_result.get("patient_name", "Unknown Patient")
    stay_id = triage_result.get("stay_id", "N/A")
    age = triage_result.get("age", "N/A")
    gender = triage_result.get("gender", "N/A")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    vitals = triage_result.get("vitals_summary", {})
    temp_str = f"{vitals.get('temperature')} °F" if vitals.get('temperature') else "UNRECORDED ⚠️"
    hr_str = f"{vitals.get('heartrate')} bpm" if vitals.get('heartrate') else "UNRECORDED ⚠️"
    rr_str = f"{vitals.get('resprate')} /min" if vitals.get('resprate') else "UNRECORDED ⚠️"
    o2_str = f"{vitals.get('o2sat')} %" if vitals.get('o2sat') else "UNRECORDED ⚠️"
    bp_str = f"{vitals.get('sbp')}/{vitals.get('dbp')} mmHg" if vitals.get('sbp') else "UNRECORDED ⚠️"
    pain_str = f"{vitals.get('pain')}/10" if vitals.get('pain') else "Unassessed"

    extracted = triage_result.get("extracted_features", {})
    raw_cc = triage_result.get("chief_complaint_raw", "")
    
    ai_acuity = triage_result.get("recommended_acuity", 3)
    acuity_label = triage_result.get("acuity_label", f"ESI {ai_acuity}")
    confidence = triage_result.get("confidence_score", 0.0)
    low_conf_flag = " [⚠️ LOW CONFIDENCE WARNING]" if triage_result.get("is_low_confidence") else ""

    safety_net = triage_result.get("safety_net_triggered", False)
    safety_reason = triage_result.get("safety_net_reason", "None")

    reasoning_list = triage_result.get("plain_language_reasoning", [])
    reasoning_bullets = "\n".join([f"  - {r}" for r in reasoning_list]) if reasoning_list else "  - Standard clinical presentation."

    # Nurse Decision
    if nurse_override_info and nurse_override_info.get("was_overridden"):
        final_acuity = nurse_override_info.get("final_acuity")
        nurse_note = f"OVERRIDDEN BY NURSE: Assigned ESI {final_acuity}. Rationale: {nurse_override_info.get('override_reason')}"
    elif nurse_override_info:
        final_acuity = ai_acuity
        nurse_note = f"APPROVED BY NURSE ({nurse_override_info.get('nurse_name', 'RN')}): Verified AI recommendation ESI {final_acuity}."
    else:
        final_acuity = ai_acuity
        nurse_note = f"PENDING NURSE VERIFICATION (Recommended ESI {ai_acuity})"

    # Care Routing Recommendation based on ESI
    routing_map = {
        1: "IMMEDIATE RESUSCITATION BAY (Level 1 Emergency)",
        2: "ACUTE CRITICAL CARE BED (Priority 1 Nurse Ratio)",
        3: "URGENT ED TREATMENT BAY (Full Diagnostic Workup)",
        4: "FAST TRACK CLINIC (Focused single-resource evaluation)",
        5: "TRIAGE EXPRESS / OUTPATIENT CLINIC"
    }
    recommended_routing = routing_map.get(final_acuity, "STANDARD ED BAY")

    summary = f"""================================================================================
                    EMERGENCY DEPARTMENT PHYSICIAN HANDOFF SUMMARY
================================================================================
PATIENT DEMOGRAPHICS & INGESTION
- Patient Name: {patient_name} (Stay ID: {stay_id})
- Age / Gender: {age} y/o {gender}
- Intake Timestamp: {timestamp}

CHIEF COMPLAINT (Ambient Voice Transcript)
"{raw_cc.strip()}"

LLM FEATURE EXTRACTION (Gemini Clinical NLP)
- Primary Symptom Category: {extracted.get('primary_symptom_category', 'general').upper()} | Secondary: {extracted.get('secondary_symptom_category', 'none').upper()}
- Symptom Onset Timing: {extracted.get('symptom_onset', 'subacute').upper()} | Red Flag Language: {'YES ⚠️' if extracted.get('red_flag_phrase') or extracted.get('is_high_risk_phrase') else 'No'}
- Inferred Pain Severity: {f"{extracted.get('llm_pain_score')}/10" if extracted.get('llm_pain_score') is not None else 'Unspecified'}
- Organ Flags: Cardiac={'YES' if extracted.get('is_cardiac') else 'No'} | Neuro={'YES' if extracted.get('is_neurological') else 'No'} | Resp={'YES' if extracted.get('is_respiratory') else 'No'} | Trauma={'YES' if extracted.get('is_trauma') else 'No'}

VITALS AT INTAKE
- Temperature: {temp_str} | Heart Rate: {hr_str}
- Resp Rate: {rr_str} | SpO2: {o2_str}
- Blood Pressure: {bp_str} | Reported Pain: {pain_str}

AI TRIAGE RECOMMENDATION & SHAP EXPLANATION
- Recommended Acuity: {acuity_label}{low_conf_flag}
- Model Confidence Score: {confidence * 100:.1f}%
- Hard Safety Net Status: {'TRIGGERED ⚠️ (' + str(safety_reason) + ')' if safety_net else 'Passed (No critical vitals breach)'}
- Key Clinical Explanations (SHAP Attribution):
{reasoning_bullets}

HUMAN-IN-THE-LOOP (HITL) NURSE DECISION & AUDIT LOG
- Status: {nurse_note}

RECOMMENDED CLINICAL ROUTING
>> {recommended_routing}
================================================================================
"""
    return summary

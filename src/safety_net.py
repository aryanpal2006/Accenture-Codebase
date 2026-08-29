"""
Age-Stratified Clinical Safety Net Rules
Sources:
  - ACEP ESI v4 Algorithm Handbook (2012, reaffirmed 2020)
  - PALS 2020 Guidelines (American Heart Association)
  - AHA ACLS 2022 Guidelines
  - AGS/ACEP 2023 Geriatric ED Guidelines
  - ATLS 10th Edition Shock Classification
  - Sepsis-3 / NEWS2 Framework (qSOFA)
"""
from typing import Tuple, Optional, List
from src.schemas import ComplaintFeatures


# ── Age Group Classification ────────────────────────────────────────────────
def _age_group(age: Optional[int]) -> str:
    """Returns standardized age group string from patient age (years)."""
    if age is None:
        return "adult"
    if age < 1:
        return "infant"
    if age < 3:
        return "toddler"
    if age < 12:
        return "child"
    if age < 18:
        return "adolescent"
    if age >= 65:
        return "geriatric"
    return "adult"


# ── Age-Stratified ESI-1 Critical Thresholds ────────────────────────────────
# Sources: PALS 2020 Table 1, AHA 2022 ACLS, ACEP ESI v4 App B
_CRITICAL_THRESHOLDS = {
    #         HR_low  HR_high  RR_low  RR_high  SBP_shock  SpO2_crit
    "infant":      (80,    180,    20,     60,      60,       90),
    "toddler":     (70,    160,    15,     45,      70,       90),
    "child":       (60,    140,    10,     35,      75,       90),
    "adolescent":  (50,    130,    10,     30,      80,       90),
    "adult":       (40,    150,     8,     35,      80,       88),
    "geriatric":   (45,    130,    10,     30,      90,       92),  # AGS/ACEP 2023: lower tolerance
}

# ── Age-Stratified ESI-2 Warning Thresholds ──────────────────────────────────
# Tachycardia / bradycardia warning band (below ESI-1 but still urgent)
_WARNING_THRESHOLDS = {
    #         HR_tachy_warn  HR_brady_warn  SpO2_warn  SBP_hypo_warn  SBP_htn_crit  RR_tachy_warn  Temp_high
    "infant":      (160,          90,           92,         65,            160,           50,          100.4),
    "toddler":     (140,          80,           92,         75,            160,           38,          100.4),
    "child":       (120,          70,           92,         80,            170,           30,          101.0),
    "adolescent":  (110,          60,           92,         85,            180,           25,          101.5),
    "adult":       (130,          45,           91,         90,            200,           30,          103.0),
    "geriatric":   (110,          50,           94,         95,            190,           25,          100.4),  # Lower thresholds: AGS 2023
}


def _sepsis_screen(
    age_grp: str,
    heartrate: Optional[float],
    resprate: Optional[float],
    temperature: Optional[float],
    sbp: Optional[float],
    o2sat: Optional[float],
    raw_lower: str
) -> Tuple[bool, List[str], str]:
    """
    Detailed qSOFA / Sepsis-3 screening tool.
    Source: Third International Consensus Definitions for Sepsis (Singer et al., JAMA 2016;315(8):801-810).
    Evaluates: Suspected infection + ≥2 physiological dysfunctions (Tachypnea, Hypotension, Fever/Hypothermia, Tachycardia).
    """
    infection_keywords = [
        "fever", "infection", "sepsis", "neutropenia", "bacteremia",
        "pyelonephritis", "pneumonia", "cellulitis", "uti", "meningitis",
        "chills", "rigors", "abscess", "purulent", "cough", "dysuria"
    ]
    matched_sources = [kw for kw in infection_keywords if kw in raw_lower]
    if not matched_sources:
        return (False, [], "")

    breaches = []
    if resprate is not None and resprate >= 22:
        breaches.append(f"Tachypnea (RR={resprate}/min ≥ 22)")
    if sbp is not None and sbp <= 100:
        breaches.append(f"Hypotension (SBP={sbp} mmHg ≤ 100)")
    if temperature is not None and (temperature > 100.4 or temperature < 96.8):
        breaches.append(f"Thermoregulation breach (Temp={temperature}°F)")
    if heartrate is not None and heartrate > 90:
        breaches.append(f"Systemic tachycardia (HR={heartrate} bpm > 90)")

    is_pos = len(breaches) >= 2
    return (is_pos, breaches, ", ".join(matched_sources))


def _acs_screen(heartrate: Optional[float], age: Optional[int], raw_lower: str) -> bool:
    """
    ACS (Acute Coronary Syndrome) screen.
    Source: ACC/AHA 2022 Chest Pain Guideline.
    """
    if age is None or age < 30:
        return False
    acs_keywords = [
        "crushing", "squeezing", "pressure", "tightness", "jaw pain",
        "arm pain", "diaphoresis", "sweating", "nstemi", "stemi", "angina",
        "substernal", "radiation to"
    ]
    chest_keywords = ["chest pain", "cp", "chest"]
    has_chest = any(kw in raw_lower for kw in chest_keywords)
    has_acs_descriptor = any(kw in raw_lower for kw in acs_keywords)
    return has_chest and has_acs_descriptor and age >= 35


def _stroke_screen(sbp: Optional[float], age: Optional[int], raw_lower: str) -> bool:
    """
    FAST+ criteria stroke screen (Face-Arm-Speech-Time + gaze/vision).
    Source: AHA/ASA 2019 Stroke Guidelines.
    """
    if age is None or age < 18:
        return False
    stroke_keywords = [
        "facial droop", "face droop", "arm weakness", "slurred speech",
        "speech difficulty", "sudden weakness", "sudden numbness",
        "vision loss", "gaze deviation", "aphasia", "hemiplegia",
        "cva", "stroke", "tia", "sah", "head bleed", "sdh"
    ]
    return any(kw in raw_lower for kw in stroke_keywords)


def _trauma_alert(
    heartrate: Optional[float],
    sbp: Optional[float],
    age_grp: str,
    raw_lower: str
) -> bool:
    """
    Trauma alert criteria.
    Source: ATLS 10th Edition Table 3-1 (Class III/IV Hemorrhagic Shock).
    """
    trauma_keywords = [
        "mvc", "motor vehicle", "car vs pole", "gsw", "gunshot", "stab",
        "fall from height", "fall down stairs", "ejected", "pedestrian",
        "motorcycle", "trauma", "head injury", "flail chest"
    ]
    has_major_trauma = any(kw in raw_lower for kw in trauma_keywords)
    if not has_major_trauma:
        return False
    crit = _CRITICAL_THRESHOLDS.get(age_grp, _CRITICAL_THRESHOLDS["adult"])
    shock_sbp = crit[4]
    if sbp is not None and sbp < shock_sbp:
        return True
    if heartrate is not None and heartrate > 120:
        return True
    return False


def evaluate_safety_net(
    temperature: Optional[float],
    heartrate: Optional[float],
    resprate: Optional[float],
    o2sat: Optional[float],
    sbp: Optional[float],
    dbp: Optional[float],
    extracted_features: ComplaintFeatures,
    raw_complaint: str,
    age: Optional[int] = None,  # ← NEW: patient age for stratification
) -> Tuple[Optional[int], Optional[str]]:
    """
    Age-stratified hard clinical safety net.
    Sources: ACEP ESI v4, PALS 2020, AHA ACLS 2022, AGS/ACEP 2023 Geriatric ED,
             ATLS 10th Ed., Sepsis-3 / NEWS2, ACC/AHA 2022 Chest Pain Guideline.
    Returns: (override_acuity, trigger_reason) or (None, None) if no breach.
    """
    raw_lower = raw_complaint.lower()
    grp = _age_group(age)

    # Retrieve thresholds for this age group
    crit = _CRITICAL_THRESHOLDS[grp]
    hr_low, hr_high, rr_low, rr_high, sbp_shock, spo2_crit = crit
    warn = _WARNING_THRESHOLDS[grp]
    hr_tachy_w, hr_brady_w, spo2_warn, sbp_hypo_w, sbp_htn, rr_tachy_w, temp_high = warn

    # ═══════════════════════════════════════════════════════════════════════════
    # LEVEL 1 — ESI 1 CRITICAL / RESUSCITATION SAFETY NET
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. Cardiopulmonary Arrest / Airway Emergency
    if any(term in raw_lower for term in [
        "cardiac arrest", "resp arrest", "respiratory arrest", "s/p arrest",
        "unresponsive", "intubated", "ett", "pulseless", "agonal"
    ]):
        return (1, "CRITICAL [ESI-1]: Cardiopulmonary arrest / airway emergency — immediate resuscitation.")

    # 2. Critical Hypoxia (age-stratified) — PALS 2020 + AHA ACLS 2022
    if o2sat is not None and o2sat < spo2_crit:
        return (1, f"CRITICAL [ESI-1]: Severe hypoxia for {grp} (SpO2={o2sat}% < {spo2_crit}%). PALS/AHA threshold.")

    # 3. Extreme Hyperpyrexia (Temp >= 105.0°F / 40.5°C) — Critical Thermoregulatory Emergency
    if temperature is not None and temperature >= 105.0:
        return (1, f"CRITICAL [ESI-1]: Extreme Hyperpyrexia (Temp={temperature}°F ≥ 105.0°F). Critical thermoregulatory failure / heat stroke / central fever risk requiring immediate emergency resuscitation & cooling protocol.")

    # 4. Profound Shock — ATLS Class III/IV (age-stratified SBP)
    if sbp is not None and sbp < sbp_shock:
        return (1, f"CRITICAL [ESI-1]: Profound hypotensive shock for {grp} (SBP={sbp} mmHg < {sbp_shock} mmHg). ATLS.")

    # 5. Critical Respiratory Failure (age-stratified RR)
    if resprate is not None and (resprate > rr_high or resprate < rr_low):
        return (1, f"CRITICAL [ESI-1]: Respiratory failure for {grp} (RR={resprate}/min, normal {rr_low}–{rr_high}). PALS.")

    # 6. Life-Threatening Dysrhythmia (age-stratified HR)
    if heartrate is not None and (heartrate > hr_high or heartrate < hr_low):
        return (1, f"CRITICAL [ESI-1]: Life-threatening dysrhythmia for {grp} (HR={heartrate} bpm, range {hr_low}–{hr_high}). AHA.")

    # 7. Stroke Protocol Active — AHA/ASA 2019 (ESI-1 if within stroke window)
    if _stroke_screen(sbp, age, raw_lower):
        # Hypertensive urgency often accompanies acute stroke
        if sbp is not None and sbp >= 160:
            return (1, f"CRITICAL [ESI-1]: Active stroke presentation (FAST+) with hypertension (SBP={sbp}). AHA/ASA 2019.")
        return (2, "EMERGENCY [ESI-2]: Stroke protocol activated — FAST criteria met. AHA/ASA 2019.")

    # 8. Trauma Alert (ATLS Class III/IV shock + major mechanism)
    if _trauma_alert(heartrate, sbp, grp, raw_lower):
        return (1, f"CRITICAL [ESI-1]: Major trauma with hemodynamic instability ({grp}). ATLS 10th Ed.")

    # ═══════════════════════════════════════════════════════════════════════════
    # LEVEL 2 — ESI 2 EMERGENT / HIGH-RISK SAFETY NET
    # ═══════════════════════════════════════════════════════════════════════════

    # 9. Moderate Hypoxia Warning (age-stratified)
    if o2sat is not None and spo2_crit <= o2sat < spo2_warn:
        return (2, f"EMERGENCY [ESI-2]: Hypoxia requiring urgent O2 for {grp} (SpO2={o2sat}%). ACEP ESI v4.")

    # 10. Hypertensive Emergency — ACC/AHA 2018 (age-stratified)
    if sbp is not None and sbp > sbp_htn:
        return (2, f"EMERGENCY [ESI-2]: Hypertensive urgency for {grp} (SBP={sbp} mmHg > {sbp_htn}). ACC/AHA.")

    # 11. Hypotensive Warning Band
    if sbp is not None and sbp_shock <= sbp < sbp_hypo_w:
        return (2, f"EMERGENCY [ESI-2]: Hypotension warning for {grp} (SBP={sbp} mmHg). ATLS/ACEP.")

    # 12. Severe Tachycardia / Bradycardia Warning (age-stratified)
    if heartrate is not None and heartrate >= hr_tachy_w:
        return (2, f"EMERGENCY [ESI-2]: Tachycardia for {grp} (HR={heartrate} bpm ≥ {hr_tachy_w}). PALS/AHA.")
    if heartrate is not None and hr_low <= heartrate < hr_brady_w:
        return (2, f"EMERGENCY [ESI-2]: Bradycardia warning for {grp} (HR={heartrate} bpm). PALS/AHA.")

    # 13. Temperature Extremes & Severe Hyperthermia (age-stratified)
    if temperature is not None and temperature < 95.0:
        return (2, f"EMERGENCY [ESI-2]: Severe hypothermia (Temp={temperature}°F < 95.0°F). Systemic exposure / shock risk. AHA ACLS 2022.")
    if temperature is not None and temperature >= 103.0:
        return (2, f"EMERGENCY [ESI-2]: Severe Hyperthermia / High Fever (Temp={temperature}°F ≥ 103.0°F). High risk of sepsis, central neuro-fever, or severe systemic inflammatory syndrome. ACEP ESI v4.")
    if temperature is not None and temperature > temp_high:
        if grp in ["infant", "toddler", "geriatric"]:
            return (2, f"EMERGENCY [ESI-2]: High-risk fever in vulnerable group ({grp}) (Temp={temperature}°F > {temp_high}°F). AGS/ACEP 2023 / PALS 2020.")
        if any(kw in raw_lower for kw in ["neutropenia", "fever", "infection", "sepsis", "chemo", "chills", "rigors"]):
            return (2, f"EMERGENCY [ESI-2]: High-risk fever in infection context (Temp={temperature}°F > {temp_high}°F). ACEP ESI v4.")
        if temperature >= 101.5:
            return (2, f"EMERGENCY [ESI-2]: Elevated core temperature (Temp={temperature}°F ≥ 101.5°F). Requires urgent infectious and metabolic evaluation.")

    # 13. Sepsis Screen — Sepsis-3 / JAMA 2016 (Singer et al.)
    is_septic, sepsis_breaches, inf_src = _sepsis_screen(grp, heartrate, resprate, temperature, sbp, o2sat, raw_lower)
    if is_septic:
        breach_desc = "; ".join(sepsis_breaches)
        return (2, (
            f"EMERGENCY [ESI-2]: Sepsis-3 Protocol Triggered (JAMA 2016 — Singer et al.). "
            f"Active Infection Focus: '{inf_src.upper()}'. "
            f"Physiological Dysfunctions: {breach_desc}. "
            f"Clinical Problem: High probability of acute organ dysfunction & rapid progression to septic shock. "
            f"Immediate Protocol: STAT blood cultures x2, serum lactate, IV broad-spectrum antibiotics within 1h, and 30 mL/kg IV crystalloid fluid bolus."
        ))

    # 14. ACS Protocol — ACC/AHA 2022 Chest Pain Guideline
    if _acs_screen(heartrate, age, raw_lower):
        return (2, "EMERGENCY [ESI-2]: ACS protocol — chest pain with high-risk descriptors, age ≥ 35. ACC/AHA 2022.")

    # 15. High-Risk Narrative Red Flags (ACEP ESI v4 App B)
    red_flag_terms = [
        "head bleed", "aortic dissection", "leaking ascites", "vomiting blood",
        "coffee ground emesis", "dka", "facial droop", "sdh", "sah",
        "hemoptysis", "melena", "ruptured", "evisceration"
    ]
    for term in red_flag_terms:
        if term in raw_lower:
            return (2, f"EMERGENCY [ESI-2]: High-risk clinical red flag '{term}' detected. ACEP ESI v4 Appendix B.")

    # 16. Geriatric-Specific: Altered Mental Status at any vital (AGS 2023)
    if grp == "geriatric":
        ams_keywords = ["confused", "confusion", "altered", "disoriented", "agitated", "unsteady"]
        if any(kw in raw_lower for kw in ams_keywords):
            return (2, "EMERGENCY [ESI-2]: Altered mental status in geriatric patient — high-risk presentation. AGS/ACEP 2023.")

    return (None, None)

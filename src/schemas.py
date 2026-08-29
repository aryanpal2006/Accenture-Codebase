from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Minimal symptom category classes (10 categories, 0-indexed encoded)
SYMPTOM_CATEGORY_MAP = {
    "cardiac": 0,
    "bleeding": 1,
    "consciousness": 2,
    "respiratory": 3,
    "trauma": 4,
    "neurological": 5,
    "gastrointestinal": 6,
    "psychiatric": 7,
    "infectious": 8,
    "general": 9
}

# Symptom onset encoding
SYMPTOM_ONSET_MAP = {
    "acute": 0,       # < 2 hours
    "subacute": 1,    # 2–12 hours
    "delayed": 2,     # 12 hours – 3 days
    "chronic": 3      # > 3 days
}

class ComplaintFeatures(BaseModel):
    """Structured clinical features extracted from unstructured chief complaint narrative using LLM."""
    pain_severity: Optional[float] = Field(
        default=None,
        description="Extracted numeric pain scale from 0 to 10. Null if unknown/not mentioned."
    )
    is_cardiac: bool = Field(
        default=False,
        description="True if patient reports chest pain, pressure, jaw/arm radiation, palpitations, or cardiac history."
    )
    is_neurological: bool = Field(
        default=False,
        description="True if patient presents with facial droop, sudden numbness/weakness, seizure, stroke (CVA), SAH/SDH, or altered mental status."
    )
    is_respiratory: bool = Field(
        default=False,
        description="True if patient reports shortness of breath (SOB), dyspnea, hypoxia, wheezing, respiratory arrest, or intubation."
    )
    is_trauma: bool = Field(
        default=False,
        description="True if mechanism includes motor vehicle crash (MVC), fall, head injury, fracture, or assault."
    )
    is_psychiatric: bool = Field(
        default=False,
        description="True if patient presents with suicidal ideation (SI), psychiatric hold, depression, or hallucinations."
    )
    is_gastrointestinal: bool = Field(
        default=False,
        description="True if patient presents with GI bleeding, hematemesis, coffee ground emesis, BRBPR, severe abdominal pain, or ascites."
    )
    is_high_risk_phrase: bool = Field(
        default=False,
        description="Safety over-flagging mechanism: True if complaint contains critical red-flag terms like 'crushing pain', 'facial droop', 'leaking ascites', 's/p arrest', 'head bleed', 'neutropenic fever', 'aortic dissection', or 'vomiting blood'."
    )
    primary_symptom_category: str = Field(
        default="general",
        description="One of: cardiac, bleeding, consciousness, respiratory, trauma, neurological, gastrointestinal, psychiatric, infectious, general."
    )
    is_hindi_script: bool = Field(
        default=False,
        description="True if chief complaint narrative is in Hindi script / Devanagari."
    )
    summary_narrative: str = Field(
        default="",
        description="A concise 1-sentence clinical synthesis of the chief complaint."
    )

    # ── NEW: 4 LLM-derived XGBoost feature columns ────────────────────────────

    llm_pain_score: Optional[float] = Field(
        default=None,
        description=(
            "LLM-inferred pain score (0–10) synthesised from complaint language and the "
            "provided numeric pain score hint. May differ slightly from the raw numeric reading "
            "to account for language tone (e.g. 'writhing' escalates, 'mild ache' de-escalates)."
        )
    )
    symptom_category_encoded: int = Field(
        default=9,
        description=(
            "Integer label encoding of primary_symptom_category. "
            "cardiac=0, bleeding=1, consciousness=2, respiratory=3, trauma=4, "
            "neurological=5, gastrointestinal=6, psychiatric=7, infectious=8, general=9."
        )
    )
    red_flag_phrase: int = Field(
        default=0,
        description=(
            "Binary flag (0 or 1). 1 if the overall complaint tone or specific language implies "
            "a potentially life-threatening situation requiring immediate escalation."
        )
    )
    symptom_onset: str = Field(
        default="subacute",
        description=(
            "Categorical onset timing inferred from complaint. "
            "One of: acute (< 2 h), subacute (2–12 h), delayed (12 h – 3 days), chronic (> 3 days)."
        )
    )
    symptom_onset_encoded: int = Field(
        default=1,
        description=(
            "Integer encoding of symptom_onset. "
            "acute=0, subacute=1, delayed=2, chronic=3."
        )
    )
    secondary_symptom_category: str = Field(
        default="none",
        description="Secondary symptom category if multiple symptom clusters exist, or 'none'."
    )
    secondary_symptom_category_encoded: int = Field(
        default=10,
        description=(
            "Integer label encoding of secondary_symptom_category. "
            "cardiac=0, bleeding=1, consciousness=2, respiratory=3, trauma=4, "
            "neurological=5, gastrointestinal=6, psychiatric=7, infectious=8, general=9, none=10."
        )
    )


class PatientIntake(BaseModel):
    subject_id: Optional[int] = None
    stay_id: Optional[int] = None
    name: Optional[str] = "Anonymous Patient"
    age: Optional[int] = 45
    gender: Optional[str] = "Unspecified"
    temperature: Optional[float] = None
    heartrate: Optional[float] = None
    resprate: Optional[float] = None
    o2sat: Optional[float] = None
    sbp: Optional[float] = None
    dbp: Optional[float] = None
    chiefcomplaint: str
    is_returning_patient: bool = False
    prior_medical_history: Optional[str] = None


class ShapFeatureImpact(BaseModel):
    feature_name: str
    feature_value: Any
    shap_value: float
    direction: str  # "escalates_acuity" or "reduces_acuity"
    explanation: str


class TriageResult(BaseModel):
    stay_id: int
    subject_id: Optional[int] = None
    patient_name: str
    age: int
    gender: str
    vitals_summary: Dict[str, Any]
    chief_complaint_raw: str
    extracted_features: ComplaintFeatures
    recommended_acuity: int  # ESI 1 (highest urgency) to 5 (lowest urgency)
    acuity_label: str
    confidence_score: float  # 0.0 to 1.0
    is_low_confidence: bool
    xgb_acuity_probabilities: Dict[int, float]
    safety_net_triggered: bool
    safety_net_reason: Optional[str] = None
    shap_explanations: List[ShapFeatureImpact]
    plain_language_reasoning: List[str]


class NurseOverrideRequest(BaseModel):
    stay_id: int
    nurse_acuity: int
    override_reason: str
    nurse_name: str = "Triage Nurse RN"


class AuditLogEntry(BaseModel):
    timestamp: str
    stay_id: int
    patient_name: str
    ai_acuity: int
    final_acuity: int
    was_overridden: bool
    override_reason: Optional[str] = None
    nurse_name: str

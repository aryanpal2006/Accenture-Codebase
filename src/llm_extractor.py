import os
import re
import json
import random
from typing import Optional
from src.schemas import ComplaintFeatures, SYMPTOM_CATEGORY_MAP, SYMPTOM_ONSET_MAP

# High-risk terms for safety over-flagging mechanism as specified in Accenture Tech Spec
HIGH_RISK_KEYWORDS = [
    "crushing pain", "facial droop", "leaking ascites", "s/p arrest", "cardiac arrest",
    "head bleed", "neutropenia", "neutropenic fever", "aortic dissection", "vomiting blood",
    "hematemesis", "brbpr", "coffee ground emesis", "dka", "intubated", "resp arrest",
    "hypotension", "hypoxia", "nstemi", "cva", "stroke", "seizure", "unresponsive",
    "car vs pole", "head injury", "lethargic", "elevated inr", "mvc", "s/p fall",
    "altered mental status", "respiratory arrest", "picc eval", "sdh", "sah",
    "hyperpyrexia", "106", "105", "104", "high fever"
]

# Bleeding indicators for the new 'bleeding' symptom category
BLEEDING_KEYWORDS = [
    "hematemesis", "coffee ground emesis", "brbpr", "blood in stool", "bloody stool",
    "hematuria", "vaginal bleeding", "heavy bleeding", "head bleed", "leaking ascites",
    "bleeding", "hemorrhage", "blood"
]

# Consciousness / altered mental status keywords
CONSCIOUSNESS_KEYWORDS = [
    "altered mental status", "ams", "confusion", "unresponsive", "lethargic", "stupor",
    "unconscious", "s/p arrest", "syncope", "presyncope", "collapse", "passed out",
    "near syncope"
]

# Infectious / sepsis / mild viral keywords
INFECTIOUS_KEYWORDS = [
    "fever", "neutropenia", "neutropenic fever", "sepsis", "uti", "cellulitis",
    "pneumonia", "infection", "infected", "pyelonephritis", "bacteremia", "chills",
    "night sweats", "elevated wbc", "hyperpyrexia", "high fever", "cough", "sneezing",
    "sore throat", "cold", "runny nose", "congestion"
]

# Acute onset indicators (< 2 h)
ACUTE_ONSET_KEYWORDS = [
    "sudden", "suddenly", "acute", "minutes ago", "just started", "just now",
    "onset", "abrupt", "s/p", "new onset", "immediately", "immediately after",
    "this morning", "this hour", "arrest", "mvc", "trauma", "fell"
]

# Subacute onset (2–12 h)
SUBACUTE_ONSET_KEYWORDS = [
    "few hours", "hours ago", "several hours", "this afternoon", "tonight",
    "this evening", "started today", "a few hours"
]

# Delayed onset (12 h – 3 days)
DELAYED_ONSET_KEYWORDS = [
    "yesterday", "since yesterday", "last night", "a day ago", "two days",
    "couple of days", "2 days", "3 days"
]

# Chronic / prolonged onset (> 3 days)
CHRONIC_ONSET_KEYWORDS = [
    "weeks", "months", "chronic", "long-standing", "ongoing", "persistent",
    "for a week", "for weeks", "recurring", "recurrent", "years", "long term"
]


def extract_features_with_gemini(
    chief_complaint: str,
    pain_score_hint: Optional[float] = None,
    api_key: Optional[str] = None
) -> ComplaintFeatures:
    """
    Extract structured features from unstructured chief complaint narrative using Gemini API
    with Pydantic structured output validation. Fallback to rule-based parser if API key is
    absent or on error.

    Args:
        chief_complaint: Raw chief complaint text from the nurse/patient.
        pain_score_hint: Numeric pain score (0–10) recorded at triage, used as a hint to the LLM.
        api_key: Optional Gemini API key (falls back to GEMINI_API_KEY env variable).
    """
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', chief_complaint))
    hindi_instruction = "\nLANGUAGE RULE: The input chief complaint narrative contains Hindi/Devanagari script. Accurately translate the Hindi medical terms (e.g., 'सीने में दर्द' -> chest pain, 'सांस में तकलीफ' -> dyspnea, 'चक्कर' -> dizziness, 'उल्टी' -> vomiting) into English clinical understanding and set `is_hindi_script=true`." if has_devanagari else ""

    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if effective_api_key:
        try:
            from google import genai
            from google.genai import types

            pain_hint_text = f"\nNurse-recorded pain score (use as hint, may refine based on language): {pain_score_hint}/10" if pain_score_hint is not None else ""

            client = genai.Client(api_key=effective_api_key)
            prompt = f"""You are a clinical AI triage assistant. Parse the following patient chief complaint narrative and extract essential clinical features for downstream XGBoost Emergency Severity Index (ESI) scoring.
{hindi_instruction}

SAFETY RULE: You MUST deliberately over-flag rare, high-risk phrases (e.g. 'crushing pain', 'facial droop', 'leaking ascites', 'head bleed', 'dka', 'severe SOB') into `is_high_risk_phrase=True` to prevent dangerous under-triage.

ONSET RULES:
- acute = onset < 2 hours (sudden, s/p event, trauma, arrest)
- subacute = onset 2–12 hours (started today, few hours)
- delayed = onset 12 hours to 3 days (yesterday, couple of days)
- chronic = onset > 3 days (weeks, months, recurring)

SYMPTOM CATEGORY RULES:
- Primary Category (pick ONE best match): cardiac, bleeding, consciousness, respiratory, trauma, neurological, gastrointestinal, psychiatric, infectious, general
- Secondary Category (pick SECOND most prominent cluster if present, otherwise 'none')

For `symptom_category_encoded` use: cardiac=0, bleeding=1, consciousness=2, respiratory=3, trauma=4, neurological=5, gastrointestinal=6, psychiatric=7, infectious=8, general=9
For `secondary_symptom_category_encoded` use: cardiac=0, bleeding=1, consciousness=2, respiratory=3, trauma=4, neurological=5, gastrointestinal=6, psychiatric=7, infectious=8, general=9, none=10
For `symptom_onset_encoded` use: acute=0, subacute=1, delayed=2, chronic=3
For `llm_pain_score`: Estimate a realistic numeric pain score (0.0 to 10.0) from the complaint. If words like 'extreme body pain', 'excruciating', 'severe', 'unbearable' are present, assign 8.5–10.0. If moderate pain/aches (e.g. 'flank pain', 'body pain', 'headache'), assign 5.0–7.0. If mild, assign 2.0–3.5. Only assign 0.0 if explicitly stated no pain or zero pain descriptors.
{pain_hint_text}

Chief Complaint Narrative:
"{chief_complaint}"
"""
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComplaintFeatures,
                    temperature=0.15
                ),
            )
            if response.text:
                parsed_dict = json.loads(response.text)
                if has_devanagari:
                    parsed_dict["is_hindi_script"] = True
                return ComplaintFeatures(**parsed_dict)
        except Exception as e:
            print(f"[Gemini Extractor Notice] API call fallback due to: {e}")

    # Offline / Fallback Rule-Based Clinical NLP Extractor
    return _rule_based_extractor(chief_complaint, pain_score_hint)


def _rule_based_extractor(
    chief_complaint: str,
    pain_score_hint: Optional[float] = None
) -> ComplaintFeatures:
    """Rule-based fallback that deterministically extracts all 4 new columns."""
    text = chief_complaint.lower()

    # ── 1. Pain severity extraction ───────────────────────────────────────────
    pain_val = None
    # Explicit numeric patterns (e.g. "pain 8", "pain: 10", "8/10", "10 out of 10", "scale 7")
    pain_match = re.search(r'pain\s*(?:of|scale|level|score)?\s*:?\s*(\d{1,2})', text)
    slash_match = re.search(r'(\d{1,2})\s*/\s*10', text)
    out_of_match = re.search(r'(\d{1,2})\s*(?:out of|\/)\s*10', text)
    
    if pain_match:
        val = float(pain_match.group(1))
        if 0 <= val <= 10:
            pain_val = val
    elif slash_match:
        val = float(slash_match.group(1))
        if 0 <= val <= 10:
            pain_val = val
    elif out_of_match:
        val = float(out_of_match.group(1))
        if 0 <= val <= 10:
            pain_val = val

    # Clinical pain vocabulary lists
    extreme_pain_words = [
        "extreme", "excruciating", "unbearable", "worst", "crushing",
        "agonizing", "intense", "severe", "screaming", "writhing",
        "terrible", "horrible", "debilitating", "incapacitating",
        "unrelenting", "crippling", "killing me", "cannot tolerate"
    ]
    moderate_pain_words = [
        "moderate", "significant", "considerable", "sharp", "burning",
        "cramping", "throbbing", "aching", "body pain", "generalized pain",
        "painful", "discomfort", "hurts a lot", "bad pain", "soreness",
        "flank pain", "back pain", "chest pain", "abd pain", "abdominal pain",
        "headache", "toothache", "ear pain", "joint pain", "hurts", "hurting"
    ]
    mild_pain_words = [
        "mild", "slight", "minor", "dull", "low grade", "twinge",
        "a little pain", "nuisance", "manageable", "tolerable", "minimal"
    ]

    if pain_val is None:
        if any(w in text for w in extreme_pain_words):
            pain_val = 9.0
        elif any(w in text for w in moderate_pain_words):
            pain_val = 6.0
        elif any(w in text for w in mild_pain_words):
            pain_val = 2.5
        elif any(w in text for w in ["pain", "ache", "sore", "hurt", "hurts"]):
            pain_val = 5.0  # Unquantified pain complaint default
        elif pain_score_hint is not None:
            pain_val = pain_score_hint

    # Use hint as fallback if still None
    if pain_val is None and pain_score_hint is not None:
        pain_val = pain_score_hint

    # ── 2. Boolean clinical category flags ────────────────────────────────────
    is_cardiac = any(w in text for w in [
        "chest pain", "cp", "palpitations", "cardiac", "nstemi", "stemi", "aortic dissection",
        "jaw pain", "arm pain", "tightness", "pressure in chest", "angina"
    ])

    is_neuro = any(w in text for w in [
        "facial droop", "slurred speech", "stroke", "cva", "sah", "sdh", "head bleed",
        "seizure", "confusion", "altered mental status", "numbness", "weakness", "lethargy",
        "lethargic", "diplopia", "dizziness", "syncope", "headache", "unresponsive"
    ])

    is_resp = any(w in text for w in [
        "sob", "shortness of breath", "dyspnea", "resp arrest", "respiratory", "intubated",
        "hypoxia", "wheezing", "cannot breathe", "stridor", "asthma"
    ])

    is_trauma = any(w in text for w in [
        "mvc", "motor vehicle", "fall", "s/p fall", "head injury", "fracture", "fx",
        "car vs pole", "assault", "rib pain", "laceration", "sw", "stab", "trauma"
    ])

    is_psych = any(w in text for w in [
        "si", "suicidal", "psychiatric", "psych eval", "depression", "anxiety",
        "hallucinations", "etoh"
    ])

    is_gi = any(w in text for w in [
        "abd pain", "abdominal", "vomiting blood", "hematemesis", "coffee ground emesis",
        "brbpr", "ascites", "leaking ascites", "diarrhea", "n/v", "epigastric", "luq", "rlq"
    ])

    is_bleeding = any(w in text for w in BLEEDING_KEYWORDS)
    is_consciousness = any(w in text for w in CONSCIOUSNESS_KEYWORDS)
    is_infectious = any(w in text for w in INFECTIOUS_KEYWORDS)

    # ── High Risk Red Flag Decision ──────────────────────────────────────────
    # ONLY trigger red_flag / is_high_risk for genuine clinical emergencies.
    # Mild symptoms (e.g. sneezing, simple cough, cold, sore throat) MUST NOT be red flags.
    matched_high_risk_kw = [kw for kw in HIGH_RISK_KEYWORDS if kw in text]
    
    has_severe_cardiac = any(w in text for w in ["crushing", "stemi", "nstemi", "aortic dissection", "substernal", "jaw pain", "arm pain"])
    has_severe_neuro = any(w in text for w in ["facial droop", "slurred speech", "stroke", "cva", "sah", "sdh", "head bleed", "seizure", "unresponsive", "altered mental status"])
    has_severe_resp = any(w in text for w in ["resp arrest", "respiratory arrest", "intubated", "stridor", "cannot breathe", "gasping", "cyanosis", "flail chest", "severe sob", "severe dyspnea"])
    has_severe_bleed = any(w in text for w in ["vomiting blood", "hematemesis", "coffee ground emesis", "brbpr", "hemorrhage", "leaking ascites"])

    is_high_risk = bool(matched_high_risk_kw or has_severe_cardiac or has_severe_neuro or has_severe_resp or has_severe_bleed or is_consciousness)
    red_flag = 1 if is_high_risk else 0

    # ── 3. Primary & Secondary symptom categories ──────────────────────────────
    matched_categories = []
    if is_cardiac:
        matched_categories.append("cardiac")
    if is_bleeding:
        matched_categories.append("bleeding")
    if is_consciousness:
        matched_categories.append("consciousness")
    if is_resp:
        matched_categories.append("respiratory")
    if is_trauma:
        matched_categories.append("trauma")
    if is_neuro:
        matched_categories.append("neurological")
    if is_gi:
        matched_categories.append("gastrointestinal")
    if is_psych:
        matched_categories.append("psychiatric")
    if is_infectious:
        matched_categories.append("infectious")

    if len(matched_categories) >= 1:
        category = matched_categories[0]
    else:
        category = "general"

    if len(matched_categories) >= 2:
        sec_category = matched_categories[1]
        sec_category_encoded = SYMPTOM_CATEGORY_MAP.get(sec_category, 9)
    else:
        sec_category = "none"
        sec_category_encoded = 10

    category_encoded = SYMPTOM_CATEGORY_MAP.get(category, 9)

    # ── 5. Symptom onset (categorical) ────────────────────────────────────────
    if any(w in text for w in ACUTE_ONSET_KEYWORDS):
        onset = "acute"
    elif any(w in text for w in SUBACUTE_ONSET_KEYWORDS):
        onset = "subacute"
    elif any(w in text for w in DELAYED_ONSET_KEYWORDS):
        onset = "delayed"
    elif any(w in text for w in CHRONIC_ONSET_KEYWORDS):
        onset = "chronic"
    else:
        # Default: trauma/arrest → acute; otherwise subacute
        onset = "acute" if is_trauma or is_consciousness else "subacute"

    onset_encoded = SYMPTOM_ONSET_MAP.get(onset, 1)

    # ── 6. LLM pain score (with hint synthesis) ───────────────────────────────
    llm_pain = pain_val if pain_val is not None else 0.0
    # Tone modifiers: escalate for severe descriptors, de-escalate for mild
    if any(w in text for w in extreme_pain_words):
        llm_pain = max(llm_pain, 9.0)
    elif any(w in text for w in moderate_pain_words):
        llm_pain = max(llm_pain, 6.0)
    elif any(w in text for w in mild_pain_words):
        llm_pain = min(llm_pain, 3.5) if llm_pain > 0 else 2.5
    elif any(w in text for w in ["pain", "ache", "hurt", "sore"]):
        llm_pain = max(llm_pain, 5.0)

    # Generate explicit clinical explanation for red flag trigger
    red_flag_reason_str = ""
    if red_flag == 1 or is_high_risk:
        matched_kw = [kw for kw in HIGH_RISK_KEYWORDS if kw in text]
        flag_details = []
        if matched_kw:
            flag_details.append(f"High-risk terms detected: '{', '.join(matched_kw)}'")
        if is_cardiac:
            flag_details.append("Cardiac Ischemia / Acute Coronary Syndrome indicators")
        if is_neuro:
            flag_details.append("Acute Stroke / Neurological deficit features")
        if is_resp:
            flag_details.append("Airway compromise / Respiratory distress risk")
        if is_bleeding:
            flag_details.append("Hemorrhage / Gastrointestinal bleeding indicators")
        if is_consciousness:
            flag_details.append("Altered mental status / Syncope alert")
        
        detail_text = " | ".join(flag_details) if flag_details else "Critical symptom severity pattern detected"
        red_flag_reason_str = f"🚩 Red Flag Warning ({detail_text}): High probability of life-threatening organ dysfunction requiring immediate emergency clinician evaluation."

    has_devanagari = bool(re.search(r'[\u0900-\u097F]', chief_complaint))

    return ComplaintFeatures(
        pain_severity=pain_val,
        is_cardiac=is_cardiac,
        is_neurological=is_neuro,
        is_respiratory=is_resp,
        is_trauma=is_trauma,
        is_psychiatric=is_psych,
        is_gastrointestinal=is_gi,
        is_high_risk_phrase=is_high_risk,
        primary_symptom_category=category,
        is_hindi_script=has_devanagari,
        summary_narrative=f"Patient presenting with {chief_complaint.strip()} (Category: {category.upper()}, Onset: {onset.upper()}).",
        # Structured XGBoost columns
        llm_pain_score=round(llm_pain, 1),
        symptom_category_encoded=category_encoded,
        secondary_symptom_category=sec_category,
        secondary_symptom_category_encoded=sec_category_encoded,
        red_flag_phrase=red_flag,
        red_flag_reason=red_flag_reason_str,
        symptom_onset=onset,
        symptom_onset_encoded=onset_encoded,
    )

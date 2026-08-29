import os
import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from typing import Dict, Any, List, Tuple
from src.schemas import ComplaintFeatures, ShapFeatureImpact, TriageResult
from src.safety_net import evaluate_safety_net

# ── Feature columns used by XGBoost ──────────────────────────────────────────
# Vitals + missingness flags
VITAL_FEATURES = [
    "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp",
    "temp_missing", "hr_missing", "rr_missing", "o2_missing", "sbp_missing", "dbp_missing",
    "is_unassessable_pain",
]
# LLM boolean binary flags (kept for SHAP signal diversity)
LLM_BOOL_FEATURES = [
    "feat_is_cardiac", "feat_is_neurological", "feat_is_respiratory",
    "feat_is_trauma", "feat_is_psychiatric", "feat_is_gastrointestinal", "feat_is_high_risk",
]
# NEW: 4 structured LLM-derived clinical columns + demographics
LLM_STRUCTURED_FEATURES = [
    "llm_pain_score",                       # 0–10 LLM inferred pain
    "symptom_category_encoded",             # 0–9 categorical symptom class
    "secondary_symptom_category_encoded",   # 0–9 secondary category, 10=none
    "red_flag_phrase",                      # 0/1 binary urgency flag
    "symptom_onset_encoded",                # 0=acute, 1=subacute, 2=delayed, 3=chronic
    "age_numeric",                          # patient age
    "gender_encoded",                       # male=0, female=1, other=2
]

FEATURE_NAMES = VITAL_FEATURES + LLM_BOOL_FEATURES + LLM_STRUCTURED_FEATURES

ESI_LABELS = {
    1: "ESI 1 - Resuscitation (Life-Threatening)",
    2: "ESI 2 - Emergent / High Risk",
    3: "ESI 3 - Urgent (Multiple Resources Needed)",
    4: "ESI 4 - Less Urgent (One Resource Needed)",
    5: "ESI 5 - Non-Urgent (No Resources Needed)"
}

GENDER_ENCODING = {"male": 0, "m": 0, "female": 1, "f": 1, "woman": 1, "man": 0}


class TriageModelPipeline:
    def __init__(self):
        self.model = None
        self.explainer = None
        self.median_vitals = {}
        self.is_trained = False

    def train(self, data_path: str = None):
        """Train 5-class XGBoost model on clinical vitals + LLM extracted complaint features."""
        if data_path is None or not os.path.exists(data_path):
            from data.generate_dataset import build_training_dataset
            df = build_training_dataset()
        else:
            df = pd.read_csv(data_path)

        # Calculate / hard-code medians for imputation during inference
        self.median_vitals = {
            "temperature": 98.6,
            "heartrate":   78.0,
            "resprate":    18.0,
            "o2sat":       98.0,
            "sbp":        120.0,
            "dbp":         75.0,
            "llm_pain_score": df["llm_pain_score"].median() if "llm_pain_score" in df.columns else 3.0,
            "age_numeric": 45.0,
        }

        # Construct feature matrix X and target y
        X = self._prepare_feature_dataframe(df)
        # Convert 1-5 ESI target to 0-4 zero-indexed classes for XGBoost
        y = (df["acuity"] - 1).clip(0, 4).astype(int)

        self.model = xgb.XGBClassifier(
            n_estimators=120,
            max_depth=5,
            learning_rate=0.08,
            objective="multi:softprob",
            num_class=5,
            random_state=42,
            eval_metric="mlogloss",
            subsample=0.85,
            colsample_bytree=0.85,
        )
        self.model.fit(X, y)

        # Initialize SHAP explainer
        self.explainer = shap.TreeExplainer(self.model)
        self.is_trained = True
        print(f"[Triage Model] XGBoost 5-Class Acuity Scorer trained on {len(df)} records "
              f"with {len(FEATURE_NAMES)} features. SHAP explainer initialized.")

    def _prepare_feature_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build the fixed-column feature DataFrame used for training and inference."""
        X = pd.DataFrame()

        # ── Vitals ────────────────────────────────────────────────────────────
        X["temperature"] = pd.to_numeric(df["temperature"], errors="coerce").fillna(self.median_vitals.get("temperature", 98.6)).astype(float)
        X["heartrate"]   = pd.to_numeric(df["heartrate"],   errors="coerce").fillna(self.median_vitals.get("heartrate",   78.0)).astype(float)
        X["resprate"]    = pd.to_numeric(df["resprate"],    errors="coerce").fillna(self.median_vitals.get("resprate",    18.0)).astype(float)
        X["o2sat"]       = pd.to_numeric(df["o2sat"],       errors="coerce").fillna(self.median_vitals.get("o2sat",       98.0)).astype(float)
        X["sbp"]         = pd.to_numeric(df["sbp"],         errors="coerce").fillna(self.median_vitals.get("sbp",        120.0)).astype(float)
        X["dbp"]         = pd.to_numeric(df["dbp"],         errors="coerce").fillna(self.median_vitals.get("dbp",         75.0)).astype(float)

        # ── Missingness flags ─────────────────────────────────────────────────
        X["temp_missing"] = df["temperature"].isna().astype(int)
        X["hr_missing"]   = df["heartrate"].isna().astype(int)
        X["rr_missing"]   = df["resprate"].isna().astype(int)
        X["o2_missing"]   = df["o2sat"].isna().astype(int)
        X["sbp_missing"]  = df["sbp"].isna().astype(int)
        X["dbp_missing"]  = df["dbp"].isna().astype(int)

        # Unassessable pain flag (intubated / unresponsive)
        pain_col = df.get("pain", pd.Series([""] * len(df)))
        X["is_unassessable_pain"] = pain_col.astype(str).str.lower().isin(
            ["ett", "ua", "unable", "critical", "uta"]
        ).astype(int)

        # ── LLM boolean binary flags ──────────────────────────────────────────
        for col in LLM_BOOL_FEATURES:
            X[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)

        # ── LLM structured features ───────────────────────────────────────────
        X["llm_pain_score"]                     = pd.to_numeric(df.get("llm_pain_score", self.median_vitals.get("llm_pain_score", 3.0)), errors="coerce").fillna(self.median_vitals.get("llm_pain_score", 3.0)).astype(float)
        X["symptom_category_encoded"]           = pd.to_numeric(df.get("symptom_category_encoded", 9), errors="coerce").fillna(9).astype(int)
        X["secondary_symptom_category_encoded"] = pd.to_numeric(df.get("secondary_symptom_category_encoded", 10), errors="coerce").fillna(10).astype(int)
        X["red_flag_phrase"]                     = pd.to_numeric(df.get("red_flag_phrase", 0), errors="coerce").fillna(0).astype(int)
        X["symptom_onset_encoded"]               = pd.to_numeric(df.get("symptom_onset_encoded", 1), errors="coerce").fillna(1).astype(int)

        # ── Demographics ──────────────────────────────────────────────────────
        age_series = pd.to_numeric(df["age"], errors="coerce") if "age" in df.columns else pd.Series([self.median_vitals.get("age_numeric", 45.0)] * len(df))
        X["age_numeric"] = age_series.fillna(self.median_vitals.get("age_numeric", 45.0)).astype(float)

        gender_series = df["gender"] if "gender" in df.columns else pd.Series(["general"] * len(df))
        X["gender_encoded"] = gender_series.astype(str).str.lower().map(
            lambda g: GENDER_ENCODING.get(g, 2)
        ).astype(int)

        return X[FEATURE_NAMES]

    def predict_patient(
        self,
        stay_id: int,
        subject_id: int,
        patient_name: str,
        age: int,
        gender: str,
        temperature: float,
        heartrate: float,
        resprate: float,
        o2sat: float,
        sbp: float,
        dbp: float,
        chief_complaint: str,
        extracted_features: ComplaintFeatures
    ) -> TriageResult:
        """Process single patient through XGBoost model + Safety Net + SHAP Explainer."""
        if not self.is_trained:
            self.train()

        # Build 1-row DataFrame for prediction
        row = {
            "temperature":    temperature,
            "heartrate":      heartrate,
            "resprate":       resprate,
            "o2sat":          o2sat,
            "sbp":            sbp,
            "dbp":            dbp,
            "pain":           None,  # no longer collected directly
            "age":            age,
            "gender":         gender,
            # Boolean LLM flags
            "feat_is_cardiac":           int(extracted_features.is_cardiac),
            "feat_is_neurological":      int(extracted_features.is_neurological),
            "feat_is_respiratory":       int(extracted_features.is_respiratory),
            "feat_is_trauma":            int(extracted_features.is_trauma),
            "feat_is_psychiatric":       int(extracted_features.is_psychiatric),
            "feat_is_gastrointestinal":  int(extracted_features.is_gastrointestinal),
            "feat_is_high_risk":         int(extracted_features.is_high_risk_phrase),
            # LLM structured columns (no augmentation at inference time)
            "llm_pain_score":                     extracted_features.llm_pain_score if extracted_features.llm_pain_score is not None else 3.0,
            "symptom_category_encoded":           extracted_features.symptom_category_encoded,
            "secondary_symptom_category_encoded": extracted_features.secondary_symptom_category_encoded,
            "red_flag_phrase":                    extracted_features.red_flag_phrase,
            "symptom_onset_encoded":              extracted_features.symptom_onset_encoded,
        }

        df_single = pd.DataFrame([row])
        X_single = self._prepare_feature_dataframe(df_single)

        # 1. XGBoost Model Inference
        probs = self.model.predict_proba(X_single)[0]
        class_probs = {i + 1: round(float(p), 4) for i, p in enumerate(probs)}

        xgb_predicted_acuity = int(np.argmax(probs) + 1)
        max_prob = float(np.max(probs))

        # Confidence calculation
        sorted_probs = sorted(probs, reverse=True)
        margin = sorted_probs[0] - sorted_probs[1]
        confidence_score = round(max_prob, 3)
        is_low_confidence = (confidence_score < 0.55 or margin < 0.15)

        # 2. Evaluate Hard Clinical Safety Net (with Age Stratification)
        safety_acuity, safety_reason = evaluate_safety_net(
            temperature, heartrate, resprate, o2sat, sbp, dbp, extracted_features, chief_complaint, age=age
        )

        final_acuity = xgb_predicted_acuity
        safety_triggered = False
        if safety_acuity is not None and safety_acuity < xgb_predicted_acuity:
            final_acuity = safety_acuity
            safety_triggered = True

        # 3. SHAP Force Value Calculation
        shap_values = self.explainer.shap_values(X_single)
        if isinstance(shap_values, list):
            target_class_shap = shap_values[xgb_predicted_acuity - 1][0]
        elif len(shap_values.shape) == 3:
            target_class_shap = shap_values[0, :, xgb_predicted_acuity - 1]
        else:
            target_class_shap = shap_values[0]

        shap_impacts = []
        plain_reasoning = []

        feature_tuples = [
            (feat_name, val, float(s_val))
            for feat_name, val, s_val in zip(FEATURE_NAMES, X_single.iloc[0].values, target_class_shap)
        ]
        feature_tuples.sort(key=lambda x: abs(x[2]), reverse=True)

        for feat_name, val, s_val in feature_tuples[:7]:
            if abs(s_val) < 0.001:
                continue
            direction = "escalates_acuity" if s_val > 0 else "reduces_acuity"
            exp_text = _generate_plain_language_shap(feat_name, val, s_val, final_acuity)
            shap_impacts.append(ShapFeatureImpact(
                feature_name=feat_name,
                feature_value=val,
                shap_value=round(s_val, 4),
                direction=direction,
                explanation=exp_text
            ))
            plain_reasoning.append(exp_text)

        if safety_triggered:
            plain_reasoning.insert(0, f"⚠️ SAFETY OVERRIDE: Escalated to ESI {final_acuity} due to {safety_reason}")

        vitals_dict = {
            "temperature": temperature,
            "heartrate":   heartrate,
            "resprate":    resprate,
            "o2sat":       o2sat,
            "sbp":         sbp,
            "dbp":         dbp,
        }

        return TriageResult(
            stay_id=stay_id,
            subject_id=subject_id,
            patient_name=patient_name,
            age=age,
            gender=gender,
            vitals_summary=vitals_dict,
            chief_complaint_raw=chief_complaint,
            extracted_features=extracted_features,
            recommended_acuity=final_acuity,
            acuity_label=ESI_LABELS.get(final_acuity, f"ESI {final_acuity}"),
            confidence_score=confidence_score,
            is_low_confidence=is_low_confidence,
            xgb_acuity_probabilities=class_probs,
            safety_net_triggered=safety_triggered,
            safety_net_reason=safety_reason,
            shap_explanations=shap_impacts,
            plain_language_reasoning=plain_reasoning
        )


CATEGORY_LABELS = {
    0: "Cardiac Presentation (Chest Pain / Arrhythmia / Ischemia)",
    1: "Active Bleeding / Hemorrhagic Risk (GI Bleed / Trauma)",
    2: "Altered Mental Status / Consciousness Deficit (Syncope / Stupor)",
    3: "Respiratory Distress / Airway Compromise (Dyspnea / Hypoxia)",
    4: "Traumatic Injury Mechanism (MVA / Fall / Fracture)",
    5: "Neurological Deficit (Stroke / FAST+ / Seizure / Weakness)",
    6: "Gastrointestinal Emergency (Acute Abdomen / Severe N/V)",
    7: "Psychiatric / Behavioral Health Crisis (Suicidal Ideation / Agitation)",
    8: "Infectious / Sepsis Risk (Fever / Immunocompromised)",
    9: "General / Non-Specific Clinical Presentation",
    10: "None (Single Symptom Cluster)"
}

ONSET_LABELS = {
    0: "Sudden Acute (< 2 hrs) — high risk of rapid clinical decompensation",
    1: "Subacute (2–12 hrs) — actively developing acute pathology",
    2: "Delayed (12 hrs – 3 days) — subacute progression",
    3: "Chronic / Prolonged (> 3 days) — non-acute baseline progression"
}


def _generate_plain_language_shap(feat_name: str, val: Any, s_val: float, acuity: int) -> str:
    # Decoded values
    try:
        val_int = int(round(float(val)))
    except (ValueError, TypeError):
        val_int = 0

    if feat_name == "symptom_category_encoded":
        cat_name = CATEGORY_LABELS.get(val_int, "General Presentation")
        return f"🫀 Primary Presentation: {cat_name}"
    elif feat_name == "secondary_symptom_category_encoded":
        if val_int == 10:
            return f"📋 Secondary Co-Morbidity: None (isolated complaint)"
        sec_name = CATEGORY_LABELS.get(val_int, "Secondary Symptom")
        return f"➕ Secondary Co-Morbidity: {sec_name}"
    elif feat_name == "symptom_onset_encoded":
        onset_text = ONSET_LABELS.get(val_int, "Subacute timeline")
        return f"⚡ Symptom Timeline: {onset_text}"
    elif feat_name == "llm_pain_score":
        pain_f = float(val) if val is not None else 0.0
        if pain_f >= 7.0:
            desc = f"Severe distress ({pain_f:.1f}/10) requiring urgent analgesia"
        elif pain_f >= 4.0:
            desc = f"Moderate pain ({pain_f:.1f}/10)"
        else:
            desc = f"Mild/minimal pain ({pain_f:.1f}/10)"
        return f"💥 Reported Pain Level: {desc}"
    elif feat_name == "red_flag_phrase":
        if val_int == 1:
            return f"🚩 Critical Narrative: High-risk red flag keywords detected in complaint narrative"
        return f"Narrative: No high-risk buzzwords detected"
    elif feat_name == "o2sat":
        return f"🫁 Oxygenation: SpO2 {val}% (PALS/AHA target ≥94%)"
    elif feat_name == "heartrate":
        return f"💓 Heart Rate: {val} bpm (AHA hemodynamics)"
    elif feat_name == "sbp":
        return f"🩸 Systolic BP: {val} mmHg (ATLS perfusion status)"
    elif feat_name == "dbp":
        return f"🩸 Diastolic BP: {val} mmHg"
    elif feat_name == "resprate":
        return f"🫁 Respiratory Rate: {val} breaths/min"
    elif feat_name == "temperature":
        return f"🌡️ Core Temperature: {val}°F"
    elif feat_name == "age_numeric":
        return f"👤 Patient Age: {int(val) if val is not None else 'N/A'} years old (age-adjusted baseline)"
    elif feat_name == "gender_encoded":
        g_name = "Male" if val_int == 0 else ("Female" if val_int == 1 else "Other")
        return f"Demographics: Biological sex ({g_name})"
    elif feat_name == "feat_is_high_risk":
        return f"⚠️ High-Risk Triage Flag: Critical symptom severity identified"
    elif feat_name == "feat_is_cardiac":
        return f"🫀 Cardiac Indicators: Chest pressure / radiation detected"
    elif feat_name == "feat_is_neurological":
        return f"🧠 Neurological Indicators: Stroke / focal deficit / seizure features present"
    elif feat_name == "feat_is_respiratory":
        return f"🫁 Respiratory Distress: Dyspnea / SOB indicators active"
    elif feat_name == "feat_is_trauma":
        return f"🚗 Trauma Mechanism: Acute injury mechanism identified"
    elif feat_name == "feat_is_psychiatric":
        return f"🧠 Psychiatric / Behavioral: Safety watch indicators active"
    elif feat_name == "feat_is_gastrointestinal":
        return f"🩺 GI / Abdominal: Acute abdominal distress / GI bleed indicators"
    elif feat_name == "is_unassessable_pain":
        return f"⚠️ Pain Assessment: Patient unable to self-report (Intubated / Critical State)"
    elif "missing" in feat_name:
        clean_v = feat_name.replace("_missing", "").upper()
        return f"ℹ️ Missing Vital Sign: {clean_v} unrecorded at triage"

    return f"Feature '{feat_name}' = {val}"

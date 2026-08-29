import pandas as pd
import numpy as np
import os
import random
from src.llm_extractor import extract_features_with_gemini

# Augmentation parameters
PAIN_NOISE_STD = 0.4   # Gaussian noise applied to llm_pain_score during training
PAIN_NOISE_CLIP = (0.0, 10.0)

def _augment_pain(base_pain: float) -> float:
    """Add light Gaussian noise to pain score for training augmentation."""
    noisy = base_pain + random.gauss(0, PAIN_NOISE_STD)
    return round(float(np.clip(noisy, *PAIN_NOISE_CLIP)), 2)


def build_training_dataset():
    csv_path = os.path.join(os.path.dirname(__file__), "triage.csv")
    df = pd.read_csv(csv_path)

    # Clean vitals
    for col in ["temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clean pain column into numeric + special text flag
    df["pain_clean"] = pd.to_numeric(df["pain"], errors="coerce")
    df["pain_special_text"] = df["pain"].astype(str).str.lower().apply(
        lambda x: x if x in ["ua", "uta", "ett", "unable", "critical"] else "none"
    )

    # Clean acuity (ensure integers 1-5)
    df["acuity"] = pd.to_numeric(df["acuity"], errors="coerce").fillna(3).astype(int)

    # Synthetic augmentation for underrepresented classes (ESI 4 and ESI 5)
    esi4_samples = [
        {"subject_id": 9001, "stay_id": 9001, "temperature": 98.6, "heartrate": 72,  "resprate": 16, "o2sat": 99,  "sbp": 120, "dbp": 78, "pain": "3",  "acuity": 4, "chiefcomplaint": "Suture removal, minor finger laceration clean"},
        {"subject_id": 9002, "stay_id": 9002, "temperature": 98.4, "heartrate": 76,  "resprate": 16, "o2sat": 99,  "sbp": 118, "dbp": 75, "pain": "2",  "acuity": 4, "chiefcomplaint": "Prescription refill for hypertension meds"},
        {"subject_id": 9003, "stay_id": 9003, "temperature": 99.0, "heartrate": 80,  "resprate": 18, "o2sat": 98,  "sbp": 122, "dbp": 80, "pain": "4",  "acuity": 4, "chiefcomplaint": "Mild sore throat, nasal congestion for 3 days"},
        {"subject_id": 9004, "stay_id": 9004, "temperature": 98.2, "heartrate": 68,  "resprate": 16, "o2sat": 100, "sbp": 115, "dbp": 72, "pain": "3",  "acuity": 4, "chiefcomplaint": "Minor ankle sprain while walking, able to bear weight"},
        {"subject_id": 9005, "stay_id": 9005, "temperature": 98.6, "heartrate": 74,  "resprate": 16, "o2sat": 99,  "sbp": 124, "dbp": 76, "pain": "2",  "acuity": 4, "chiefcomplaint": "Insect bite on arm, mild redness, no itching"},
    ]
    esi5_samples = [
        {"subject_id": 9006, "stay_id": 9006, "temperature": 98.6, "heartrate": 70,  "resprate": 16, "o2sat": 100, "sbp": 118, "dbp": 74, "pain": "0",  "acuity": 5, "chiefcomplaint": "Work physical clearance form required"},
        {"subject_id": 9007, "stay_id": 9007, "temperature": 98.4, "heartrate": 68,  "resprate": 14, "o2sat": 99,  "sbp": 116, "dbp": 72, "pain": "0",  "acuity": 5, "chiefcomplaint": "TB skin test reading, asymptomatic"},
        {"subject_id": 9008, "stay_id": 9008, "temperature": 98.6, "heartrate": 72,  "resprate": 16, "o2sat": 99,  "sbp": 120, "dbp": 78, "pain": "1",  "acuity": 5, "chiefcomplaint": "Bandage change, healing abrasion"},
        {"subject_id": 9009, "stay_id": 9009, "temperature": 98.5, "heartrate": 66,  "resprate": 15, "o2sat": 100, "sbp": 114, "dbp": 70, "pain": "0",  "acuity": 5, "chiefcomplaint": "Medical record copy request and immunization history check"},
    ]

    df_aug = pd.concat([df, pd.DataFrame(esi4_samples), pd.DataFrame(esi5_samples)], ignore_index=True)

    # Process each row – pass BOTH chief complaint and known pain score to LLM extractor
    processed_rows = []
    total = len(df_aug)
    for idx, row in df_aug.iterrows():
        cc = str(row.get("chiefcomplaint", "")).strip()

        # Extract numeric pain hint from the known pain column
        pain_hint = None
        raw_pain = row.get("pain_clean", None)
        if raw_pain is not None and not pd.isna(raw_pain):
            pain_hint = float(raw_pain)

        # Extract structured features (passes pain hint to LLM / rule-based extractor)
        feats = extract_features_with_gemini(cc, pain_score_hint=pain_hint)

        row_dict = row.to_dict()

        # Old boolean columns (kept for backwards compatibility in SHAP labels)
        row_dict["feat_is_cardiac"]        = int(feats.is_cardiac)
        row_dict["feat_is_neurological"]   = int(feats.is_neurological)
        row_dict["feat_is_respiratory"]    = int(feats.is_respiratory)
        row_dict["feat_is_trauma"]         = int(feats.is_trauma)
        row_dict["feat_is_psychiatric"]    = int(feats.is_psychiatric)
        row_dict["feat_is_gastrointestinal"] = int(feats.is_gastrointestinal)
        row_dict["feat_is_high_risk"]      = int(feats.is_high_risk_phrase)

        # ── LLM-derived XGBoost columns ────────────────────────────────
        base_pain = feats.llm_pain_score if feats.llm_pain_score is not None else 0.0
        # Apply light augmentation to pain score to improve model generalisation
        row_dict["llm_pain_score"]                     = _augment_pain(base_pain)
        row_dict["symptom_category_encoded"]           = int(feats.symptom_category_encoded)
        row_dict["secondary_symptom_category_encoded"] = int(feats.secondary_symptom_category_encoded)
        row_dict["red_flag_phrase"]                     = int(feats.red_flag_phrase)
        row_dict["symptom_onset_encoded"]               = int(feats.symptom_onset_encoded)

        processed_rows.append(row_dict)

        if (idx + 1) % 25 == 0:
            print(f"  Processed {idx + 1}/{total} rows...")

    final_df = pd.DataFrame(processed_rows)
    out_path = os.path.join(os.path.dirname(__file__), "processed_triage.csv")
    final_df.to_csv(out_path, index=False)
    print(f"\n[Dataset] Successfully built {out_path} — {len(final_df)} records, columns: {list(final_df.columns)}")
    return final_df


if __name__ == "__main__":
    build_training_dataset()

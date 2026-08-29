import os
import sys
import unittest
import pandas as pd
import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


from src.schemas import ComplaintFeatures, PatientIntake
from src.llm_extractor import extract_features_with_gemini
from src.safety_net import evaluate_safety_net
from src.model import TriageModelPipeline
from src.simulated_patients import SIMULATED_PATIENTS
from src.handoff_generator import generate_physician_handoff_summary

class TestPatientTriageSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing patientTriage Automated Test Suite ===")
        cls.pipeline = TriageModelPipeline()
        cls.pipeline.train()

    def test_01_llm_extractor_pydantic(self):
        """Test LLM Feature Extraction (Gemini Pydantic Schema / Fallback)."""
        narrative = "Patient presenting with crushing substernal chest pain radiating to left arm and diaphoresis."
        feats = extract_features_with_gemini(narrative)
        
        self.assertIsInstance(feats, ComplaintFeatures)
        self.assertTrue(feats.is_cardiac)
        self.assertTrue(feats.is_high_risk_phrase)
        self.assertEqual(feats.primary_symptom_category, "cardiac")
        print("  [PASS] Test 01: LLM Pydantic feature extractor correctly identified cardiac red flags.")

    def test_02_safety_net_overrides(self):
        """Test Independent Hard Clinical Safety Net threshold overrides."""
        feats = ComplaintFeatures(is_high_risk_phrase=True, is_respiratory=True)
        
        # Test SpO2 < 88% -> ESI 1
        acuity, reason = evaluate_safety_net(98.0, 110, 28, 85.0, 110, 70, feats, "Severe dyspnea")
        self.assertEqual(acuity, 1)
        self.assertIn("Severe hypoxia", reason)

        # Test SBP < 80 -> ESI 1
        acuity, reason = evaluate_safety_net(98.0, 120, 20, 96.0, 75.0, 45, feats, "Hypotension shock")
        self.assertEqual(acuity, 1)
        self.assertIn("hypotensive shock", reason.lower())

        # Test SpO2 90% -> ESI 2
        acuity, reason = evaluate_safety_net(98.0, 105, 22, 90.0, 110, 70, feats, "Moderate SOB")
        self.assertEqual(acuity, 2)
        print("  [PASS] Test 02: Hard Safety Net correctly overrode predictions on critical vitals.")

    def test_03_xgboost_5class_inference(self):
        """Test XGBoost 5-Class ESI model inference on simulated patient suite."""
        print("\n  Evaluating 16 Simulated Patient Cases:")
        esi_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for p in SIMULATED_PATIENTS:
            feats = extract_features_with_gemini(p["chiefcomplaint"])
            t_res = self.pipeline.predict_patient(
                stay_id=p["stay_id"],
                subject_id=p.get("subject_id", p["stay_id"]),
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
                extracted_features=feats
            )
            
            rec_acuity = t_res.recommended_acuity
            esi_counts[rec_acuity] += 1

            self.assertIn(rec_acuity, [1, 2, 3, 4, 5])
            self.assertGreater(t_res.confidence_score, 0.0)
            self.assertIsNotNone(t_res.shap_explanations)
            
            print(f"    - Patient #{p['stay_id']} ({p['name'][:30]}): ESI {rec_acuity} | Conf: {t_res.confidence_score * 100:.1f}% | SafetyNet: {t_res.safety_net_triggered}")

        print(f"  [PASS] Test 03: All 16 test cases predicted cleanly across ESI classes: {esi_counts}")

    def test_04_physician_handoff_generation(self):
        """Test Stage 7 Physician Handoff summary compilation."""
        p = SIMULATED_PATIENTS[1]  # Stroke patient
        feats = extract_features_with_gemini(p["chiefcomplaint"])
        t_res = self.pipeline.predict_patient(
            stay_id=p["stay_id"],
            subject_id=p["subject_id"],
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
            extracted_features=feats
        )
        
        summary = generate_physician_handoff_summary(t_res.model_dump(), {
            "was_overridden": False,
            "nurse_name": "Triage Nurse RN"
        })

        self.assertIn("PHYSICIAN HANDOFF SUMMARY", summary)
        self.assertIn(p["name"], summary)
        self.assertIn("RECOMMENDED CLINICAL ROUTING", summary)
        print("  [PASS] Test 04: Physician handoff report generated with complete clinical details.")

if __name__ == "__main__":
    unittest.main()

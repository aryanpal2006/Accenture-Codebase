"""
Triage Scoring Engine
Implements ESI-like 5-level severity scoring with age-aware thresholds.
Biased toward escalation (under-triage is worse than over-triage).
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple
import math


class TriageSeverityLevel(str, Enum):
    RESUSCITATION = "1_resuscitation"
    EMERGENT = "2_emergent"
    URGENT = "3_urgent"
    MINOR = "4_minor"
    FAST_TRACK = "5_fast_track"


@dataclass
class VitalMetrics:
    """Patient vital signs snapshot"""
    temperature_celsius: Optional[float] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    oxygen_saturation: Optional[float] = None
    pain_score: Optional[int] = None  # 0-10
    consciousness_alert: bool = True
    chief_complaint: str = ""


@dataclass
class PatientContext:
    """Additional clinical context"""
    age_years: float
    is_returning_patient: bool
    has_recent_history: bool  # Has prior medical records
    data_completeness: float  # 0-1, what % of expected data do we have?


@dataclass
class TriageResult:
    """Output of triage scoring"""
    severity_level: TriageSeverityLevel
    confidence_score: float  # 0-1, how certain are we?
    reasoning: List[str]  # Human-readable factors
    escalation_flags: List[str]  # Red flags that pushed toward escalation
    data_quality_warning: bool  # Do we have enough data to be confident?


class TriageThresholds:
    """
    Age-calibrated vital sign thresholds.
    Pediatric, adolescent, adult, geriatric populations have different
    normal ranges and clinical significance.
    
    References:
    - Pediatric vital signs: AAP guidelines, PALS
    - Geriatric vital signs: varies significantly; frailty complicates interpretation
    - Adult: standard EM practice
    """
    
    # Temperature thresholds (°C)
    TEMP_CRITICAL_LOW = 35.0
    TEMP_CRITICAL_HIGH = 40.0
    
    # Age-specific normal ranges and thresholds
    THRESHOLDS = {
        "pediatric": {  # 0-12 years
            "heart_rate_normal_min": 70,
            "heart_rate_normal_max": 110,
            "heart_rate_tachycardic": 130,  # Age 6-12; younger is higher
            "respiratory_rate_normal_min": 20,
            "respiratory_rate_normal_max": 30,
            "respiratory_rate_tachypneic": 40,
            "systolic_bp_normal_min": 90,  # Rough; depends on age within group
            "oxygen_sat_critical": 92,  # Lower margin for pediatric
            "temp_fever_threshold": 38.5,  # Higher for young children; fever is normal
            "temp_very_high": 39.5,
        },
        "adolescent": {  # 13-17 years
            "heart_rate_normal_min": 60,
            "heart_rate_normal_max": 100,
            "heart_rate_tachycardic": 120,
            "respiratory_rate_normal_min": 16,
            "respiratory_rate_normal_max": 20,
            "respiratory_rate_tachypneic": 30,
            "systolic_bp_normal_min": 100,
            "oxygen_sat_critical": 94,
            "temp_fever_threshold": 38.0,
            "temp_very_high": 39.0,
        },
        "adult": {  # 18-64 years
            "heart_rate_normal_min": 60,
            "heart_rate_normal_max": 100,
            "heart_rate_tachycardic": 110,
            "respiratory_rate_normal_min": 12,
            "respiratory_rate_normal_max": 20,
            "respiratory_rate_tachypneic": 25,
            "systolic_bp_normal_min": 90,
            "systolic_bp_normal_max": 140,
            "oxygen_sat_critical": 94,
            "temp_fever_threshold": 38.0,
            "temp_very_high": 39.5,
        },
        "geriatric": {  # 65+ years
            "heart_rate_normal_min": 60,
            "heart_rate_normal_max": 100,
            "heart_rate_tachycardic": 100,  # Lower threshold; less cardiac reserve
            "respiratory_rate_normal_min": 12,
            "respiratory_rate_normal_max": 20,
            "respiratory_rate_tachypneic": 24,  # Even slight elevation is concerning
            "systolic_bp_normal_min": 100,  # Often higher in elderly
            "oxygen_sat_critical": 92,  # Chronic hypoxia tolerance varies
            "temp_fever_threshold": 37.5,  # Lower threshold; blunted fever response
            "temp_very_high": 38.5,
        },
    }
    
    @staticmethod
    def get_age_group(age_years: float) -> str:
        if age_years < 13:
            return "pediatric"
        elif age_years < 18:
            return "adolescent"
        elif age_years < 65:
            return "adult"
        else:
            return "geriatric"
    
    @staticmethod
    def get_thresholds(age_years: float) -> dict:
        age_group = TriageThresholds.get_age_group(age_years)
        return TriageThresholds.THRESHOLDS[age_group]


class TriageEngine:
    """
    Core triage scoring logic.
    
    Philosophy:
    - Escalate under uncertainty (asymmetric cost: under-triage >> over-triage)
    - Confidence is explicitly modeled
    - Age-aware thresholds prevent silent failures
    - Reasoning is always explicit and queryable
    """
    
    def __init__(self):
        self.thresholds = TriageThresholds()
    
    def score(
        self,
        vitals: VitalMetrics,
        context: PatientContext,
    ) -> TriageResult:
        """
        Main triage scoring method.
        Returns severity level, confidence, reasoning, and escalation flags.
        """
        reasoning = []
        escalation_flags = []
        scores = []  # Intermediate severity scores
        
        # 1. Check for immediate life threat (RESUSCITATION)
        resus_check, resus_reason = self._check_resuscitation(vitals, context)
        if resus_check:
            return TriageResult(
                severity_level=TriageSeverityLevel.RESUSCITATION,
                confidence_score=0.99,
                reasoning=[resus_reason],
                escalation_flags=[resus_reason],
                data_quality_warning=False,
            )
        
        # 2. Data completeness assessment
        data_quality_score = self._assess_data_quality(vitals, context)
        if data_quality_score < 0.4:
            data_quality_warning = True
            reasoning.append(f"⚠ Low data quality ({data_quality_score:.0%}). Escalating under uncertainty.")
            escalation_flags.append("incomplete_data")
        else:
            data_quality_warning = False
        
        # 3. Vital signs severity scoring
        vitals_score = self._score_vitals(vitals, context)
        scores.append(vitals_score)
        reasoning.extend(self._vitals_reasoning)
        escalation_flags.extend(self._vitals_escalation_flags)
        
        # 4. Chief complaint / symptom complexity
        complaint_score = self._score_chief_complaint(vitals.chief_complaint)
        scores.append(complaint_score)
        reasoning.extend(self._complaint_reasoning)
        escalation_flags.extend(self._complaint_escalation_flags)
        
        # 5. Age-specific risk factors
        age_risk_score, age_reasoning = self._score_age_risk(context)
        scores.append(age_risk_score)
        reasoning.extend(age_reasoning)
        
        # 6. Patient history / acuity
        history_score = self._score_patient_history(context)
        scores.append(history_score)
        
        # Aggregate scores: take the MAXIMUM (bias toward escalation)
        max_score = max(scores) if scores else 3.0
        
        # Map to severity level
        severity_level = self._score_to_severity(max_score)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            max_score=max_score,
            data_quality=data_quality_score,
            scores_variance=self._calculate_variance(scores)
        )
        
        # If data is poor, reduce confidence
        if data_quality_warning:
            confidence = min(confidence, 0.65)  # Cap at 65% if data is sketchy
        
        return TriageResult(
            severity_level=severity_level,
            confidence_score=confidence,
            reasoning=reasoning,
            escalation_flags=escalation_flags,
            data_quality_warning=data_quality_warning,
        )
    
    def _check_resuscitation(
        self,
        vitals: VitalMetrics,
        context: PatientContext
    ) -> Tuple[bool, str]:
        """Check for immediate life threat"""
        
        if not vitals.consciousness_alert:
            return True, "Unresponsive patient → RESUSCITATION"
        
        if vitals.oxygen_saturation is not None and vitals.oxygen_saturation < 88:
            return True, f"Critical hypoxia (SpO2 {vitals.oxygen_saturation}%) → RESUSCITATION"
        
        if vitals.systolic_bp is not None and vitals.systolic_bp < 80:
            return True, f"Hypotensive (SBP {vitals.systolic_bp}) → RESUSCITATION"
        
        if vitals.heart_rate is not None and vitals.heart_rate > 150:
            return True, f"Severe tachycardia (HR {vitals.heart_rate}) → RESUSCITATION"
        
        if vitals.respiratory_rate is not None and vitals.respiratory_rate > 40:
            return True, f"Severe tachypnea (RR {vitals.respiratory_rate}) → RESUSCITATION"
        
        return False, ""
    
    def _assess_data_quality(
        self,
        vitals: VitalMetrics,
        context: PatientContext
    ) -> float:
        """
        Assess how complete and reliable our data is.
        Returns 0-1 score.
        """
        required_vitals = [
            vitals.temperature_celsius is not None,
            vitals.heart_rate is not None,
            vitals.respiratory_rate is not None,
            vitals.oxygen_saturation is not None,
        ]
        
        vitals_completeness = sum(required_vitals) / len(required_vitals)
        
        # Returning patients with history are more reliable
        history_bonus = 0.15 if context.has_recent_history else 0
        
        # Overall data quality
        quality_score = (vitals_completeness * 0.7) + (context.data_completeness * 0.3) + history_bonus
        return min(quality_score, 1.0)
    
    def _score_vitals(
        self,
        vitals: VitalMetrics,
        context: PatientContext
    ) -> float:
        """Score vital signs against age-specific thresholds. Returns 1-5 (higher = more severe)."""
        
        self._vitals_reasoning = []
        self._vitals_escalation_flags = []
        
        thresholds = self.thresholds.get_thresholds(context.age_years)
        severity_scores = []
        
        # Temperature
        if vitals.temperature_celsius is not None:
            temp = vitals.temperature_celsius
            if temp < self.thresholds.TEMP_CRITICAL_LOW:
                severity_scores.append(1.0)  # Hypothermia
                self._vitals_escalation_flags.append(f"Hypothermia ({temp}°C)")
            elif temp > self.thresholds.TEMP_CRITICAL_HIGH:
                severity_scores.append(1.5)  # Very high fever
                self._vitals_escalation_flags.append(f"Very high fever ({temp}°C)")
            elif temp > thresholds["temp_very_high"]:
                severity_scores.append(2.0)
                self._vitals_reasoning.append(f"High fever ({temp}°C)")
            elif temp > thresholds["temp_fever_threshold"]:
                severity_scores.append(2.5)
                self._vitals_reasoning.append(f"Fever ({temp}°C)")
            else:
                severity_scores.append(4.0)
        
        # Heart rate
        if vitals.heart_rate is not None:
            hr = vitals.heart_rate
            if hr > 150:
                severity_scores.append(1.0)  # Severe tachycardia
                self._vitals_escalation_flags.append(f"Severe tachycardia ({hr} bpm)")
            elif hr > thresholds["heart_rate_tachycardic"]:
                severity_scores.append(2.0)
                self._vitals_reasoning.append(f"Tachycardic ({hr} bpm)")
            elif hr < 50:
                severity_scores.append(2.5)  # Bradycardia
                self._vitals_escalation_flags.append(f"Bradycardia ({hr} bpm)")
            else:
                severity_scores.append(4.0)
        
        # Respiratory rate
        if vitals.respiratory_rate is not None:
            rr = vitals.respiratory_rate
            if rr > 40:
                severity_scores.append(1.0)  # Severe tachypnea
                self._vitals_escalation_flags.append(f"Severe tachypnea ({rr} bpm)")
            elif rr > thresholds["respiratory_rate_tachypneic"]:
                severity_scores.append(2.0)
                self._vitals_reasoning.append(f"Tachypneic ({rr} bpm)")
            else:
                severity_scores.append(4.0)
        
        # Oxygen saturation
        if vitals.oxygen_saturation is not None:
            sat = vitals.oxygen_saturation
            if sat < 88:
                severity_scores.append(1.0)  # Critical hypoxia
                self._vitals_escalation_flags.append(f"Critical hypoxia ({sat}%)")
            elif sat < thresholds["oxygen_sat_critical"]:
                severity_scores.append(2.0)
                self._vitals_reasoning.append(f"Low O2 sat ({sat}%)")
            else:
                severity_scores.append(4.0)
        
        # Pain score
        if vitals.pain_score is not None:
            pain = vitals.pain_score
            if pain >= 8:
                severity_scores.append(2.5)
                self._vitals_reasoning.append(f"Severe pain ({pain}/10)")
            elif pain >= 5:
                severity_scores.append(3.0)
                self._vitals_reasoning.append(f"Moderate pain ({pain}/10)")
            else:
                severity_scores.append(4.0)
        
        # Return worst (minimum) score
        return min(severity_scores) if severity_scores else 3.0
    
    def _score_chief_complaint(self, chief_complaint: str) -> float:
        """Score chief complaint severity. Higher risk complaints → lower (more severe) score."""
        
        self._complaint_reasoning = []
        self._complaint_escalation_flags = []
        
        if not chief_complaint:
            return 3.0  # Default to urgent if unknown
        
        complaint_lower = chief_complaint.lower()
        
        # Critical complaints (RESUSCITATION/EMERGENT level)
        critical_keywords = [
            "chest pain", "difficulty breathing", "unresponsive", "unconscious",
            "severe bleeding", "acute abdomen", "severe trauma", "stroke",
            "anaphylaxis", "sepsis", "shock", "seizure", "altered mental status"
        ]
        for keyword in critical_keywords:
            if keyword in complaint_lower:
                self._complaint_escalation_flags.append(f"Critical complaint: {keyword}")
                return 1.5
        
        # High-risk complaints (EMERGENT level)
        high_risk_keywords = [
            "fall", "head injury", "fever and confusion", "shortness of breath",
            "acute confusion", "dizziness with chest pain", "severe headache",
            "vomiting blood", "weakness", "severe infection"
        ]
        for keyword in high_risk_keywords:
            if keyword in complaint_lower:
                self._complaint_reasoning.append(f"High-risk complaint: {keyword}")
                return 2.0
        
        # Moderate complaints (URGENT level)
        moderate_keywords = [
            "abdominal pain", "headache", "fever", "cough", "sore throat",
            "nausea", "rash", "diarrhea", "urinary symptoms"
        ]
        for keyword in moderate_keywords:
            if keyword in complaint_lower:
                self._complaint_reasoning.append(f"Moderate complaint: {keyword}")
                return 3.0
        
        # Minor complaints (MINOR level)
        minor_keywords = [
            "minor cut", "splinter", "insect bite", "minor burn", "cold", "allergy"
        ]
        for keyword in minor_keywords:
            if keyword in complaint_lower:
                self._complaint_reasoning.append(f"Minor complaint: {keyword}")
                return 4.5
        
        # Default: URGENT
        return 3.0
    
    def _score_age_risk(self, context: PatientContext) -> Tuple[float, List[str]]:
        """Score age-specific risk factors"""
        reasoning = []
        
        if context.age_years < 2:
            reasoning.append(f"Infant/toddler ({context.age_years:.1f} y) - high monitoring risk")
            return 2.0, reasoning
        
        if context.age_years >= 80:
            reasoning.append(f"Very elderly ({context.age_years:.1f} y) - higher baseline risk")
            return 2.5, reasoning
        
        if 65 <= context.age_years < 75:
            reasoning.append(f"Older adult ({context.age_years:.1f} y) - frailty consideration")
            return 3.0, reasoning
        
        return 4.0, reasoning
    
    def _score_patient_history(self, context: PatientContext) -> float:
        """Score based on availability of patient history"""
        if context.is_returning_patient and context.has_recent_history:
            return 3.5  # Returning patients with history are more reliably triaged
        elif context.is_returning_patient:
            return 3.0  # Returning but history not available
        else:
            return 2.5  # First-time patient: escalate under uncertainty
    
    def _score_to_severity(self, score: float) -> TriageSeverityLevel:
        """Map numeric score to severity level"""
        if score < 1.5:
            return TriageSeverityLevel.RESUSCITATION
        elif score < 2.0:
            return TriageSeverityLevel.EMERGENT
        elif score < 3.5:
            return TriageSeverityLevel.URGENT
        elif score < 4.3:
            return TriageSeverityLevel.MINOR
        else:
            return TriageSeverityLevel.FAST_TRACK
    
    def _calculate_confidence(
        self,
        max_score: float,
        data_quality: float,
        scores_variance: float
    ) -> float:
        """
        Calculate confidence in the triage score.
        Factors:
        - Data quality: poor data → low confidence
        - Score variance: high variance across subscores → uncertainty
        - Score extremeness: very high/low scores → high confidence
        """
        base_confidence = data_quality  # 0-1
        
        # Reduce confidence if subscores diverge (uncertainty)
        variance_penalty = min(scores_variance * 0.2, 0.2)
        
        # Increase confidence if score is extreme (very sick or very well)
        if max_score < 2.0 or max_score > 4.5:
            base_confidence = min(base_confidence + 0.1, 1.0)
        
        confidence = base_confidence - variance_penalty
        return max(0.0, min(confidence, 1.0))
    
    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of subscores"""
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        return math.sqrt(variance)  # Return std dev

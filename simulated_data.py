"""
Simulated Patient Data Generator
Creates realistic patient scenarios for testing and demonstration.
Includes edge cases: pediatric, geriatric, ambiguous, zero-history, surge scenarios.
"""

from datetime import datetime, timedelta
import random
import uuid
from typing import List, Dict, Any


class SimulatedPatientGenerator:
    """Generate realistic test patient data"""
    
    @staticmethod
    def generate_patient_cohort(
        num_patients: int = 20,
        include_edge_cases: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Generate a cohort of simulated patients.
        
        Args:
            num_patients: Total patients to generate
            include_edge_cases: Include pediatric, geriatric, ambiguous, etc.
        
        Returns:
            List of patient dictionaries ready for intake
        """
        
        patients = []
        
        if include_edge_cases:
            # Edge case patients (specific clinical scenarios)
            patients.extend(SimulatedPatientGenerator._generate_edge_cases())
            
            # Fill remainder with realistic random cases
            remaining = num_patients - len(patients)
            patients.extend(SimulatedPatientGenerator._generate_random_patients(remaining))
        else:
            patients = SimulatedPatientGenerator._generate_random_patients(num_patients)
        
        return patients[:num_patients]
    
    @staticmethod
    def _generate_edge_cases() -> List[Dict[str, Any]]:
        """Generate specific edge case patients"""
        
        return [
            # 1. PEDIATRIC: 4-year-old with fever
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "Emma",
                "last_name": "Chen",
                "date_of_birth": (datetime.now() - timedelta(days=4*365+10)).isoformat(),
                "gender": "F",
                "mrn": None,  # First-time patient
                "is_returning_patient": False,
                "chief_complaint": "High fever and fast breathing",
                "vitals": {
                    "temperature_celsius": 39.8,
                    "heart_rate": 135,  # Elevated for age
                    "respiratory_rate": 42,  # Tachypneic
                    "systolic_bp": 105,
                    "diastolic_bp": 68,
                    "oxygen_saturation": 96.0,
                    "pain_score": None,
                    "consciousness_alert": True,
                },
                "clinical_notes": "Fever for 2 days, rapid breathing, appears uncomfortable",
            },
            
            # 2. GERIATRIC: 82-year-old with fall
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "Robert",
                "last_name": "Johnson",
                "date_of_birth": (datetime.now() - timedelta(days=82*365+30)).isoformat(),
                "gender": "M",
                "mrn": "MRN-45678",
                "is_returning_patient": True,
                "chief_complaint": "Fall at home, hit head, confusion",
                "vitals": {
                    "temperature_celsius": 36.8,
                    "heart_rate": 92,  # Mild elevation OK for elderly
                    "respiratory_rate": 18,
                    "systolic_bp": 145,  # Common in elderly
                    "diastolic_bp": 82,
                    "oxygen_saturation": 95.0,
                    "pain_score": 5,
                    "consciousness_alert": False,  # Altered mental status
                },
                "clinical_notes": "History of dementia, lives alone, possible head trauma",
            },
            
            # 3. AMBIGUOUS: Chest discomfort, unclear etiology
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "Michael",
                "last_name": "Davis",
                "date_of_birth": (datetime.now() - timedelta(days=58*365+100)).isoformat(),
                "gender": "M",
                "mrn": "MRN-23456",
                "is_returning_patient": True,
                "chief_complaint": "Mild chest discomfort, unclear onset",
                "vitals": {
                    "temperature_celsius": 37.2,
                    "heart_rate": 88,
                    "respiratory_rate": 16,
                    "systolic_bp": 138,
                    "diastolic_bp": 75,
                    "oxygen_saturation": 98.0,
                    "pain_score": 3,  # Mild
                    "consciousness_alert": True,
                },
                "clinical_notes": "Vague chest pressure, may be musculoskeletal, risk factors for CAD",
            },
            
            # 4. ZERO-HISTORY: First-time patient, limited info
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "Sarah",
                "last_name": "Unknown",
                "date_of_birth": (datetime.now() - timedelta(days=35*365+200)).isoformat(),
                "gender": "F",
                "mrn": None,
                "is_returning_patient": False,
                "chief_complaint": "Abdominal pain",
                "vitals": {
                    "temperature_celsius": 37.9,
                    "heart_rate": None,  # Couldn't get initial
                    "respiratory_rate": 19,
                    "systolic_bp": 118,
                    "diastolic_bp": 72,
                    "oxygen_saturation": None,  # Equipment unavailable
                    "pain_score": 7,
                    "consciousness_alert": True,
                },
                "clinical_notes": "Uninsured, no prior records available, speaks limited English",
            },
            
            # 5. CRITICAL: Sepsis presentation
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "John",
                "last_name": "Williams",
                "date_of_birth": (datetime.now() - timedelta(days=72*365+50)).isoformat(),
                "gender": "M",
                "mrn": "MRN-67890",
                "is_returning_patient": True,
                "chief_complaint": "Fever, confusion, rapid heartbeat",
                "vitals": {
                    "temperature_celsius": 40.2,
                    "heart_rate": 128,  # Tachycardic
                    "respiratory_rate": 28,  # Tachypneic
                    "systolic_bp": 92,  # Low (concerning)
                    "diastolic_bp": 58,
                    "oxygen_saturation": 93.0,
                    "pain_score": None,
                    "consciousness_alert": False,  # Altered mental status
                },
                "clinical_notes": "Diabetic, recent UTI, appears lethargic and confused",
            },
            
            # 6. ADOLESCENT: 15-year-old with severe asthma
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "Alex",
                "last_name": "Martinez",
                "date_of_birth": (datetime.now() - timedelta(days=15*365+200)).isoformat(),
                "gender": "M",
                "mrn": "MRN-11111",
                "is_returning_patient": True,
                "chief_complaint": "Difficulty breathing, wheezing",
                "vitals": {
                    "temperature_celsius": 37.1,
                    "heart_rate": 118,
                    "respiratory_rate": 32,
                    "systolic_bp": 132,
                    "diastolic_bp": 78,
                    "oxygen_saturation": 91.0,  # Low for adolescent
                    "pain_score": None,
                    "consciousness_alert": True,
                },
                "clinical_notes": "Known asthmatic, ran out of inhaler 2 days ago",
            },
            
            # 7. MINOR: Ankle sprain
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "Lisa",
                "last_name": "Anderson",
                "date_of_birth": (datetime.now() - timedelta(days=22*365+100)).isoformat(),
                "gender": "F",
                "mrn": None,
                "is_returning_patient": False,
                "chief_complaint": "Twisted ankle, swelling",
                "vitals": {
                    "temperature_celsius": 37.0,
                    "heart_rate": 78,
                    "respiratory_rate": 16,
                    "systolic_bp": 116,
                    "diastolic_bp": 70,
                    "oxygen_saturation": 99.0,
                    "pain_score": 4,
                    "consciousness_alert": True,
                },
                "clinical_notes": "Sport injury, happened 2 hours ago, able to walk with difficulty",
            },
            
            # 8. INFANT: 18-month-old with unknown rash
            {
                "patient_id": str(uuid.uuid4()),
                "first_name": "Lily",
                "last_name": "Brown",
                "date_of_birth": (datetime.now() - timedelta(days=18*30+15)).isoformat(),
                "gender": "F",
                "mrn": "MRN-22222",
                "is_returning_patient": True,
                "chief_complaint": "Rash all over body, fever",
                "vitals": {
                    "temperature_celsius": 38.9,
                    "heart_rate": 128,
                    "respiratory_rate": 35,
                    "systolic_bp": 95,
                    "diastolic_bp": 62,
                    "oxygen_saturation": 97.0,
                    "pain_score": None,  # Can't assess
                    "consciousness_alert": True,
                },
                "clinical_notes": "Petechial rash that doesn't blanch, inconsolable, concerned for meningitis",
            },
        ]
    
    @staticmethod
    def _generate_random_patients(num_patients: int) -> List[Dict[str, Any]]:
        """Generate random realistic patients"""
        
        common_complaints = [
            "Abdominal pain",
            "Headache",
            "Sore throat",
            "Cough",
            "Shortness of breath",
            "Chest pain",
            "Dizziness",
            "Nausea and vomiting",
            "Diarrhea",
            "Urinary symptoms",
            "Back pain",
            "Fever",
            "Weakness",
            "Confusion",
        ]
        
        first_names = ["James", "Mary", "Robert", "Patricia", "Michael", "Jennifer", "David", "Linda"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Lee"]
        
        patients = []
        
        for _ in range(num_patients):
            age = random.uniform(18, 85)
            is_returning = random.random() < 0.5
            
            # Generate realistic vitals (mostly normal with some abnormalities)
            vitals = {
                "temperature_celsius": 37.0 + random.gauss(0, 0.8),
                "heart_rate": int(75 + random.gauss(0, 10)),
                "respiratory_rate": int(18 + random.gauss(0, 3)),
                "systolic_bp": int(120 + random.gauss(0, 15)),
                "diastolic_bp": int(75 + random.gauss(0, 10)),
                "oxygen_saturation": 97.0 + random.gauss(0, 2),
                "pain_score": None if random.random() < 0.3 else int(random.uniform(1, 8)),
                "consciousness_alert": random.random() < 0.95,
            }
            
            # Clamp ranges
            vitals["temperature_celsius"] = max(35.0, min(40.5, vitals["temperature_celsius"]))
            vitals["heart_rate"] = max(40, min(180, vitals["heart_rate"]))
            vitals["respiratory_rate"] = max(8, min(50, vitals["respiratory_rate"]))
            vitals["systolic_bp"] = max(60, min(220, vitals["systolic_bp"]))
            vitals["diastolic_bp"] = max(40, min(150, vitals["diastolic_bp"]))
            vitals["oxygen_saturation"] = max(75.0, min(100.0, vitals["oxygen_saturation"]))
            
            patient = {
                "patient_id": str(uuid.uuid4()),
                "first_name": random.choice(first_names),
                "last_name": random.choice(last_names),
                "date_of_birth": (datetime.now() - timedelta(days=age*365+random.randint(0, 365))).isoformat(),
                "gender": random.choice(["M", "F"]),
                "mrn": f"MRN-{random.randint(10000, 99999)}" if is_returning else None,
                "is_returning_patient": is_returning,
                "chief_complaint": random.choice(common_complaints),
                "vitals": vitals,
            }
            
            patients.append(patient)
        
        return patients
    
    @staticmethod
    def generate_surge_scenario(
        base_arrival_rate: int = 10,
        surge_multiplier: int = 3,
        duration_minutes: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Generate a surge scenario (e.g., 3x normal volume).
        
        Args:
            base_arrival_rate: Normal arrivals per minute
            surge_multiplier: How many times normal (e.g., 3)
            duration_minutes: Length of surge
        
        Returns:
            List of patients arriving during surge
        """
        
        surge_volume = base_arrival_rate * surge_multiplier * duration_minutes
        
        print(f"\n📊 SURGE SCENARIO:")
        print(f"   Normal rate: {base_arrival_rate} patients/min")
        print(f"   Surge multiplier: {surge_multiplier}x")
        print(f"   Duration: {duration_minutes} minutes")
        print(f"   Total patients: {surge_volume}")
        
        patients = SimulatedPatientGenerator.generate_patient_cohort(
            num_patients=surge_volume,
            include_edge_cases=False,  # Mostly routine for surge
        )
        
        # Simulate staggered arrival times
        arrival_interval = 60 / (base_arrival_rate * surge_multiplier)
        
        for i, patient in enumerate(patients):
            arrival_time = datetime.now() + timedelta(minutes=i * arrival_interval)
            patient["simulated_arrival_time"] = arrival_time.isoformat()
        
        return patients


if __name__ == "__main__":
    # Test data generation
    print("🏥 Generating test patient cohort...\n")
    
    patients = SimulatedPatientGenerator.generate_patient_cohort(20, include_edge_cases=True)
    
    for i, patient in enumerate(patients, 1):
        print(f"{i}. {patient['first_name']} {patient['last_name']}")
        print(f"   Age: {(datetime.now() - datetime.fromisoformat(patient['date_of_birth'])).days / 365:.1f} years")
        print(f"   Complaint: {patient['chief_complaint']}")
        print(f"   Returning: {patient['is_returning_patient']}")
        print()

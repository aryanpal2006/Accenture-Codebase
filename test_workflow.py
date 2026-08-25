"""
Test & Demo Workflow
Demonstrates complete triage workflow with the API.

Run this after starting the server:
    python test_workflow.py
"""

import requests
import json
from datetime import datetime, timedelta
import time

BASE_URL = "http://localhost:8000"

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}\n")

def print_step(step_num, title):
    print(f"{Colors.CYAN}→ Step {step_num}: {title}{Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.ENDC}")

def print_json(data):
    print(json.dumps(data, indent=2, default=str))

def test_health():
    """Test basic connectivity"""
    print_step(0, "Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("API is healthy")
            return True
        else:
            print_error(f"API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to API. Is the server running on port 8000?")
        return False

def load_sample_patients():
    """Load sample cohort"""
    print_step(1, "Load Sample Patient Cohort")
    
    try:
        response = requests.post(
            f"{BASE_URL}/demo/load-sample-patients?num_patients=20"
        )
        response.raise_for_status()
        data = response.json()
        print_success(f"Loaded {data['patients_loaded']} patients")
        return True
    except Exception as e:
        print_error(f"Failed to load patients: {e}")
        return False

def get_queue():
    """Get current queue"""
    print_step(2, "View Triage Queue")
    
    try:
        response = requests.get(f"{BASE_URL}/queue?limit=5")
        response.raise_for_status()
        queue = response.json()
        
        print(f"Current queue (top 5):\n")
        for i, patient in enumerate(queue, 1):
            severity_color = Colors.RED if "resuscitation" in patient["severity"] else Colors.YELLOW
            print(f"  {i}. {patient['name']:<20} | Age {patient['age']:>5} | "
                  f"{severity_color}{patient['severity']:<20}{Colors.ENDC} | "
                  f"Wait: {patient['wait_minutes']} min | Confidence: {patient['confidence']}")
        
        print_success(f"Retrieved {len(queue)} patients from queue")
        return queue[0] if queue else None
    
    except Exception as e:
        print_error(f"Failed to get queue: {e}")
        return None

def show_patient_details(patient_id):
    """Show detailed audit trail for a patient"""
    print_step(3, "View Patient Audit Trail (Safety & Compliance)")
    
    try:
        response = requests.get(f"{BASE_URL}/audit/patient/{patient_id}")
        response.raise_for_status()
        audit = response.json()
        
        print(f"Patient: {patient_id}")
        print(f"Total events: {audit['total_events']}\n")
        
        for event in audit['events']:
            timestamp = event['timestamp']
            event_type = event['event_type']
            print(f"{Colors.BOLD}{event_type.upper()}{Colors.ENDC} @ {timestamp}")
            print(f"  {event['event_description']}")
            
            # Show key payload info
            payload = event['event_payload']
            if event_type == 'triage_score':
                print(f"  Severity: {payload['severity_level']} | Confidence: {payload['confidence_score']:.0%}")
                print(f"  Reasoning: {', '.join(payload['reasoning'][:2])}...")
            elif event_type == 'clinical_override':
                print(f"  Override: {payload['original_severity']} → {payload['overridden_severity']}")
                print(f"  Clinician: {event['clinician_name']}")
                if payload.get('override_reason'):
                    print(f"  Reason: {payload['override_reason']}")
            print()
        
        print_success(f"Retrieved {len(audit['events'])} audit events")
    
    except Exception as e:
        print_error(f"Failed to get audit trail: {e}")

def get_metrics():
    """Get system metrics"""
    print_step(4, "System Metrics (Surge Detection)")
    
    try:
        response = requests.get(f"{BASE_URL}/metrics/surge")
        response.raise_for_status()
        metrics = response.json()
        
        print(f"Queue Size:             {metrics['current_queue_size']} patients")
        print(f"Avg Wait Time:          {metrics['avg_wait_time_minutes']:.1f} minutes")
        print(f"System Load:            {metrics['system_load_percentage']:.1f}%")
        print(f"Estimated Throughput:   {metrics['estimated_throughput_per_hour']:.0f} patients/hour")
        print(f"\nSeverity Breakdown:")
        for severity, count in metrics['patients_per_severity'].items():
            severity_color = Colors.RED if "resuscitation" in severity else Colors.YELLOW
            print(f"  {severity_color}{severity:<25}{Colors.ENDC}: {count} patients")
        
        print_success("Retrieved system metrics")
    
    except Exception as e:
        print_error(f"Failed to get metrics: {e}")

def register_custom_patient():
    """Register a new patient with critical vitals"""
    print_step(5, "Register Custom Patient (Critical Case)")
    
    try:
        # Create a patient with chest pain (high-risk)
        patient_data = {
            "first_name": "TEST",
            "last_name": "CRITICAL",
            "date_of_birth": (datetime.now() - timedelta(days=55*365)).isoformat(),
            "gender": "M",
            "mrn": None,  # First-time patient
            "chief_complaint": "Chest pain with difficulty breathing",
            "vitals": {
                "temperature_celsius": 37.1,
                "heart_rate": 115,
                "respiratory_rate": 28,
                "systolic_bp": 135,
                "diastolic_bp": 82,
                "oxygen_saturation": 92.0,
                "pain_score": 8,
                "consciousness_alert": True
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/patients/intake",
            json=patient_data
        )
        response.raise_for_status()
        data = response.json()
        
        print_success(f"Registered patient: {data['patient_id']}")
        print(f"Vital ID: {data['vital_id']}")
        print(f"Arrival: {data['arrival_timestamp']}")
        
        return data['patient_id']
    
    except Exception as e:
        print_error(f"Failed to register patient: {e}")
        return None

def perform_triage(patient_id):
    """Perform triage on patient"""
    print_step(6, "Perform Triage Scoring")
    
    try:
        response = requests.post(
            f"{BASE_URL}/triage/score",
            json={"patient_id": patient_id}
        )
        response.raise_for_status()
        triage = response.json()
        
        print(f"Patient:           {triage['patient_id']}")
        print(f"Decision ID:       {triage['decision_id']}")
        print(f"Severity:          {Colors.RED}{triage['severity_level']}{Colors.ENDC}")
        print(f"Confidence:        {triage['confidence_score']:.0%}")
        print(f"Wait Time:         {triage['wait_time_at_decision']} seconds")
        print(f"\nData Completeness:")
        print(f"  Vitals: {triage['data_completeness']['vitals']:.0%}")
        print(f"  History: {triage['data_completeness']['history']:.0%}")
        
        if triage['data_quality_warning']:
            print(f"{Colors.YELLOW}⚠ Data quality warning!{Colors.ENDC}")
        
        print(f"\nReasoning:")
        for reason in triage['reasoning']:
            print(f"  • {reason}")
        
        if triage['escalation_flags']:
            print(f"\nEscalation Flags:")
            for flag in triage['escalation_flags']:
                print(f"  {Colors.RED}🚨 {flag}{Colors.ENDC}")
        
        print_success(f"Triage complete: {triage['severity_level']}")
        
        return triage['decision_id']
    
    except Exception as e:
        print_error(f"Failed to perform triage: {e}")
        return None

def test_clinician_override(decision_id, patient_id):
    """Test clinician override"""
    print_step(7, "Clinician Override (Safety Check)")
    
    try:
        override_data = {
            "decision_id": decision_id,
            "overridden_severity": "1_resuscitation",
            "override_reason": "Clinical judgment: EKG shows concerning changes, STEMI protocol activated",
            "clinician_id": "MD-TEST-001",
            "clinician_name": "Dr. Test Clinician"
        }
        
        response = requests.post(
            f"{BASE_URL}/triage/override",
            json=override_data
        )
        response.raise_for_status()
        override = response.json()
        
        print(f"Override ID:       {override['override_id']}")
        print(f"Original Severity: {override['original_severity']}")
        print(f"New Severity:      {Colors.RED}{override['overridden_severity']}{Colors.ENDC}")
        print(f"Clinician:         {override['clinician_name']}")
        print(f"Reason:            {override['override_reason']}")
        
        print_success("Override recorded in audit log")
        
        return override['override_id']
    
    except Exception as e:
        print_error(f"Failed to record override: {e}")
        return None

def get_override_report():
    """Get override report for quality tracking"""
    print_step(8, "Quality Report: Clinician Overrides")
    
    try:
        response = requests.get(f"{BASE_URL}/audit/overrides?hours=24")
        response.raise_for_status()
        report = response.json()
        
        print(f"Reporting Period:    {report['reporting_period_hours']} hours")
        print(f"Total Overrides:     {report['total_overrides']}")
        print(f"Escalations:         {report['escalations']}")
        print(f"De-escalations:      {report['de_escalations']}")
        
        if report['override_reasons']:
            print(f"\nRecent Overrides:")
            for override in report['override_reasons'][:3]:
                print(f"  • {override['clinician']}: {override['original']} → {override['new']}")
                print(f"    Reason: {override['reason']}")
        
        print_success("Retrieved override report")
    
    except Exception as e:
        print_error(f"Failed to get override report: {e}")

def main():
    """Run complete workflow"""
    
    print_section("🏥 EMERGENCY DEPARTMENT TRIAGE ASSISTANT - DEMO WORKFLOW")
    
    # Step 0: Health check
    if not test_health():
        print_error("\nCannot connect to API. Make sure server is running:")
        print("  docker-compose up --build")
        return
    
    time.sleep(1)
    
    # Step 1: Load patients
    if not load_sample_patients():
        return
    
    time.sleep(1)
    
    # Step 2: View queue
    first_patient = get_queue()
    
    time.sleep(1)
    
    # Step 3: Show audit trail if we have a patient
    if first_patient:
        show_patient_details(first_patient['patient_id'])
        time.sleep(1)
    
    # Step 4: Get metrics
    get_metrics()
    
    time.sleep(1)
    
    # Step 5: Register custom patient (critical case)
    new_patient_id = register_custom_patient()
    
    if new_patient_id:
        time.sleep(1)
        
        # Step 6: Perform triage
        decision_id = perform_triage(new_patient_id)
        
        if decision_id:
            time.sleep(1)
            
            # Step 7: Clinician override
            test_clinician_override(decision_id, new_patient_id)
            
            time.sleep(1)
            
            # Show updated audit trail
            show_patient_details(new_patient_id)
    
    time.sleep(1)
    
    # Step 8: Get override report
    get_override_report()
    
    # Summary
    print_section("✅ WORKFLOW COMPLETE")
    print(f"""
{Colors.GREEN}Key Capabilities Demonstrated:{Colors.ENDC}

1. ✓ Patient intake with initial vitals
2. ✓ Age-aware triage scoring (ESI 1-5)
3. ✓ Confidence quantification (0-1)
4. ✓ Safety-first escalation under uncertainty
5. ✓ Immutable audit logging with checksums
6. ✓ Clinician override with reason capture
7. ✓ Queue management and metrics
8. ✓ Quality tracking via override report

{Colors.YELLOW}For detailed documentation, see README.md{Colors.ENDC}

{Colors.BOLD}📊 API Endpoints Available:{Colors.ENDC}
- POST   /patients/intake              (Register patient)
- POST   /triage/score                 (Score patient)
- POST   /triage/override              (Clinician override)
- GET    /queue                        (View triage queue)
- GET    /metrics/surge                (System metrics)
- GET    /audit/patient/{{id}}         (Patient audit trail)
- GET    /audit/overrides              (Quality report)
- GET    /docs                         (Interactive Swagger UI)

{Colors.CYAN}Interactive API: http://localhost:8000/docs{Colors.ENDC}
    """)

if __name__ == "__main__":
    main()

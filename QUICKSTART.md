# Quick Start Guide

Get the triage system running in 5 minutes.

---

## Method 1: Docker (Recommended)

### Prerequisites
- Docker (version 20.10+)
- Docker Compose (version 1.29+)

### Steps

**1. Start Services**
```bash
docker-compose up --build
```

You should see:
```
triage_db is healthy
triage_api listening on http://localhost:8000
```

**2. In another terminal, load sample patients**
```bash
curl -X POST "http://localhost:8000/demo/load-sample-patients?num_patients=20"
```

**3. Open interactive API docs**
```bash
open http://localhost:8000/docs
```

Or visit: http://localhost:8000/docs

---

## Method 2: Local Python

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- pip

### Steps

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Set up database**

Make sure PostgreSQL is running, then:

```bash
export DATABASE_URL="postgresql://triage_user:triage_secure_pass_2024@localhost:5432/triage_db"

# Create database (in psql)
createdb triage_db

# Initialize schema
python -c "from database import init_db; init_db()"
```

**3. Start API server**
```bash
uvicorn main:app --reload --port 8000
```

**4. Load sample patients**
```bash
curl -X POST "http://localhost:8000/demo/load-sample-patients?num_patients=20"
```

**5. Open API docs**
http://localhost:8000/docs

---

## Running the Demo Workflow

Once the server is running, run the interactive demo:

```bash
python test_workflow.py
```

This will:
1. ✓ Load 20 sample patients (edge cases included)
2. ✓ Display triage queue
3. ✓ Show audit trails
4. ✓ Register a critical patient
5. ✓ Perform triage scoring
6. ✓ Demonstrate clinician override
7. ✓ Show quality metrics

**Expected output:**
```
=======================================================================
🏥 EMERGENCY DEPARTMENT TRIAGE ASSISTANT - DEMO WORKFLOW
=======================================================================

→ Step 0: Health Check
✓ API is healthy

→ Step 1: Load Sample Patient Cohort
✓ Loaded 20 patients

→ Step 2: View Triage Queue
Current queue (top 5):
  1. Emma Chen         | Age  4.0 | 2_emergent           | Wait: 1 min | Confidence: 91%
  2. Robert Johnson    | Age 82.0 | 1_resuscitation      | Wait: 1 min | Confidence: 95%
  ...
```

---

## Testing Individual Endpoints

### 1. Intake a Patient
```bash
curl -X POST "http://localhost:8000/patients/intake" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Smith",
    "date_of_birth": "1965-05-15T00:00:00",
    "gender": "M",
    "chief_complaint": "Chest pain",
    "vitals": {
      "temperature_celsius": 37.2,
      "heart_rate": 102,
      "respiratory_rate": 22,
      "systolic_bp": 145,
      "diastolic_bp": 88,
      "oxygen_saturation": 94.0,
      "pain_score": 7,
      "consciousness_alert": true
    }
  }'
```

**Save the `patient_id` from response**

### 2. Perform Triage
```bash
curl -X POST "http://localhost:8000/triage/score" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "YOUR_PATIENT_ID_HERE"}'
```

**Save the `decision_id` from response**

### 3. Override Score
```bash
curl -X POST "http://localhost:8000/triage/override" \
  -H "Content-Type: application/json" \
  -d '{
    "decision_id": "YOUR_DECISION_ID_HERE",
    "overridden_severity": "1_resuscitation",
    "override_reason": "ST elevation on EKG",
    "clinician_id": "MD-001",
    "clinician_name": "Dr. Smith"
  }'
```

### 4. View Audit Trail
```bash
curl "http://localhost:8000/audit/patient/YOUR_PATIENT_ID_HERE"
```

### 5. View Queue
```bash
curl "http://localhost:8000/queue?limit=10"
```

### 6. View Metrics
```bash
curl "http://localhost:8000/metrics/surge"
```

---

## Database Access

### Connect to PostgreSQL (Docker)

```bash
docker exec -it triage_db psql -U triage_user -d triage_db
```

### Useful Queries

**View all patients:**
```sql
SELECT patient_id, first_name, last_name, chief_complaint, arrival_timestamp 
FROM patients ORDER BY arrival_timestamp DESC;
```

**View triage decisions:**
```sql
SELECT p.first_name, p.last_name, td.severity_score, td.confidence_score, td.triage_timestamp
FROM triage_decisions td
JOIN patients p ON p.patient_id = td.patient_id
ORDER BY td.triage_timestamp DESC LIMIT 20;
```

**View clinical overrides:**
```sql
SELECT co.override_id, p.first_name, p.last_name, 
       co.original_severity, co.overridden_severity, co.clinician_name, co.override_timestamp
FROM clinical_overrides co
JOIN triage_decisions td ON td.decision_id = co.decision_id
JOIN patients p ON p.patient_id = td.patient_id
ORDER BY co.override_timestamp DESC;
```

**View audit logs:**
```sql
SELECT log_id, event_type, event_description, clinician_name, event_timestamp
FROM audit_logs
ORDER BY event_timestamp DESC LIMIT 50;
```

---

## Troubleshooting

### "Connection refused on port 5432"
Make sure PostgreSQL is running and has the correct credentials.

```bash
# Docker: Check if postgres container is healthy
docker ps
docker logs triage_db
```

### "Cannot connect to API on port 8000"
Make sure the API container is running:

```bash
docker ps
docker logs triage_api

# Or if running locally
uvicorn main:app --port 8000
```

### "Module not found" errors
Make sure you've installed all dependencies:

```bash
pip install -r requirements.txt
```

### Database already exists
```bash
docker-compose down -v  # Remove volumes
docker-compose up --build
```

---

## Understanding the Output

### Triage Severity Levels (ESI Scale)

| Level | Name | Examples |
|-------|------|----------|
| 1 | **RESUSCITATION** | Unresponsive, severe hypoxia, shock |
| 2 | **EMERGENT** | Chest pain, high fever, severe pain |
| 3 | **URGENT** | Moderate risk, stable vitals |
| 4 | **MINOR** | Minor injuries, cold, allergy |
| 5 | **FAST TRACK** | Very minor, no monitoring needed |

### Confidence Score (0-1)

- **0.9-1.0**: Very confident (good data quality, clear presentation)
- **0.7-0.9**: Confident (most vitals present)
- **0.5-0.7**: Moderate confidence (some data gaps)
- **<0.5**: Low confidence (poor data, escalate under uncertainty)

### Data Quality Warning

Appears when:
- Missing vital signs (<50% data completeness)
- First-time patient with no history
- High variance in scoring factors

**System Response:** Escalate severity, cap confidence at 65%

---

## Key Concepts

### Safety-First Bias

The system is designed to **escalate under uncertainty** rather than downgrade.

**Why?** Missing a critical patient is worse than over-triaging.

Example:
- Ambiguous chest pain + high-risk patient = EMERGENT (not URGENT)
- Fever with missing HR/RR = escalate + confidence cap

### Age-Aware Thresholds

Vital sign normal ranges differ by age:

```
Fever thresholds:
  Pediatric (0-12y):  38.5°C (fever)
  Adult (18-64y):     38.0°C (fever)
  Geriatric (65+y):   37.5°C (fever)

Heart rate thresholds:
  Pediatric (0-12y):  70-110 bpm (tachycardia >130)
  Adult (18-64y):     60-100 bpm (tachycardia >110)
  Geriatric (65+y):   60-100 bpm (tachycardia >100, lower reserve)
```

### Audit Trail

Every decision is logged immutably:
- Patient intake
- Triage scoring
- Clinician overrides (with reason)
- Patient deterioration re-triage

**Tamper-evident:** SHA256 checksum on each event

---

## Next Steps

1. **Explore the API**
   - Interactive docs: http://localhost:8000/docs
   - Try different patient scenarios

2. **Review the Code**
   - `triage_engine.py` - Scoring logic
   - `database.py` - Schema & ORM models
   - `audit_logger.py` - Compliance logging
   - `main.py` - API endpoints

3. **Test Edge Cases**
   - Load sample patients (includes edge cases)
   - Try custom patients with missing vitals
   - Simulate clinician overrides

4. **Customize**
   - Adjust age thresholds in `triage_engine.py`
   - Modify chief complaint keywords
   - Add hospital-specific logic

---

## Architecture Overview

```
┌─────────────┐
│   FastAPI   │  (Main application)
│   (8000)    │
└──────┬──────┘
       │
       ├─── triage_engine.py     (Scoring logic)
       ├─── audit_logger.py      (Compliance)
       ├─── database.py          (ORM + schema)
       │
       └─── PostgreSQL (5432)    (Persistent storage)
            │
            ├── patients         (Demographics)
            ├── vital_signs      (Measurements)
            ├── triage_decisions (Scores)
            ├── clinical_overrides (Clinician decisions)
            └── audit_logs       (Immutable trail)
```

---

## Support

See `README.md` for:
- Detailed API documentation
- Test scenarios (pediatric, geriatric, ambiguous)
- Database maintenance queries
- Production deployment considerations

---

**Ready to go!** 🚀

Next: Open http://localhost:8000/docs and start testing.

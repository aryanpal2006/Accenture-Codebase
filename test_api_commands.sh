#!/bin/bash
# 
# Triage API Testing - cURL Commands
# 
# Run commands individually or source this file and use the functions.
# Make sure the API is running on http://localhost:8000
#

BASE_URL="http://localhost:8000"
DEMO_MODE=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   TRIAGE API - cURL Test Commands${NC}"
echo -e "${BLUE}========================================${NC}\n"

# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================

echo -e "${YELLOW}[SYSTEM] Health Check${NC}"
curl -s -X GET "$BASE_URL/health" | jq '.'
echo ""

echo -e "${YELLOW}[SYSTEM] API Information${NC}"
curl -s -X GET "$BASE_URL/" | jq '.'
echo ""

# ============================================================================
# DEMO DATA LOADING
# ============================================================================

echo -e "${YELLOW}[DEMO] Load 20 Sample Patients${NC}"
curl -s -X POST "$BASE_URL/demo/load-sample-patients?num_patients=20" | jq '.'
echo ""

echo -e "${BLUE}⏳ Waiting for data to be loaded...${NC}"
sleep 2

# ============================================================================
# PATIENT INTAKE
# ============================================================================

echo -e "${YELLOW}[INTAKE] Register New Patient${NC}"
PATIENT_PAYLOAD='{
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "1965-05-15T00:00:00",
  "gender": "M",
  "mrn": "MRN-TEST-001",
  "chief_complaint": "Chest pain with difficulty breathing",
  "vitals": {
    "temperature_celsius": 37.2,
    "heart_rate": 115,
    "respiratory_rate": 28,
    "systolic_bp": 145,
    "diastolic_bp": 88,
    "oxygen_saturation": 92.0,
    "pain_score": 8,
    "consciousness_alert": true
  }
}'

INTAKE_RESPONSE=$(curl -s -X POST "$BASE_URL/patients/intake" \
  -H "Content-Type: application/json" \
  -d "$PATIENT_PAYLOAD")

echo "$INTAKE_RESPONSE" | jq '.'

# Extract patient_id for later use
PATIENT_ID=$(echo "$INTAKE_RESPONSE" | jq -r '.patient_id')
echo -e "${GREEN}✓ Patient ID: $PATIENT_ID${NC}\n"

sleep 1

# ============================================================================
# TRIAGE SCORING
# ============================================================================

echo -e "${YELLOW}[TRIAGE] Perform Triage Scoring${NC}"
TRIAGE_PAYLOAD="{\"patient_id\": \"$PATIENT_ID\"}"

TRIAGE_RESPONSE=$(curl -s -X POST "$BASE_URL/triage/score" \
  -H "Content-Type: application/json" \
  -d "$TRIAGE_PAYLOAD")

echo "$TRIAGE_RESPONSE" | jq '.'

# Extract decision_id for override
DECISION_ID=$(echo "$TRIAGE_RESPONSE" | jq -r '.decision_id')
echo -e "${GREEN}✓ Decision ID: $DECISION_ID${NC}\n"

sleep 1

# ============================================================================
# CLINICIAN OVERRIDE
# ============================================================================

echo -e "${YELLOW}[OVERRIDE] Clinician Override Score${NC}"
OVERRIDE_PAYLOAD="{
  \"decision_id\": \"$DECISION_ID\",
  \"overridden_severity\": \"1_resuscitation\",
  \"override_reason\": \"EKG shows ST elevation changes, STEMI protocol activated\",
  \"clinician_id\": \"MD-TEST-001\",
  \"clinician_name\": \"Dr. Test Clinician\"
}"

curl -s -X POST "$BASE_URL/triage/override" \
  -H "Content-Type: application/json" \
  -d "$OVERRIDE_PAYLOAD" | jq '.'
echo ""

sleep 1

# ============================================================================
# QUEUE MANAGEMENT
# ============================================================================

echo -e "${YELLOW}[QUEUE] Get Triage Queue (Top 5)${NC}"
curl -s -X GET "$BASE_URL/queue?limit=5" | jq '.'
echo ""

echo -e "${YELLOW}[QUEUE] Get Full Queue (Top 20)${NC}"
curl -s -X GET "$BASE_URL/queue?limit=20" | jq '.'
echo ""

sleep 1

# ============================================================================
# SYSTEM METRICS
# ============================================================================

echo -e "${YELLOW}[METRICS] Get System Metrics & Surge Detection${NC}"
curl -s -X GET "$BASE_URL/metrics/surge" | jq '.'
echo ""

# ============================================================================
# AUDIT TRAILS
# ============================================================================

echo -e "${YELLOW}[AUDIT] Get Patient Audit Trail${NC}"
curl -s -X GET "$BASE_URL/audit/patient/$PATIENT_ID" | jq '.'
echo ""

sleep 1

echo -e "${YELLOW}[AUDIT] Get Clinician Override Report (Last 24 Hours)${NC}"
curl -s -X GET "$BASE_URL/audit/overrides?hours=24" | jq '.'
echo ""

# ============================================================================
# MANUAL TESTING SECTION
# ============================================================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   MANUAL TEST COMMANDS${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${YELLOW}Use these commands to test individually:${NC}\n"

echo "# Health Check"
echo 'curl -X GET "http://localhost:8000/health"'
echo ""

echo "# Load Sample Patients"
echo 'curl -X POST "http://localhost:8000/demo/load-sample-patients?num_patients=20"'
echo ""

echo "# Register Patient"
echo 'curl -X POST "http://localhost:8000/patients/intake" \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "1990-01-15T00:00:00",
    "gender": "F",
    "chief_complaint": "Severe headache and high fever",
    "vitals": {
      "temperature_celsius": 39.5,
      "heart_rate": 102,
      "respiratory_rate": 22,
      "systolic_bp": 140,
      "diastolic_bp": 85,
      "oxygen_saturation": 97.0,
      "pain_score": 9,
      "consciousness_alert": true
    }
  }'"'"
echo ""

echo "# Get Queue"
echo 'curl -X GET "http://localhost:8000/queue?limit=10"'
echo ""

echo "# Get Metrics"
echo 'curl -X GET "http://localhost:8000/metrics/surge"'
echo ""

echo "# View Audit Trail (replace PATIENT_ID)"
echo 'curl -X GET "http://localhost:8000/audit/patient/PATIENT_ID"'
echo ""

echo "# Get Override Report"
echo 'curl -X GET "http://localhost:8000/audit/overrides?hours=24"'
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   ✓ API Testing Complete${NC}"
echo -e "${GREEN}========================================${NC}"

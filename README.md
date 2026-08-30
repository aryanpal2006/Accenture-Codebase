# PatientTriage: Clinical AI Agent & Emergency Department Triage System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-orange.svg)](https://xgboost.readthedocs.io/)
[![Google Gemini API](https://img.shields.io/badge/Gemini_API-Pydantic_Extraction-purple.svg)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**patientTriage** is an enterprise-grade, safety-first Emergency Department (ED) clinical AI system engineered to perform automated patient intake, multi-class Emergency Severity Index (ESI) acuity classification, explainable decision support, and automated physician handoff generation.

By combining **Google Gemini LLM narrative extraction**, **XGBoost supervised machine learning**, **SHAP (SHapley Additive exPlanations) explainability**, an independent **Age-Stratified Hard Clinical Safety Net**, and a **Human-in-the-Loop (HITL) nurse workflow**, patientTriage delivers rapid, transparent, and mathematically grounded clinical triage while strictly guaranteeing zero unhandled critical clinical risk.

---

## 🏛️ Architectural Rationale & System Philosophy

### 1. The Clinical Emergency Problem Space
Emergency Departments globally suffer from severe operational friction, triage latency, variable nurse experience levels, and risk of mis-triaging critically ill patients:
- **Under-Triage Risk**: Delaying care for silent critical conditions (e.g. atypical acute coronary syndrome, early sepsis, hyperpyrexia) leads to adverse patient outcomes and sentinel events.
- **Over-Triage Risk**: Assigning non-urgent respiratory viral symptoms (e.g. mild cough, sneezing, cold) to high-acuity levels exhausts resuscitation bays and paralyzes trauma staff.
- **Language & Intake Barriers**: Patients presenting in regional languages (e.g. Devanagari Hindi or Romanized Hinglish) or communicating via verbal free-text narratives create intake translation delays.

### 2. Why a Hybrid Dual-Tier Architecture?
Traditional single-paradigm approaches fail in high-stakes clinical triage environments:

| Approach Paradigm | Primary Strengths | Fundamental Vulnerabilities & Failure Modes |
| :--- | :--- | :--- |
| **Pure LLM Solution** | Excellent narrative understanding, complex free-text extraction, multilingual Hindi/Hinglish translation. | Nondeterministic output, risk of clinical hallucination, inability to enforce strict mathematical vital sign bounds, latency. |
| **Pure ML Model Solution** | Rapid statistical classification over tabular vitals and structured clinical features. | Black-box opacity; statistically smooths out rare, extreme clinical outliers (e.g. extreme hyperpyrexia `Temp ≥ 105°F` or profound shock `SBP < 80`) if underrepresented in training distributions. |
| **Pure Rule Engine Solution** | 100% deterministic, audit-compliant, and predictable for extreme vital signs. | Completely brittle; unable to interpret unstructured patient narratives, clinical context, or regional idioms (*"seene me tez dard"*). |

### 3. The 5-Layer Hybrid Blueprint
To solve these limitations, **patientTriage** implements a complementary 5-layer architecture:

```
                               ┌─────────────────────────────────────────┐
                               │   Unstructured Patient Intake Narrative │
                               │     (English / Hindi / Hinglish / Voice)│
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ LAYER 1 & 2: Google Gemini LLM Narrative Extractor & Multilingual NLP                                │
 │ - Parses unstructured text into Pydantic schema (ComplaintFeatures)                                │
 │ - Calibrated red-flag gating (differentiates benign viral symptoms from severe emergencies)        │
 │ - Translates Devanagari & Hinglish idioms ("seene me dard" -> chest pain) into clinical indicators │
 └──────────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                    │
                                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ LAYER 3: XGBoost 5-Class ESI Acuity Classifier & SHAP Explainable AI (XAI)                          │
 │ - Combines raw vital signs (SpO2, SBP, DBP, HR, RR, Temp) with extracted clinical indicators        │
 │ - Computes baseline ESI acuity prediction (1 to 5)                                                  │
 │ - Generates local SHAP feature attributions showing exact clinical feature impacts                  │
 └──────────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                    │
                                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ LAYER 4: Age-Stratified Hard Clinical Safety Net Rule Engine                                        │
 │ - Evaluates age-stratified guidelines (ACEP ESI v4, AHA ACLS/PALS, Sepsis-3, AGS Geriatric ED, ATLS) │
 │ - Deterministically OVERRIDES ML predictions whenever critical vital or clinical bounds are breached │
 └──────────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                    │
                                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ LAYER 5: Governance, HITL Nurse Workflow & SBAR Physician Handoff                                   │
 │ - Triage nurse reviews, approves, or overrides AI recommendations with required justification       │
 │ - Generates structured SBAR (Situation, Background, Assessment, Recommendation) handoff reports      │
 │ - Persists immutable timestamped audit logs for all clinical overrides                              │
 └─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Emergency Severity Index (ESI) Scale & Clinical Alignment

patientTriage adheres strictly to the **ACEP ESI Version 4 Algorithm**, categorizing patients into 5 distinct acuity levels based on clinical stability, life-threat probability, and anticipated resource utilization:

| ESI Level | Acuity Category | Clinical Target Time | Core Clinical Criteria | Supported Guidelines & Safety Net Triggers |
| :---: | :--- | :--- | :--- | :--- |
| **ESI 1** | **Resuscitation** | **Immediate (0 min)** | Life-threatening condition requiring immediate life-saving intervention. | Cardiopulmonary arrest, severe hypoxia (`SpO2 < 88%`), extreme hyperpyrexia (`Temp ≥ 105°F`), profound shock (`SBP < 80`), critical respiratory failure, life-threatening dysrhythmia. *(PALS 2020, AHA ACLS 2022, ATLS 10th Ed)* |
| **ESI 2** | **Emergent** | **< 10 minutes** | High-risk situation, altered mental status, severe pain, or acute physiological distress. | Acute coronary syndrome (ACS), active stroke presentation (FAST+ criteria), Sepsis-3 protocol trigger, severe hyperthermia (`Temp ≥ 103°F`), hypertensive emergency, geriatric altered mental status. *(ACEP ESI v4 App B, Sepsis-3 JAMA 2016, AGS/ACEP 2023)* |
| **ESI 3** | **Urgent** | **< 30 minutes** | Stable vitals requiring **multiple diagnostic/therapeutic resources** (e.g. lab work, CT/X-ray, IV fluids, IV medications). | Abdominal pain, moderate dyspnea, complex lacerations, acute pyelonephritis, uncomplicated kidney stones. |
| **ESI 4** | **Less Urgent** | **< 60 minutes** | Stable vitals requiring a **single resource** (e.g. simple X-ray, suture, or oral medication). | Simple extremity fracture, minor laceration requiring sutures, localized sprain, mild skin abscess. |
| **ESI 5** | **Non-Urgent** | **< 120 minutes** | Stable vitals requiring **no resources** (physical exam and prescription/reassurance only). | Prescription refill, suture removal, chronic minor rash, mild upper respiratory cold without fever. |

---

## 🔍 Deep-Dive: Layer-by-Layer Technical Implementation

### Layer 1 & 2: Gemini LLM Narrative Extractor & Multilingual NLP
Implemented in [`src/llm_extractor.py`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/src/llm_extractor.py).

- **Pydantic Schema Validation**: Forces Google Gemini models (via `google-genai` SDK) to output strictly validated JSON matching the `ComplaintFeatures` model defined in [`src/schemas.py`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/src/schemas.py).
- **Calibrated Red-Flag Gating**: Prevents false positive ESI 1 over-triage by enforcing strict differentiation between benign upper respiratory symptoms (*sneezing*, *mild cough*, *sore throat*, *cold*) and genuine red-flag emergencies (*crushing chest pain*, *slurred speech*, *flail chest*, *coffee ground emesis*).
- **Hindi & Hinglish Clinical Translation**: Native parsing of Devanagari Hindi script (*"सीने में तेज दर्द"*, *"सांस में तकलीफ"*) and Romanized Hinglish (*"seene me tez dard"*, *"saans lene me takleef"*, *"lakwa"*, *"bukhar"*) mapped directly to standardized English clinical indicators (`is_cardiac`, `is_respiratory`, `is_neurological`).
- **Continuous Voice Intake**: Built-in Web Speech API in [`static/app.js`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/static/app.js) operating in a continuous loop with dedicated language selectors (`hi-IN`, `en-IN`, `en-US`), allowing long multi-sentence spoken patient intakes without premature truncation.

### Layer 3: XGBoost ESI Classifier & SHAP Explainable AI (XAI)
Implemented in [`src/model.py`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/src/model.py).

- **Multi-Class XGBoost Model**: Trains a 5-class multi-class gradient boosting model (`n_estimators=120`, `max_depth=5`, `learning_rate=0.08`) over 10,000 synthetic clinical records generated via [`data/generate_dataset.py`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/data/generate_dataset.py).
- **Comprehensive Feature Vector**: Combines numeric vitals (`temperature`, `heartrate`, `resprate`, `o2sat`, `sbp`, `dbp`), missingness indicators (`temp_missing`, `hr_missing`, etc.), demographics (`age_numeric`, `gender_encoded`), and LLM extracted indicators (`llm_pain_score`, `symptom_category_encoded`, `symptom_onset_encoded`, `red_flag_phrase`, binary category flags).
- **SHAP Local Attribution**: Employs `shap.TreeExplainer` to compute exact feature attributions for every prediction, rendering clinical impact explanations (e.g. *"+1.8 ESI Risk due to Severe Hypoxia (SpO2=84%)"*) rather than non-informative feature names.

### Layer 4: Age-Stratified Hard Clinical Safety Net
Implemented in [`src/safety_net.py`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/src/safety_net.py).

The Hard Safety Net is a deterministic rule engine that **unconditionally overrides ML model predictions** when physiological vitals breach critical guidelines across six age brackets (`infant`, `toddler`, `child`, `adolescent`, `adult`, `geriatric`):

1. **Extreme Hyperpyrexia (`Temp ≥ 105.0°F / 40.5°C`)** → **ESI-1 Resuscitation**
   - *Rationale*: Critical heat stroke / central thermoregulatory failure risk requiring immediate emergency cooling protocol.
2. **Severe Hyperthermia (`Temp ≥ 103.0°F`)** → **ESI-2 Emergent**
   - *Rationale*: High risk of sepsis, CNS infection, or severe systemic inflammatory response syndrome (SIRS).
3. **Severe Hypoxia (`SpO2 < 88%` Adult / `< 90%` Peds)** → **ESI-1 Resuscitation**
   - *Rationale*: AHA ACLS / PALS airway and resuscitation threshold.
4. **Profound Shock (`SBP < 80 mmHg` Adult / Age-Stratified)** → **ESI-1 Resuscitation**
   - *Rationale*: ATLS Class III/IV hemorrhagic shock classification.
5. **Sepsis-3 Protocol (qSOFA Criteria + Active Infection)** → **ESI-2 Emergent**
   - *Rationale*: Triggered when an active infection site is identified alongside ≥2 physiological dysfunctions (tachypnea `RR ≥ 22`, hypotension `SBP ≤ 100`, fever/hypothermia). Automatically prompts STAT blood cultures, serum lactate, IV broad-spectrum antibiotics within 1h, and 30 mL/kg fluid bolus.
6. **Active Stroke Presentation (FAST+ Criteria)** → **ESI-1 / ESI-2**
   - *Rationale*: AHA/ASA 2019 Stroke Guidelines for immediate neuro-interventional pathway.
7. **Geriatric Altered Mental Status** → **ESI-2 Emergent**
   - *Rationale*: AGS/ACEP 2023 Geriatric Emergency Department Guidelines.

### Layer 5: Human-in-the-Loop (HITL) Workflow & SBAR Handoff
Implemented in [`server.py`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/server.py) and [`src/handoff_generator.py`](file:///c:/Users/palar/OneDrive/Desktop/Accenture%20New/src/handoff_generator.py).

- **Nurse Override Control**: Triage nurses retain ultimate clinical authority. The web interface provides interactive approval or manual override of AI recommended acuity, requiring a mandatory clinical justification text string.
- **Immutable Audit Logging**: Every override action appends an unalterable `AuditLogEntry` record detailing original AI recommendation, overridden ESI score, nurse ID, clinical reason, and UTC timestamp.
- **Automated SBAR Physician Handoff**: Synthesizes patient vitals, red flags, ML scores, and safety net reasons into structured physician handoff reports formatted according to the Joint Commission SBAR protocol (Situation, Background, Assessment, Recommendation).

---

## 📂 Project Architecture & Directory Structure

```
Accenture-Codebase/
├── server.py                 # FastAPI Web Server & REST API Endpoint Handlers
├── test_and_run.py           # Comprehensive Automated Integration & Unit Test Suite
├── Dockerfile                # Container Specification for Enterprise Deployment
├── docker-compose.yml        # Docker Compose Orchestration Setup
├── requirements.txt          # Python Dependencies
├── .env.example              # Environment Variable Template
├── README.md                 # System Architecture & Documentation
│
├── src/                      # Core Clinical Engine Modules
│   ├── llm_extractor.py      # Gemini LLM Extractor & Multilingual Hindi/Hinglish NLP
│   ├── model.py              # 5-Class XGBoost Classifier & SHAP Explainer Pipeline
│   ├── safety_net.py         # Age-Stratified Hard Clinical Safety Net Engine
│   ├── schemas.py            # Pydantic Data Schemas & API Contracts
│   ├── handoff_generator.py  # SBAR Physician Handoff Summary Generator
│   └── simulated_patients.py # Clinical Test Patients & Validation Cohort
│
├── static/                   # Clinical Triage Web Dashboard Frontend
│   ├── index.html            # Web UI Layout (Glassmorphism Dashboard)
│   ├── app.js                # Frontend Controller, Web Speech Voice Intake & Dynamic Queue
│   └── styles.css            # Responsive CSS Theme & Glassmorphism Styling
│
└── data/                     # Data Generation & ML Datasets
    ├── generate_dataset.py   # Synthetic Clinical Dataset Generation Script
    ├── triage.csv            # Base Raw Clinical Triage Records
    └── processed_triage.csv  # Processed ML Model Training Data
```

---

## 🚀 Quick Start Guide

### 1. System Requirements
- **Python**: 3.11 or higher
- **Operating System**: Linux, macOS, or Windows
- **API Key**: Google Gemini API key (Free tier supported via Google AI Studio)

### 2. Installation & Environment Setup

```bash
# Clone repository
git clone https://github.com/aryanpal2006/Accenture-Codebase.git
cd Accenture-Codebase

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. API Key Configuration
Create a `.env` file in the project root directory using `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` and add your Google Gemini API key:
```env
GOOGLE_API_KEY=your_actual_gemini_api_key_here
```

*(Note: If no API key is provided, the system automatically falls back to an offline rule-based clinical extractor for demonstration purposes).*

### 4. Launching the Clinical Server

Execute `server.py` to start the FastAPI server:

```bash
python server.py
```

Open your web browser and navigate to:
👉 **`http://localhost:8000`**

---

## 🧪 Running Automated Tests

Run the automated test suite to verify pipeline training, Gemini extraction, Hard Safety Net bounds, and HITL overrides:

```bash
python test_and_run.py
```

The test suite validates:
- [x] XGBoost model training and SHAP tree explainer initialization.
- [x] Multilingual Gemini narrative feature extraction (English, Hindi, Hinglish).
- [x] Extreme Hyperpyrexia (`Temp ≥ 105.0°F`) ESI-1 safety net override.
- [x] Severe Hypoxia (`SpO2 < 88%`) & Profound Shock (`SBP < 80`) safety net triggers.
- [x] Sepsis-3 qSOFA protocol evaluation.
- [x] Human-in-the-loop nurse override persistence and audit log entry formatting.

---

## 🌐 Key REST API Endpoints

| Method | Endpoint | Description | Request Body / Query Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Renders the Clinical Triage Dashboard Web UI. | None |
| `GET` | `/api/patients` | Returns active patient queue sorted by acuity score. | None |
| `POST` | `/api/triage` | Submits patient intake for LLM extraction, ML scoring, and Safety Net evaluation. | `PatientIntake` (Vitals + Chief Complaint) |
| `POST` | `/api/override` | Records a nurse HITL override or approval with clinical rationale. | `NurseOverrideRequest` (`stay_id`, `final_acuity`, `override_reason`) |
| `GET` | `/api/handoff/{stay_id}` | Generates formatted SBAR physician handoff summary. | `stay_id` (Path Parameter) |
| `POST` | `/api/surge` | Toggles Emergency Department Surge Mode simulation. | `SurgeRequest` (`surge_active`: boolean) |

---

## 🐳 Docker Deployment

To build and run the application in a isolated Docker container:

```bash
# Build and start container with Docker Compose
docker-compose up --build
```

The application will be accessible at `http://localhost:8000`.

---

## 🔒 Security, Governance & Compliance

- **Zero Hardcoded Secrets**: All API credentials are read securely via environment variables `.env` and excluded from source control via `.gitignore`.
- **Immutable Audit Trails**: Nurse overrides log immutable records containing nurse IDs, original AI outputs, override acuity levels, and UTC timestamps.
- **Fail-Safe Safety Nets**: In the event of network disruption or LLM rate-limiting, the deterministic Hard Clinical Safety Net continues operating independently to guarantee patient safety.

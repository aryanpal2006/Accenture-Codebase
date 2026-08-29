# patientTriage: Clinical AI Agent & Emergency Department Triage System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-orange.svg)](https://xgboost.readthedocs.io/)
[![Google Gemini API](https://img.shields.io/badge/Gemini_API-Pydantic_Extraction-purple.svg)](https://ai.google.dev/)

**patientTriage** is an intelligent, safety-first Emergency Department (ED) clinical AI system designed to perform automated patient intake, ESI (Emergency Severity Index) acuity classification, and clinician handoff generation.

The system combines **LLM-driven narrative extraction**, **XGBoost machine learning classification**, **explainable AI (SHAP)**, and an independent **Hard Clinical Safety Net** to ensure rapid, transparent, and safe patient triage.

---

## 🌟 Key Features

1. **LLM Red Flag & Feature Extractor**:
   - Parses unstructured patient chief complaints into structured Pydantic schemas using Google Gemini models.
   - Identifies high-risk clinical phrases (e.g., *crushing chest pain*, *slurred speech*, *flail chest*, *hyperpyrexia / severe fever*).
   - **Calibrated Red-Flag Gating**: Differentiates benign viral/respiratory complaints (*sneezing*, *mild cough*, *sore throat*, *cold*) from genuine emergencies, preventing false positive ESI 1 over-triage.
   - **Clinical Reason Generator**: Provides explicit plain-language explanations detailing *why* a red flag was raised and what specific organ risks are present.

2. **XGBoost 5-Class ESI Acuity Classifier**:
   - Predicts ESI Acuity levels (ESI 1: Immediate life-saving intervention to ESI 5: Non-urgent).
   - Combines vital signs (SpO2, SBP, DBP, Heart Rate, Resp Rate, Temp) with extracted clinical indicators.

3. **Independent Hard Clinical Safety Net**:
   - Deterministic rule layer that automatically overrides ML predictions whenever vital signs breach critical thresholds:
     - **Extreme Hyperpyrexia (`Temp ≥ 105.0°F`)** → **ESI-1 Resuscitation** (Critical heat stroke / central thermoregulatory failure risk requiring immediate emergency cooling).
     - **Severe Hyperthermia (`Temp ≥ 103.0°F`)** → **ESI-2 Emergent** (Urgent sepsis / CNS infection protocol).
     - **Profound Shock (`SBP < 80 mmHg`)** → **ESI-1 Resuscitation** (ATLS shock classification).
     - **Severe Hypoxia (`SpO2 < 88%`)** → **ESI-1 Resuscitation** (AHA/PALS airway protocol).

4. **SHAP Explainable AI (XAI)**:
   - Provides local feature impact explanations for every prediction, showing clinicians *why* a specific acuity level was assigned with clear clinical descriptions instead of generic placeholder text.

5. **Human-in-the-Loop (HITL) Nurse Workflow**:
   - Enables triage nurses to review, approve, or override AI recommendations with required clinical justification and complete audit trails.

6. **Automated SBAR Physician Handoff Summaries**:
   - Synthesizes intake vitals, red flags, and risk assessments into concise physician handoff reports.

7. **ED Surge Mode**:
   - Simulates high-volume emergency department conditions, re-prioritizing queues dynamically to focus on critical patients.

---

## 📂 Project Architecture

```
Accenture-Codebase/
├── server.py                # FastAPI Web Server & REST API Endpoints
├── test_and_run.py          # Automated Test Suite
├── src/
│   ├── model.py             # XGBoost Pipeline & SHAP Explanations
│   ├── llm_extractor.py     # Gemini LLM Narrative Feature Extractor
│   ├── safety_net.py        # Hard Clinical Safety Net Rule Engine
│   ├── schemas.py           # Pydantic Schemas & Data Contracts
│   ├── handoff_generator.py # SBAR Handoff Summary Generator
│   └── simulated_patients.py # Representative Clinical Test Cases
├── static/
│   ├── index.html           # Clinical Triage Web Dashboard UI
│   ├── app.js               # Frontend Controller & Real-Time Updates
│   └── styles.css           # Modern Glassmorphism Styling System
├── data/
│   ├── generate_dataset.py   # Synthetic Dataset Generation Script
│   ├── triage.csv           # Base Clinical Triage Data
│   └── processed_triage.csv # Processed ML Training Dataset
├── Dockerfile               # Container Image Specification
├── docker-compose.yml       # Docker Compose Deployment Configuration
├── .env.example             # Environment Variable Template
├── .gitignore               # Git Ignore Specification
└── requirements.txt         # Dependencies
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Installation & Setup

```bash
# Clone repository
git clone https://github.com/aryanpal2006/Accenture-Codebase.git
cd Accenture-Codebase

# Create virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Add your Google Gemini API key to `.env`:
```env
GOOGLE_API_KEY=your_actual_gemini_api_key_here
```

### 4. Running the Application

Start the server using `python server.py`:

```bash
python server.py
```

The clinical dashboard will be available at: **http://localhost:8000**

---

## 🧪 Running Tests

Execute the comprehensive automated unit & integration test suite:

```bash
python test_and_run.py
```

---

## 🐳 Docker Deployment

To build and run using Docker:

```bash
docker-compose up --build
```

---

## 🔒 Security & Compliance
- **Zero Credentials Committed**: Credentials are loaded securely via `.env` and kept untracked.
- **Audit Trails**: All nurse overrides and clinical decisions log immutable timestamped audit entries.

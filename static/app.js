let currentStayId = null;
let currentPatientData = null;
let currentTriageResult = null;
let selectedOverrideEsi = null;
let currentFilter = 'all';
let isSurgeMode = false;
let isRecording = false;

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initQueueState();
  loadPatientQueue();
  setupIntakeEnterNavigation();
});

// Queue Panel Visibility Toggle
function toggleQueuePanel() {
  const container = document.querySelector('.app-container');
  if (!container) return;
  const isCollapsed = container.classList.toggle('queue-collapsed');
  localStorage.setItem('queueCollapsed', isCollapsed ? 'true' : 'false');
  updateQueueToggleBtnUI(isCollapsed);
}

function updateQueueToggleBtnUI(isCollapsed) {
  const btnText = document.getElementById('queueToggleText');
  const btnIcon = document.getElementById('queueToggleIcon');
  const queueBtn = document.getElementById('queueToggleBtn');
  const hamburgerBtn = document.getElementById('hamburgerMenuBtn');
  if (btnText) {
    btnText.innerText = isCollapsed ? 'Show Queue' : 'Hide Queue';
  }
  if (btnIcon) {
    btnIcon.innerText = isCollapsed ? '☰' : '📋';
  }
  if (queueBtn) {
    if (isCollapsed) {
      queueBtn.classList.remove('active');
    } else {
      queueBtn.classList.add('active');
    }
  }
  if (hamburgerBtn) {
    if (isCollapsed) {
      hamburgerBtn.classList.remove('active');
    } else {
      hamburgerBtn.classList.add('active');
    }
  }
}

function initQueueState() {
  const saved = localStorage.getItem('queueCollapsed');
  if (saved === 'true') {
    const container = document.querySelector('.app-container');
    if (container) container.classList.add('queue-collapsed');
    updateQueueToggleBtnUI(true);
  }
}

// Dark / Light Theme Toggle
function initTheme() {
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = savedTheme || (prefersDark ? 'dark' : 'light');
  applyTheme(theme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  if (document.body) {
    document.body.setAttribute('data-theme', theme);
    if (theme === 'dark') {
      document.body.classList.add('dark-theme');
    } else {
      document.body.classList.remove('dark-theme');
    }
  }
  localStorage.setItem('theme', theme);
  const themeIcon = document.getElementById('themeIcon');
  if (themeIcon) {
    themeIcon.innerText = (theme === 'dark') ? '☀️' : '🌙';
  }
}

function toggleDarkMode() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || (document.body ? document.body.getAttribute('data-theme') : 'light') || 'light';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
}

async function loadPatientQueue() {
  try {
    const res = await fetch('/api/patients');
    const data = await res.json();

    isSurgeMode = data.surge_mode;
    updateSurgeUI();

    document.getElementById('queueCount').innerText = data.patient_count;
    renderQueueList(data.patients);

    // Auto-select first patient if none selected
    if (!currentStayId && data.patients.length > 0) {
      selectPatient(data.patients[0].stay_id);
    }
  } catch (err) {
    console.error('Failed to load patient queue:', err);
  }
}

function updateSurgeUI() {
  const surgeBtn = document.getElementById('surgeBtn');
  const surgeText = document.getElementById('surgeStatusText');
  if (isSurgeMode) {
    surgeBtn.classList.add('active');
    surgeText.innerText = '3x SURGE ACTIVE';
  } else {
    surgeBtn.classList.remove('active');
    surgeText.innerText = 'NORMAL';
  }
}

async function clearAllHistory() {
  if (!confirm('Are you sure you want to clear the entire triage queue and patient history for a fresh shift?')) {
    return;
  }
  try {
    const res = await fetch('/api/clear-history', { method: 'POST' });
    const data = await res.json();
    currentStayId = null;
    currentPatientData = null;
    currentTriageResult = null;
    openNewIntakeForm();
    await loadPatientQueue();
  } catch (err) {
    console.error('Failed to clear patient history:', err);
  }
}

function renderQueueList(patients) {
  const container = document.getElementById('patientListContainer');
  container.innerHTML = '';

  const searchVal = document.getElementById('searchBox').value.toLowerCase();

  patients.forEach(p => {
    // Search filter
    if (searchVal) {
      const matchName = p.name.toLowerCase().includes(searchVal);
      const matchId = String(p.stay_id).includes(searchVal);
      const matchCc = p.chiefcomplaint.toLowerCase().includes(searchVal);
      if (!matchName && !matchId && !matchCc) return;
    }

    // Pill filter
    if (currentFilter === '1' && p.recommended_acuity !== 1) return;
    if (currentFilter === '2' && p.recommended_acuity !== 2) return;
    if (currentFilter === '3' && p.recommended_acuity !== 3) return;
    if (currentFilter === 'low_conf' && !p.is_low_confidence) return;

    const card = document.createElement('div');
    card.className = `patient-card ${p.stay_id === currentStayId ? 'selected' : ''}`;
    card.onclick = () => selectPatient(p.stay_id);

    const esiClass = `esi-${p.recommended_acuity}`;

    let tagsHtml = '';
    if (p.safety_net_triggered) {
      tagsHtml += `<span class="warning-tag">⚠️ HARD SAFETY NET</span> `;
    }
    if (p.is_low_confidence) {
      tagsHtml += `<span class="warning-tag" style="background: rgba(234,179,8,0.2); color:#fde047; border-color: rgba(234,179,8,0.4);">⚠️ LOW CONFIDENCE</span> `;
    }
    if (p.was_overridden) {
      tagsHtml += `<span class="warning-tag" style="background: rgba(139,92,246,0.2); color:#c084fc; border-color: rgba(139,92,246,0.4);">✏️ NURSE OVERRIDDEN</span> `;
    }

    const tempStr = p.temperature ? `${p.temperature}°F` : 'Temp: N/A';
    const hrStr = p.heartrate ? `HR: ${p.heartrate}` : 'HR: N/A';
    const o2Str = p.o2sat ? `SpO2: ${p.o2sat}%` : 'SpO2: N/A';

    card.innerHTML = `
      <div class="card-header">
        <div>
          <div class="card-name">${p.name}</div>
          <div class="card-meta">ID: #${p.stay_id} | ${p.age} y/o ${p.gender}</div>
        </div>
        <div class="esi-badge ${esiClass}">ESI ${p.recommended_acuity}</div>
      </div>
      <div class="card-cc">"${p.chiefcomplaint}"</div>
      <div class="card-vitals-row">
        <span class="vital-tag">${tempStr}</span>
        <span class="vital-tag">${hrStr}</span>
        <span class="vital-tag">${o2Str}</span>
      </div>
      <div>${tagsHtml}</div>
    `;

    container.appendChild(card);
  });
}

async function selectPatient(stayId) {
  currentStayId = stayId;
  try {
    const res = await fetch(`/api/patient/${stayId}`);
    const data = await res.json();

    currentPatientData = data.patient;
    currentTriageResult = data.triage_result;

    renderWorkspace(data.patient, data.triage_result, data.nurse_decision);
    loadPatientQueue();
  } catch (err) {
    console.error('Failed to select patient:', err);
  }
}

function renderWorkspace(patient, triage, nurseDecision) {
  // Stage 1 Header & Vitals
  const nameInput = document.getElementById('v_name');
  if (nameInput) {
    nameInput.value = patient.name || '';
  }
  document.getElementById('patientMetaText').innerText = `Stay ID: #${patient.stay_id} | Subject ID: ${patient.subject_id || 'N/A'} | Age: ${patient.age} | Gender: ${patient.gender}`;

  const historyBox = document.getElementById('historyBadge');
  if (patient.is_returning_patient || (patient.prior_medical_history && !patient.prior_medical_history.includes('First-Time'))) {
    historyBox.innerText = `📂 History: ${patient.prior_medical_history || 'Returning Patient'}`;
    historyBox.style.background = '#e0f2fe';
    historyBox.style.color = '#0369a1';
    historyBox.style.border = '1px solid #bae6fd';
  } else {
    historyBox.innerText = `View Full History →`;
    historyBox.style.background = '#ffffff';
    historyBox.style.color = '#2563eb';
    historyBox.style.border = '1px solid #2563eb';
  }

  // Populate vitals inputs
  document.getElementById('v_temp').value = patient.temperature || '';
  document.getElementById('v_hr').value = patient.heartrate || '';
  document.getElementById('v_rr').value = patient.resprate || '';
  document.getElementById('v_o2').value = patient.o2sat || '';
  document.getElementById('v_sbp').value = patient.sbp || '';
  document.getElementById('v_dbp').value = patient.dbp || '';
  document.getElementById('v_age').value = patient.age || '';
  document.getElementById('v_gender').value = patient.gender || 'Unspecified';

  // Stage 2 Complaint
  document.getElementById('complaintInput').value = patient.chiefcomplaint;

  // Stage 3 LLM Features
  const extracted = triage.extracted_features;
  document.getElementById('llmSummaryNarrative').innerText = extracted.summary_narrative || 'Extracted clinical features from complaint narrative.';

  const featGrid = document.getElementById('llmFeaturesGrid');

  // Build onset label from encoded value
  const onsetLabels = { 0: 'Acute (<2h)', 1: 'Sub-Acute (2-12h)', 2: 'Delayed (12h-3d)', 3: 'Chronic (>3d)' };
  const onsetLabel = onsetLabels[extracted.symptom_onset_encoded] || extracted.symptom_onset || 'Unknown';
  const catLabel = (extracted.primary_symptom_category || 'general').toUpperCase();
  const secCat = extracted.secondary_symptom_category && extracted.secondary_symptom_category !== 'none'
    ? extracted.secondary_symptom_category.toUpperCase()
    : 'NONE';
  const painScore = extracted.llm_pain_score !== null && extracted.llm_pain_score !== undefined
    ? `${extracted.llm_pain_score}/10`
    : 'N/A';

  let hindiPill = '';
  if (extracted.is_hindi_script) {
    hindiPill = `
    <div class="feature-pill-box">
      <span class="feature-label">Language Input</span>
      <span class="feature-val" style="background: #ffedd5; color: #c2410c;">🇮🇳 Hindi Script</span>
    </div>`;
  }

  const redFlagNotice = (extracted.red_flag_reason) ? `
    <div style="grid-column: 1 / -1; background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 10px 14px; margin-top: 6px; color: #991b1b; font-size: 13px; line-height: 1.5;">
      ${extracted.red_flag_reason}
    </div>` : '';

  featGrid.innerHTML = `
    <div class="feature-pill-box">
      <span class="feature-label">Primary Category</span>
      <span class="feature-val" style="background: #e0f2fe; color:#0369a1;">${catLabel}</span>
    </div>
    <div class="feature-pill-box">
      <span class="feature-label">Secondary Category</span>
      <span class="feature-val" style="background: #f3e8ff; color:#6d28d9;">${secCat}</span>
    </div>
    <div class="feature-pill-box">
      <span class="feature-label">LLM Pain Score</span>
      <span class="feature-val" style="background: #ffedd5; color:#c2410c;">${painScore}</span>
    </div>
    <div class="feature-pill-box">
      <span class="feature-label">Red Flag Phrase</span>
      <span class="feature-val ${extracted.red_flag_phrase ? 'val-true' : 'val-false'}">${extracted.red_flag_phrase ? 'YES ⚠️' : 'No'}</span>
    </div>
    <div class="feature-pill-box">
      <span class="feature-label">Symptom Onset</span>
      <span class="feature-val" style="background: #fae8ff; color:#86198f;">${onsetLabel}</span>
    </div>
    ${hindiPill}
    ${redFlagNotice}
  `;

  // Stage 4 Acuity Assessment (ALWAYS shows AI recommendation so nurse override in Stage 5 doesn't change it)
  const aiAcuity = triage.recommended_acuity;

  const circle = document.getElementById('esiScoreCircle');
  circle.innerText = aiAcuity;
  circle.className = `esi-circle esi-${aiAcuity}`;

  document.getElementById('esiLabelText').innerText = triage.acuity_label;
  document.getElementById('currentRecEsi').innerText = aiAcuity;

  const safetyBox = document.getElementById('safetyNetStatusText');
  if (triage.safety_net_triggered) {
    safetyBox.innerHTML = `<span style="color: #ef4444; font-weight: 800;">🚨 HARD SAFETY NET TRIGGERED: ${triage.safety_net_reason}</span>`;
  } else {
    safetyBox.innerHTML = `<span style="color: #10b981;">✅ Hard Safety Net: Passed (No vital boundary breach)</span>`;
  }

  const confVal = Math.round((triage.confidence_score || 0.8) * 100);
  document.getElementById('confidenceScoreVal').innerText = `${confVal}%`;
  const confLbl = document.getElementById('confidenceLabel');
  if (triage.is_low_confidence) {
    confLbl.innerHTML = `<span style="color: #eab308; font-weight: 700;">⚠️ Low Confidence Flag</span>`;
  } else {
    confLbl.innerText = 'AI Model Confidence';
  }

  // SHAP bullets: Clean up text and order by urgency (red bars first, green bars second)
  const shapContainer = document.getElementById('shapListContainer');
  shapContainer.innerHTML = '';

  const rawReasonings = triage.plain_language_reasoning || [];
  const redItems = [];
  const greenItems = [];

  rawReasonings.forEach(r => {
    // Strip SHAP score badges or inc/dec text if present
    const cleanText = r.replace(/\s*\(SHAP:\s*[+-]?\d+\.?\d*\)/gi, '')
                       .replace(/\s*—\s*↑\s*Escalates\s*Acuity/gi, '')
                       .replace(/\s*—\s*↓\s*Decreases\s*Urgency/gi, '')
                       .replace(/\s*\(\+\)/g, '')
                       .replace(/\s*\(\-\)/g, '')
                       .trim();

    const lower = r.toLowerCase();
    const isEscalates = r.includes('(+)').toString() === 'true' || 
                        r.includes('↑') || 
                        lower.includes('escalates') || 
                        lower.includes('primary presentation') || 
                        lower.includes('high-risk') || 
                        lower.includes('red flag') || 
                        lower.includes('severe') || 
                        lower.includes('hypoxia') || 
                        lower.includes('critical');

    if (isEscalates) {
      redItems.push(cleanText);
    } else {
      greenItems.push(cleanText);
    }
  });

  // Render Red items first
  redItems.forEach(text => {
    const item = document.createElement('div');
    item.className = 'shap-item escalates';
    item.innerHTML = `<div>${text}</div>`;
    shapContainer.appendChild(item);
  });

  // Render Green items second
  greenItems.forEach(text => {
    const item = document.createElement('div');
    item.className = 'shap-item reduces';
    item.innerHTML = `<div>${text}</div>`;
    shapContainer.appendChild(item);
  });

  // Nurse Status Box
  const statusBox = document.getElementById('nurseStatusBox');
  if (nurseDecision) {
    statusBox.style.display = 'block';
    if (nurseDecision.was_overridden) {
      statusBox.style.background = '#f3e8ff';
      statusBox.style.border = '1px solid #d8b4fe';
      statusBox.style.color = '#6d28d9';
      statusBox.innerHTML = `<strong>✏️ NURSE OVERRIDDEN:</strong> Final Assigned ESI ${nurseDecision.final_acuity}. <br>Rationale: "${nurseDecision.override_reason}" (Reviewed by ${nurseDecision.nurse_name} at ${nurseDecision.timestamp})`;
    } else {
      statusBox.style.background = '#ecfdf5';
      statusBox.style.border = '1px solid #a7f3d0';
      statusBox.style.color = '#047857';
      statusBox.innerHTML = `<strong>✅ APPROVED BY NURSE:</strong> Verified AI recommendation ESI ${nurseDecision.final_acuity}. (Reviewed by ${nurseDecision.nurse_name} at ${nurseDecision.timestamp})`;
    }
  } else {
    statusBox.style.display = 'none';
  }
}

async function executeTriageAnalysis() {
  const cc = document.getElementById('complaintInput').value;
  if (!cc.trim()) {
    alert('Please enter a chief complaint narrative.');
    return;
  }

  const nameInput = document.getElementById('v_name');
  const patientName = (nameInput && nameInput.value.trim())
    ? nameInput.value.trim()
    : (currentPatientData ? currentPatientData.name : 'Walk-in Intake Patient');

  const payload = {
    stay_id: currentStayId,
    subject_id: currentPatientData ? currentPatientData.subject_id : null,
    name: patientName,
    age: parseInt(document.getElementById('v_age').value) || (currentPatientData ? currentPatientData.age : 45),
    gender: document.getElementById('v_gender').value || (currentPatientData ? currentPatientData.gender : 'Unspecified'),
    temperature: parseFloat(document.getElementById('v_temp').value) || null,
    heartrate: parseFloat(document.getElementById('v_hr').value) || null,
    resprate: parseFloat(document.getElementById('v_rr').value) || null,
    o2sat: parseFloat(document.getElementById('v_o2').value) || null,
    sbp: parseFloat(document.getElementById('v_sbp').value) || null,
    dbp: parseFloat(document.getElementById('v_dbp').value) || null,
    chiefcomplaint: cc,
    is_returning_patient: currentPatientData ? currentPatientData.is_returning_patient : false,
    prior_medical_history: currentPatientData ? currentPatientData.prior_medical_history : null
  };

  try {
    const res = await fetch('/api/triage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    currentStayId = data.stay_id;
    await selectPatient(currentStayId);
  } catch (err) {
    console.error('Failed to run triage analysis:', err);
  }
}

function loadSampleText(text) {
  document.getElementById('complaintInput').value = text;
}

let activeRecognition = null;

function toggleVoiceRecord() {
  const btn = document.getElementById('recordMicBtn');
  const txt = document.getElementById('micStatusText');
  const bars = document.querySelectorAll('.waveform-sim .bar');
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (isRecording) {
    // Stop recording
    if (activeRecognition) {
      activeRecognition.stop();
      activeRecognition = null;
    }
    isRecording = false;
    btn.classList.remove('recording');
    txt.innerText = 'Click mic for speech intake';
    bars.forEach(b => b.classList.remove('animating'));
    return;
  }

  // Start recording using Web Speech API
  if (SpeechRecognition) {
    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        isRecording = true;
        btn.classList.add('recording');
        txt.innerText = '🎙️ Listening live... Speak clinical chief complaint';
        bars.forEach(b => b.classList.add('animating'));
      };

      recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        document.getElementById('complaintInput').value = transcript;
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition notice:', event.error);
        txt.innerText = `Mic alert (${event.error}). Click to retry or type directly.`;
        isRecording = false;
        btn.classList.remove('recording');
        bars.forEach(b => b.classList.remove('animating'));
      };

      recognition.onend = () => {
        isRecording = false;
        btn.classList.remove('recording');
        txt.innerText = '✅ Speech captured. Review narrative and click Analyze.';
        bars.forEach(b => b.classList.remove('animating'));
        activeRecognition = null;
      };

      activeRecognition = recognition;
      recognition.start();
    } catch (e) {
      console.error('Failed to start speech recognition:', e);
      _fallbackSimulatedVoice(btn, txt, bars);
    }
  } else {
    // Browser doesn't support Web Speech API (e.g. Firefox)
    _fallbackSimulatedVoice(btn, txt, bars);
  }
}

function _fallbackSimulatedVoice(btn, txt, bars) {
  isRecording = true;
  btn.classList.add('recording');
  txt.innerText = '🎙️ (Simulated Voice) Capturing speech transcript...';
  bars.forEach(b => b.classList.add('animating'));

  setTimeout(() => {
    isRecording = false;
    btn.classList.remove('recording');
    txt.innerText = 'Click mic for speech intake';
    bars.forEach(b => b.classList.remove('animating'));
    loadSampleText('Patient reporting sudden crushing chest pain radiating to jaw with dyspnea.');
    executeTriageAnalysis();
  }, 2500);
}

function resetWorkspaceToBlank() {
  currentStayId = null;
  currentPatientData = null;
  currentTriageResult = null;

  const nameInput = document.getElementById('v_name');
  if (nameInput) {
    nameInput.value = '';
    nameInput.placeholder = 'Enter Patient Name';
    nameInput.focus();
  }
  const metaText = document.getElementById('patientMetaText');
  if (metaText) {
    metaText.innerText = 'Enter patient vitals and chief complaint narrative below.';
  }

  const historyBox = document.getElementById('historyBadge');
  if (historyBox) {
    historyBox.innerText = 'Medical History: Pending Intake';
    historyBox.style.background = '#f1f5f9';
    historyBox.style.color = '#64748b';
    historyBox.style.border = '1px solid #cbd5e1';
  }

  document.getElementById('v_temp').value = '';
  document.getElementById('v_hr').value = '';
  document.getElementById('v_rr').value = '';
  document.getElementById('v_o2').value = '';
  document.getElementById('v_sbp').value = '';
  document.getElementById('v_dbp').value = '';
  document.getElementById('v_age').value = '';
  document.getElementById('v_gender').value = 'Unspecified';
  document.getElementById('complaintInput').value = '';

  // Reset Stage 3 LLM Features
  const llmNarrative = document.getElementById('llmSummaryNarrative');
  if (llmNarrative) {
    llmNarrative.innerText = 'Awaiting patient submission to extract clinical features...';
  }
  const featGrid = document.getElementById('llmFeaturesGrid');
  if (featGrid) {
    featGrid.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; font-style: italic; padding: 0.5rem 0;">No feature extraction data yet. Enter patient details and click "Generate Diagnosis".</div>';
  }

  // Reset Stage 4 Acuity Banner & SHAP
  const circle = document.getElementById('esiScoreCircle');
  if (circle) {
    circle.innerText = '--';
    circle.className = 'esi-circle esi-pending';
  }
  const labelText = document.getElementById('esiLabelText');
  if (labelText) {
    labelText.innerText = 'ESI Score Pending';
  }
  const currentRecEsi = document.getElementById('currentRecEsi');
  if (currentRecEsi) {
    currentRecEsi.innerText = '--';
  }
  const safetyBox = document.getElementById('safetyNetStatusText');
  if (safetyBox) {
    safetyBox.innerHTML = '<span style="color: var(--text-muted);">Hard Safety Net: Awaiting Triage</span>';
  }
  const confScore = document.getElementById('confidenceScoreVal');
  if (confScore) {
    confScore.innerText = '--';
  }
  const confLabel = document.getElementById('confidenceLabel');
  if (confLabel) {
    confLabel.innerText = 'AI Model Confidence';
  }

  const shapContainer = document.getElementById('shapListContainer');
  if (shapContainer) {
    shapContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; font-style: italic; padding: 0.5rem 0;">SHAP clinical reasoning will appear here after AI triage analysis.</div>';
  }

  const statusBox = document.getElementById('nurseStatusBox');
  if (statusBox) {
    statusBox.style.display = 'none';
  }
}

function openNewIntakeForm() {
  resetWorkspaceToBlank();
}

async function approveAiRecommendation() {
  if (!currentStayId || !currentTriageResult) return;

  const payload = {
    stay_id: currentStayId,
    nurse_acuity: currentTriageResult.recommended_acuity,
    override_reason: 'Approved AI recommendation without changes',
    nurse_name: 'Triage Nurse RN'
  };

  try {
    await fetch('/api/override', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    await selectPatient(currentStayId);
  } catch (err) {
    console.error('Failed to approve recommendation:', err);
  }
}

function openOverrideModal() {
  if (!currentStayId || !currentTriageResult) return;
  selectedOverrideEsi = currentTriageResult.recommended_acuity;
  document.getElementById('overrideModal').classList.add('open');
}

function closeOverrideModal() {
  document.getElementById('overrideModal').classList.remove('open');
}

function selectOverrideEsi(esi, el) {
  selectedOverrideEsi = esi;
  document.querySelectorAll('.override-option').forEach(opt => opt.classList.remove('selected'));
  el.classList.add('selected');
}

async function submitNurseOverride() {
  const reason = document.getElementById('overrideReasonInput').value;
  if (!reason.trim()) {
    alert('Please enter clinical justification for the override.');
    return;
  }

  const payload = {
    stay_id: currentStayId,
    nurse_acuity: selectedOverrideEsi,
    override_reason: reason,
    nurse_name: 'Triage Nurse RN'
  };

  try {
    await fetch('/api/override', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    closeOverrideModal();
    await selectPatient(currentStayId);
  } catch (err) {
    console.error('Failed to submit override:', err);
  }
}

let currentHandoffRawText = "";

async function openPhysicianHandoffModal() {
  if (!currentStayId) return;
  try {
    const res = await fetch(`/api/handoff/${currentStayId}`);
    const data = await res.json();
    currentHandoffRawText = data.summary_text || "";
    renderHospitalReport(data);
    document.getElementById('handoffModal').classList.add('open');
  } catch (err) {
    console.error('Failed to generate physician handoff:', err);
  }
}

function renderHospitalReport(data) {
  const container = document.getElementById('handoffReportContent');
  if (!container) return;

  const t = data.triage_result || {};
  const n = data.nurse_info || {};
  const p = data.patient_info || {};
  const vitals = t.vitals_summary || {};
  const ext = t.extracted_features || {};

  const stayId = t.stay_id || currentStayId;
  const name = t.patient_name || p.name || 'Unknown Patient';
  const age = t.age || p.age || 'N/A';
  const gender = t.gender || p.gender || 'N/A';
  const timestamp = new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });

  // Vitals Strings & alert triggers
  const tempVal = vitals.temperature ? `${vitals.temperature} °F` : 'Unrecorded';
  const tempAlert = vitals.temperature && (vitals.temperature > 100.4 || vitals.temperature < 95.0);

  const hrVal = vitals.heartrate ? `${vitals.heartrate} bpm` : 'Unrecorded';
  const hrAlert = vitals.heartrate && (vitals.heartrate > 100 || vitals.heartrate < 50);

  const rrVal = vitals.resprate ? `${vitals.resprate} /min` : 'Unrecorded';
  const rrAlert = vitals.resprate && (vitals.resprate > 24 || vitals.resprate < 10);

  const o2Val = vitals.o2sat ? `${vitals.o2sat}%` : 'Unrecorded';
  const o2Alert = vitals.o2sat && vitals.o2sat < 92;

  const bpVal = (vitals.sbp && vitals.dbp) ? `${vitals.sbp}/${vitals.dbp} mmHg` : 'Unrecorded';
  const bpAlert = vitals.sbp && (vitals.sbp > 180 || vitals.sbp < 90);

  const painVal = vitals.pain !== undefined && vitals.pain !== null ? `${vitals.pain} / 10` : 'Unassessed';

  // Acuity & Nurse
  const aiAcuity = t.recommended_acuity || 3;
  const acuityLabel = t.acuity_label || `ESI ${aiAcuity}`;
  const confidence = t.confidence_score ? `${(t.confidence_score * 100).toFixed(1)}%` : 'N/A';
  const isLowConf = t.is_low_confidence || false;

  const safetyNetTriggered = t.safety_net_triggered || false;
  const safetyNetReason = t.safety_net_reason || 'None';

  let nurseStatusTitle = `PENDING NURSE VERIFICATION (AI Rec: ESI ${aiAcuity})`;
  let nurseStatusClass = "pending";
  let nurseNote = "Pending final RN verification and triage assignment.";
  let finalAcuity = aiAcuity;
  let nurseName = "Triage RN";
  let nurseTime = timestamp;

  if (n && n.was_overridden) {
    finalAcuity = n.final_acuity;
    nurseStatusTitle = `CLINICAL OVERRIDE: Assigned ESI ${finalAcuity} (AI Rec was ESI ${aiAcuity})`;
    nurseStatusClass = "overridden";
    nurseNote = n.override_reason || "Nurse override logged.";
    nurseName = n.nurse_name || "RN Officer";
    nurseTime = n.timestamp || timestamp;
  } else if (n && n.final_acuity) {
    finalAcuity = n.final_acuity;
    nurseStatusTitle = `APPROVED BY RN: ESI ${finalAcuity} Verified`;
    nurseStatusClass = "approved";
    nurseNote = "Nurse verified and approved AI recommendation without modification.";
    nurseName = n.nurse_name || "RN Officer";
    nurseTime = n.timestamp || timestamp;
  }

  const routingMap = {
    1: "IMMEDIATE RESUSCITATION BAY (Level 1 Emergency)",
    2: "ACUTE CRITICAL CARE BED (Priority 1 Ratio)",
    3: "URGENT ED TREATMENT BAY (Full Diagnostic Workup)",
    4: "FAST TRACK CLINIC (Focused single-resource evaluation)",
    5: "TRIAGE EXPRESS / OUTPATIENT CLINIC"
  };
  const careRouting = routingMap[finalAcuity] || "STANDARD ED BAY";

  const shapList = (t.plain_language_reasoning || []).map(r => `<li>${r}</li>`).join('');

  container.innerHTML = `
    <div class="report-paper">
      <!-- Hospital Header Banner -->
      <div class="report-header-banner">
        <div class="hospital-brand">
          <div class="hospital-seal">⚕️</div>
          <div>
            <h2 class="hospital-name">ST. JUDE GENERAL HOSPITAL & MEDICAL CENTER</h2>
            <div class="hospital-sub">Department of Emergency Medicine • Clinical AI Decision Support</div>
          </div>
        </div>
        <div class="report-meta-box">
          <div><strong>DOCUMENT:</strong> PHYSICIAN HANDOFF REPORT</div>
          <div><strong>PROTOCOL:</strong> SBAR Standard</div>
          <div><strong>PATIENT ID:</strong> MRN-${stayId}</div>
          <div><strong>DATE/TIME:</strong> ${timestamp}</div>
        </div>
      </div>

      <!-- Demographics Section -->
      <div class="report-section-title">1. PATIENT DEMOGRAPHICS & IDENTIFICATION</div>
      <table class="report-table">
        <tr>
          <th>Patient Name:</th>
          <td><strong>${name}</strong></td>
          <th>Stay ID / MRN:</th>
          <td>#${stayId}</td>
        </tr>
        <tr>
          <th>Age / Gender:</th>
          <td>${age} y/o ${gender}</td>
          <th>Intake Time:</th>
          <td>${timestamp}</td>
        </tr>
        <tr>
          <th>EHR History:</th>
          <td colspan="3">${p.is_returning_patient ? '⚠️ Returning Patient (Prior Emergency Visit Records on File)' : 'Initial Visit / No Prior ED Visits'}</td>
        </tr>
      </table>

      <!-- Situation & Background -->
      <div class="report-section-title">2. CHIEF COMPLAINT</div>
      <div class="report-narrative-box">
        "${t.chief_complaint_raw || p.chiefcomplaint || 'No complaint text recorded.'}"
      </div>

      <!-- Vitals Table -->
      <div class="report-section-title">3. INTAKE VITAL SIGNS</div>
      <div class="report-vitals-grid">
        <div class="v-box ${tempAlert ? 'v-alert' : ''}">
          <span class="v-label">TEMPERATURE</span>
          <span class="v-val">${tempVal}</span>
        </div>
        <div class="v-box ${hrAlert ? 'v-alert' : ''}">
          <span class="v-label">HEART RATE</span>
          <span class="v-val">${hrVal}</span>
        </div>
        <div class="v-box ${rrAlert ? 'v-alert' : ''}">
          <span class="v-label">RESP RATE</span>
          <span class="v-val">${rrVal}</span>
        </div>
        <div class="v-box ${o2Alert ? 'v-alert' : ''}">
          <span class="v-label">SPO2 SAT</span>
          <span class="v-val">${o2Val}</span>
        </div>
        <div class="v-box ${bpAlert ? 'v-alert' : ''}">
          <span class="v-label">BLOOD PRESSURE</span>
          <span class="v-val">${bpVal}</span>
        </div>
        <div class="v-box">
          <span class="v-label">PAIN SCORE</span>
          <span class="v-val">${painVal}</span>
        </div>
      </div>

      <!-- Clinical NLP Extractions -->
      <div class="report-section-title">4. CLINICAL NLP EXTRACTION</div>
      <table class="report-table">
        <tr>
          <th>Primary Category:</th>
          <td><span class="report-tag">${(ext.primary_symptom_category || 'General').toUpperCase()}</span></td>
          <th>Secondary Category:</th>
          <td><span class="report-tag">${(ext.secondary_symptom_category || 'None').toUpperCase()}</span></td>
        </tr>
        <tr>
          <th>Red Flag Phrases:</th>
          <td>${(ext.red_flag_phrase || ext.is_high_risk_phrase) ? '<span class="tag-alert">YES ⚠️ Red Flag Detected</span>' : '<span class="tag-pass">None Identified</span>'}</td>
          <th>Symptom Onset:</th>
          <td>${(ext.symptom_onset || 'Subacute').toUpperCase()}</td>
        </tr>
        <tr>
          <th>Organ Systems:</th>
          <td colspan="3">
            <span class="organ-flag ${ext.is_cardiac ? 'flag-active' : ''}">Cardiac: ${ext.is_cardiac ? 'YES' : 'No'}</span>
            <span class="organ-flag ${ext.is_neurological ? 'flag-active' : ''}">Neuro: ${ext.is_neurological ? 'YES' : 'No'}</span>
            <span class="organ-flag ${ext.is_respiratory ? 'flag-active' : ''}">Resp: ${ext.is_respiratory ? 'YES' : 'No'}</span>
            <span class="organ-flag ${ext.is_trauma ? 'flag-active' : ''}">Trauma: ${ext.is_trauma ? 'YES' : 'No'}</span>
          </td>
        </tr>
      </table>

      <!-- AI Triage & SHAP -->
      <div class="report-section-title">5. AI ACUITY ASSESSMENT & SHAP EXPLANATION</div>
      <div class="report-ai-card">
        <div class="ai-left-group">
          <div class="report-esi-badge esi-${aiAcuity}">ESI ${aiAcuity}</div>
          <div>
            <div class="ai-acuity-name">${acuityLabel}</div>
            <div class="ai-confidence-meta">XGBoost Model Confidence: <strong>${confidence}</strong> ${isLowConf ? '<span class="tag-alert">⚠️ Low Confidence</span>' : ''}</div>
          </div>
        </div>
        <div class="safety-net-status ${safetyNetTriggered ? 'sn-triggered' : 'sn-ok'}">
          <strong>Hard Safety Net:</strong> ${safetyNetTriggered ? `TRIGGERED ⚠️ (${safetyNetReason})` : 'Passed'}
        </div>
      </div>
      <div class="report-shap-box">
        <div style="font-weight: 700; margin-bottom: 0.35rem; color: #000000;">Clinical Feature Drivers (SHAP Attribution):</div>
        <ul>${shapList || '<li>Standard clinical presentation.</li>'}</ul>
      </div>

      <!-- Nurse HITL Review -->
      <div class="report-section-title">NURSE VERIFICATION & AUDIT</div>
      <div class="report-nurse-box ${nurseStatusClass}">
        <div class="nurse-status-header">
          <span>${nurseStatusTitle}</span>
        </div>
        <div class="nurse-details">
          <div><strong>Nurse Officer:</strong> ${nurseName} | <strong>Timestamp:</strong> ${nurseTime}</div>
          <div style="margin-top: 0.35rem;"><strong>Clinical Rationale:</strong> ${nurseNote}</div>
        </div>
      </div>

      <!-- Care Routing -->
      <div class="report-section-title">RECOMMENDED CARE ROUTING</div>
      <div class="report-routing-banner">
        <div style="font-size: 1.4rem;">🚑</div>
        <div>
          <div style="font-size: 0.72rem; text-transform: uppercase; font-weight: 800; opacity: 0.9;">Destination Routing Bay:</div>
          <div style="font-size: 1.05rem; font-weight: 900;">${careRouting}</div>
        </div>
      </div>

      <!-- Signature & Attestation Footer -->
      <div class="report-attestation">
        <div class="attest-col">
          <div class="attest-label">Triage Officer / RN Signature:</div>
          <div class="attest-signature">Verified via Electronic Health Record (EHR)</div>
        </div>
        <div class="attest-col" style="text-align: right;">
          <div class="attest-label">ED Attending Physician Sign-Off:</div>
          <div class="attest-line">__________________________________________</div>
        </div>
      </div>
      <div class="report-disclaimer">
        CONFIDENTIAL MEDICAL RECORD — ST. JUDE HEALTH SYSTEM • FOR PROFESSIONAL CLINICAL USE ONLY
      </div>
    </div>
  `;
}

function closeHandoffModal() {
  document.getElementById('handoffModal').classList.remove('open');
}

function copyHandoffToClipboard() {
  if (currentHandoffRawText) {
    navigator.clipboard.writeText(currentHandoffRawText);
    alert('Physician Handoff text summary copied to clipboard!');
  } else {
    alert('No summary text available to copy.');
  }
}

function printHandoffReport() {
  window.print();
}

function filterQueue() {
  loadPatientQueue();
}

function setFilter(filterType, el) {
  currentFilter = filterType;
  document.querySelectorAll('.filter-pills .pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  loadPatientQueue();
}

function setupIntakeEnterNavigation() {
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.keyCode !== 13) return;

    const intakeSequence = [
      'v_name',
      'v_temp',
      'v_hr',
      'v_rr',
      'v_o2',
      'v_sbp',
      'v_dbp',
      'v_age',
      'v_gender',
      'complaintInput'
    ];

    const activeEl = document.activeElement;
    if (!activeEl) return;

    const activeId = activeEl.id;
    const currentIndex = intakeSequence.indexOf(activeId);

    if (currentIndex === -1) return; // Active element is not in intake sequence

    // In Chief Complaint textarea: Shift+Enter allows newline; Enter triggers triage analysis
    if (activeId === 'complaintInput') {
      if (!e.shiftKey) {
        e.preventDefault();
        executeTriageAnalysis();
      }
      return;
    }

    // Prevent default newline/submit behavior
    e.preventDefault();

    const nextId = intakeSequence[currentIndex + 1];
    if (nextId) {
      const nextEl = document.getElementById(nextId);
      if (nextEl) {
        nextEl.focus();
        if (typeof nextEl.select === 'function' && nextEl.tagName !== 'SELECT') {
          try {
            nextEl.select();
          } catch (err) { }
        }
        nextEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  });
}


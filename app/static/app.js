const ingestBtn = document.getElementById("ingest-btn");
const decisionBtn = document.getElementById("decision-btn");
const vitalsBtn = document.getElementById("vitals-btn");
const ingestStatus = document.getElementById("ingest-status");
const decisionStatus = document.getElementById("decision-status");
const vitalsStatus = document.getElementById("vitals-status");
const recordCard = document.getElementById("record-card");
const recordContent = document.getElementById("record-content");
const decisionCard = document.getElementById("decision-card");
const decisionContent = document.getElementById("decision-content");

let currentPatientId = null;
let currentTab = "text";

function switchTab(tab) {
    currentTab = tab;
    document.getElementById("input-text").classList.toggle("hidden", tab !== "text");
    document.getElementById("input-pdf").classList.toggle("hidden", tab !== "pdf");
    document.getElementById("tab-text").classList.toggle("active", tab === "text");
    document.getElementById("tab-pdf").classList.toggle("active", tab === "pdf");
}

function tagList(items) {
    if (!items || items.length === 0) return "<span class='label'>אין נתונים</span>";
    return `<div class="tag-list">${items.map((i) => `<span class="tag">${escapeHtml(i)}</span>`).join("")}</div>`;
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function field(label, value) {
    return `<div class="field"><div class="label">${label}</div><div>${escapeHtml(value ?? "—")}</div></div>`;
}

function populateVitalsForm(vitals) {
    if (!vitals) return;
    if (vitals.heart_rate) document.getElementById("v-hr").value = vitals.heart_rate;
    if (vitals.blood_pressure_systolic) document.getElementById("v-sys").value = vitals.blood_pressure_systolic;
    if (vitals.blood_pressure_diastolic) document.getElementById("v-dia").value = vitals.blood_pressure_diastolic;
    if (vitals.temperature_celsius) document.getElementById("v-temp").value = vitals.temperature_celsius;
    if (vitals.spo2_percent) document.getElementById("v-spo2").value = vitals.spo2_percent;
    if (vitals.respiratory_rate) document.getElementById("v-rr").value = vitals.respiratory_rate;
}

function renderRecord(record) {
    const vitals = record.vitals || {};
    recordContent.innerHTML = `
        <div class="field-grid">
            ${field("שם מלא", record.full_name)}
            ${field("תאריך לידה", record.date_of_birth)}
            ${field("מגדר", record.gender)}
            ${field("דופק", vitals.heart_rate)}
            ${field("ל\"ד", vitals.blood_pressure_systolic && vitals.blood_pressure_diastolic ? `${vitals.blood_pressure_systolic}/${vitals.blood_pressure_diastolic}` : null)}
            ${field("סטורציה", vitals.spo2_percent ? `${vitals.spo2_percent}%` : null)}
        </div>
        <div class="field"><div class="label">תלונה עיקרית</div><div>${escapeHtml(record.chief_complaint ?? "—")}</div></div>
        <div class="field"><div class="label">תסמינים</div>${tagList(record.symptoms)}</div>
        <div class="field"><div class="label">היסטוריה רפואית</div>${tagList(record.medical_history)}</div>
        <div class="field"><div class="label">תרופות</div>${tagList(record.medications)}</div>
        <div class="field"><div class="label">אלרגיות</div>${tagList(record.allergies)}</div>
    `;
    populateVitalsForm(record.vitals);
}

function renderDecision(result) {
    const flagsHtml = (result.flags || [])
        .map((f) => `<div class="flag ${f.severity}"><span class="severity">${f.severity}</span>${escapeHtml(f.message)}</div>`)
        .join("");
    const listHtml = (items) => `<ul>${(items || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`;

    decisionContent.innerHTML = `
        <div class="field"><div class="label">דגלים</div>${flagsHtml || "<span class='label'>אין דגלים</span>"}</div>
        <div class="field"><div class="label">אבחנה מבדלת</div>${listHtml(result.differential_diagnosis)}</div>
        <div class="field"><div class="label">המלצות פעולה</div>${listHtml(result.recommended_actions)}</div>
        <div class="field"><div class="label">סיכום</div><div>${escapeHtml(result.summary ?? "—")}</div></div>
    `;
}

async function doIngest() {
    const patientId = document.getElementById("patient-id").value.trim();
    if (!patientId) { ingestStatus.textContent = "נא למלא מזהה מטופל"; ingestStatus.classList.add("error"); return; }

    ingestStatus.classList.remove("error");
    ingestStatus.textContent = "מעבד...";
    ingestBtn.disabled = true;
    decisionCard.classList.add("hidden");

    try {
        let res;
        if (currentTab === "pdf") {
            const file = document.getElementById("pdf-file").files[0];
            if (!file) throw new Error("נא לבחור קובץ PDF");
            const arrayBuffer = await file.arrayBuffer();
            const bytes = new Uint8Array(arrayBuffer);
            let binary = "";
            for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
            const base64 = btoa(binary);
            res = await fetch("/ingest/pdf-base64", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ patient_id: patientId, pdf_base64: base64 }),
            });
        } else {
            const text = document.getElementById("raw-text").value.trim();
            if (!text) throw new Error("נא להדביק טקסט רפואי");
            res = await fetch("/ingest/text", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ patient_id: patientId, text }) });
        }

        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const record = await res.json();
        currentPatientId = record.patient_id;
        renderRecord(record);
        recordCard.classList.remove("hidden");
        ingestStatus.textContent = "הופק בהצלחה ✓";
    } catch (err) {
        ingestStatus.textContent = `שגיאה: ${err.message}`;
        ingestStatus.classList.add("error");
    } finally {
        ingestBtn.disabled = false;
    }
}

async function doUpdateVitals() {
    if (!currentPatientId) return;
    vitalsStatus.classList.remove("error");
    vitalsStatus.textContent = "שומר...";
    vitalsBtn.disabled = true;

    const body = {};
    const hr = document.getElementById("v-hr").value;
    const sys = document.getElementById("v-sys").value;
    const dia = document.getElementById("v-dia").value;
    const temp = document.getElementById("v-temp").value;
    const spo2 = document.getElementById("v-spo2").value;
    const rr = document.getElementById("v-rr").value;
    if (hr) body.heart_rate = parseFloat(hr);
    if (sys) body.blood_pressure_systolic = parseFloat(sys);
    if (dia) body.blood_pressure_diastolic = parseFloat(dia);
    if (temp) body.temperature_celsius = parseFloat(temp);
    if (spo2) body.spo2_percent = parseFloat(spo2);
    if (rr) body.respiratory_rate = parseFloat(rr);

    try {
        const res = await fetch(`/patients/${encodeURIComponent(currentPatientId)}/vitals`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const record = await res.json();
        renderRecord(record);
        vitalsStatus.textContent = "מדדים עודכנו ✓";
    } catch (err) {
        vitalsStatus.textContent = `שגיאה: ${err.message}`;
        vitalsStatus.classList.add("error");
    } finally {
        vitalsBtn.disabled = false;
    }
}

async function doDecision() {
    if (!currentPatientId) return;
    decisionStatus.classList.remove("error");
    decisionStatus.textContent = "מריץ סוכן החלטות...";
    decisionBtn.disabled = true;

    try {
        const res = await fetch(`/decision/${encodeURIComponent(currentPatientId)}`, { method: "POST" });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const result = await res.json();
        renderDecision(result);
        decisionCard.classList.remove("hidden");
        decisionStatus.textContent = "";
    } catch (err) {
        decisionStatus.textContent = `שגיאה: ${err.message}`;
        decisionStatus.classList.add("error");
    } finally {
        decisionBtn.disabled = false;
    }
}

ingestBtn.addEventListener("click", doIngest);
vitalsBtn.addEventListener("click", doUpdateVitals);
decisionBtn.addEventListener("click", doDecision);
document.getElementById("tab-text").addEventListener("click", () => switchTab("text"));
document.getElementById("tab-pdf").addEventListener("click", () => switchTab("pdf"));

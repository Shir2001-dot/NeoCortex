const ingestBtn = document.getElementById("ingest-btn");
const decisionBtn = document.getElementById("decision-btn");
const ingestStatus = document.getElementById("ingest-status");
const decisionStatus = document.getElementById("decision-status");
const recordCard = document.getElementById("record-card");
const recordContent = document.getElementById("record-content");
const decisionCard = document.getElementById("decision-card");
const decisionContent = document.getElementById("decision-content");

let currentPatientId = null;

function tagList(items) {
    if (!items || items.length === 0) return "<span class='label'>אין נתונים</span>";
    return `<div class="tag-list">${items.map((i) => `<span class="tag">${escapeHtml(i)}</span>`).join("")}</div>`;
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[c]));
}

function field(label, value) {
    return `<div class="field"><div class="label">${label}</div><div>${escapeHtml(value ?? "—")}</div></div>`;
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
            ${field("חמצן בדם", vitals.spo2_percent)}
        </div>
        <div class="field">
            <div class="label">תלונה עיקרית</div>
            <div>${escapeHtml(record.chief_complaint ?? "—")}</div>
        </div>
        <div class="field">
            <div class="label">תסמינים</div>
            ${tagList(record.symptoms)}
        </div>
        <div class="field">
            <div class="label">היסטוריה רפואית</div>
            ${tagList(record.medical_history)}
        </div>
        <div class="field">
            <div class="label">תרופות</div>
            ${tagList(record.medications)}
        </div>
        <div class="field">
            <div class="label">אלרגיות</div>
            ${tagList(record.allergies)}
        </div>
    `;
}

function renderDecision(result) {
    const flagsHtml = (result.flags || [])
        .map(
            (f) => `<div class="flag ${f.severity}">
                <span class="severity">${f.severity}</span>${escapeHtml(f.message)}
            </div>`
        )
        .join("");

    const listHtml = (items) =>
        `<ul>${(items || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`;

    decisionContent.innerHTML = `
        <div class="field">
            <div class="label">דגלים</div>
            ${flagsHtml || "<span class='label'>אין דגלים</span>"}
        </div>
        <div class="field">
            <div class="label">אבחנה מבדלת</div>
            ${listHtml(result.differential_diagnosis)}
        </div>
        <div class="field">
            <div class="label">המלצות פעולה</div>
            ${listHtml(result.recommended_actions)}
        </div>
        <div class="field">
            <div class="label">סיכום</div>
            <div>${escapeHtml(result.summary ?? "—")}</div>
        </div>
    `;
}

ingestBtn.addEventListener("click", async () => {
    const patientId = document.getElementById("patient-id").value.trim();
    const text = document.getElementById("raw-text").value.trim();

    if (!patientId || !text) {
        ingestStatus.textContent = "נא למלא מזהה מטופל וטקסט רפואי";
        ingestStatus.classList.add("error");
        return;
    }

    ingestStatus.classList.remove("error");
    ingestStatus.textContent = "מעבד...";
    ingestBtn.disabled = true;
    decisionCard.classList.add("hidden");

    try {
        const res = await fetch("/ingest/text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patient_id: patientId, text }),
        });

        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);

        const record = await res.json();
        currentPatientId = record.patient_id;
        renderRecord(record);
        recordCard.classList.remove("hidden");
        ingestStatus.textContent = "הופק בהצלחה";
    } catch (err) {
        ingestStatus.textContent = `שגיאה: ${err.message}`;
        ingestStatus.classList.add("error");
    } finally {
        ingestBtn.disabled = false;
    }
});

decisionBtn.addEventListener("click", async () => {
    if (!currentPatientId) return;

    decisionStatus.classList.remove("error");
    decisionStatus.textContent = "מריץ סוכן החלטות...";
    decisionBtn.disabled = true;

    try {
        const res = await fetch(`/decision/${encodeURIComponent(currentPatientId)}`, {
            method: "POST",
        });

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
});

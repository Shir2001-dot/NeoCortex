// ─── Elements ───
const ingestBtn   = document.getElementById("ingest-btn");
const decisionBtn = document.getElementById("decision-btn");
const vitalsBtn   = document.getElementById("vitals-btn");
const recordCard  = document.getElementById("record-card");
const decisionCard = document.getElementById("decision-card");
const recordContent = document.getElementById("record-content");
const decisionContent = document.getElementById("decision-content");
const timelineSection = document.getElementById("timeline-section");
const timelineContent = document.getElementById("timeline-content");

let currentPatientId = null;
let currentTab = "text";

// ─── Tab switch ───
document.getElementById("tab-text").addEventListener("click", () => switchTab("text"));
document.getElementById("tab-pdf").addEventListener("click",  () => switchTab("pdf"));

function switchTab(tab) {
    currentTab = tab;
    document.getElementById("input-text").classList.toggle("hidden", tab !== "text");
    document.getElementById("input-pdf").classList.toggle("hidden", tab !== "pdf");
    document.getElementById("tab-text").classList.toggle("active", tab === "text");
    document.getElementById("tab-pdf").classList.toggle("active", tab === "pdf");
}

// ─── Stepper ───
function setStep(n) {
    [1,2,3].forEach(i => {
        const el = document.getElementById("step" + i);
        el.classList.remove("active","done");
        if (i < n)  el.classList.add("done");
        if (i === n) el.classList.add("active");
    });
}

// ─── Helpers ───
function esc(str) {
    return String(str ?? "").replace(/[&<>"']/g, c =>
        ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function setStatus(prefix, msg, type="") {
    const el = document.getElementById(prefix + "-msg");
    const sp = document.getElementById(prefix + "-spinner");
    if (el) { el.textContent = msg; el.className = type; }
    if (sp) sp.classList.toggle("visible", type === "loading");
}

function tagList(items) {
    if (!items?.length) return "<span style='color:var(--muted);font-size:.85rem'>אין נתונים</span>";
    return `<div class="tag-list">${items.map(i=>`<span class="tag">${esc(i)}</span>`).join("")}</div>`;
}

const TX_TYPE_LABELS = {
    referral: "הפניה",
    hospitalization: "אשפוז",
    visit: "ביקור",
    test: "בדיקה",
};

const TX_TYPE_COLORS = {
    referral: "badge-referral",
    hospitalization: "badge-hospitalization",
    visit: "badge-visit",
    test: "badge-test",
};

// ─── Render patient record ───
function renderRecord(r) {
    const v = r.vitals || {};
    const bp = v.blood_pressure_systolic && v.blood_pressure_diastolic
        ? `${v.blood_pressure_systolic}/${v.blood_pressure_diastolic} mmHg`
        : "—";

    recordContent.innerHTML = `
        <div class="info-grid" style="margin-bottom:1rem">
            ${infoCell("שם מלא", r.full_name)}
            ${infoCell("תאריך לידה", r.date_of_birth)}
            ${infoCell("מגדר", r.gender)}
            ${infoCell("דופק", v.heart_rate ? v.heart_rate + " bpm" : null)}
            ${infoCell('ל"ד', bp)}
            ${infoCell("סטורציה", v.spo2_percent ? v.spo2_percent + "%" : null)}
        </div>
        <table class="clinical-table" style="border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:1rem">
            ${clinicalRow("תלונה עיקרית", esc(r.chief_complaint) || "—")}
            ${clinicalRow("תסמינים", tagList(r.symptoms))}
            ${clinicalRow("היסטוריה רפואית", tagList(r.medical_history))}
            ${clinicalRow("תרופות", tagList(r.medications))}
            ${clinicalRow("אלרגיות", tagList(r.allergies))}
        </table>
    `;
    populateVitals(r.vitals);
}

function clinicalRow(label, valueHtml) {
    return `<tr>
        <td class="ct-label">${label}</td>
        <td class="ct-value">${valueHtml}</td>
    </tr>`;
}

function infoCell(lbl, val) {
    return `<div class="info-cell"><div class="lbl">${lbl}</div><div class="val">${esc(val) || "—"}</div></div>`;
}

function populateVitals(v) {
    if (!v) return;
    if (v.heart_rate)               document.getElementById("v-hr").value   = v.heart_rate;
    if (v.blood_pressure_systolic)  document.getElementById("v-sys").value  = v.blood_pressure_systolic;
    if (v.blood_pressure_diastolic) document.getElementById("v-dia").value  = v.blood_pressure_diastolic;
    if (v.temperature_celsius)      document.getElementById("v-temp").value = v.temperature_celsius;
    if (v.spo2_percent)             document.getElementById("v-spo2").value = v.spo2_percent;
    if (v.respiratory_rate)         document.getElementById("v-rr").value   = v.respiratory_rate;
}

// ─── Render transaction timeline ───
function renderTimeline(transactions, currentTxId) {
    if (!transactions || transactions.length === 0) {
        timelineSection.classList.add("hidden");
        return;
    }
    timelineSection.classList.remove("hidden");
    timelineContent.innerHTML = transactions.map((tx, idx) => {
        const isCurrent = tx.transaction_id === currentTxId;
        const label = TX_TYPE_LABELS[tx.transaction_type] || tx.transaction_type;
        const colorClass = TX_TYPE_COLORS[tx.transaction_type] || "badge-referral";
        const complaint = tx.extracted?.chief_complaint || "—";
        return `
            <div class="timeline-item${isCurrent ? " timeline-current" : ""}">
                <div class="timeline-dot${isCurrent ? " timeline-dot-current" : ""}"></div>
                <div class="timeline-body">
                    <div class="timeline-header">
                        <span class="timeline-date">${esc(tx.date)}</span>
                        <span class="tx-badge ${colorClass}">${esc(label)}</span>
                        ${isCurrent ? '<span class="current-badge">נוכחי</span>' : ""}
                    </div>
                    <div class="timeline-complaint">${esc(complaint)}</div>
                </div>
            </div>
        `;
    }).join("");
}

// ─── Render decision ───
function renderDecision(result) {
    const flags = (result.flags || []).map(f => `
        <div class="flag ${f.severity}">
            <div class="flag-dot"></div>
            <div class="flag-body">
                <div class="flag-severity">${esc(f.severity)}</div>
                <div class="flag-msg">${esc(f.message)}</div>
            </div>
        </div>`).join("");

    const dxItems = (result.differential_diagnosis || [])
        .map(d => `<li>${esc(d)}</li>`).join("");

    const actionItems = (result.recommended_actions || [])
        .map(a => `<li>${esc(a)}</li>`).join("");

    decisionContent.innerHTML = `
        <div class="section-title">דגלים קליניים</div>
        ${flags || "<p style='color:var(--muted);font-size:.88rem'>אין דגלים</p>"}
        <div class="section-title" style="margin-top:1.25rem">אבחנה מבדלת</div>
        <ul class="dx-list">${dxItems}</ul>
        <div class="section-title" style="margin-top:1.25rem">המלצות פעולה</div>
        <ul class="action-list">${actionItems}</ul>
        <div class="section-title" style="margin-top:1.25rem">סיכום קליני</div>
        <div class="summary-box">${esc(result.summary)}</div>
    `;
}


// ─── Ingest ───
ingestBtn.addEventListener("click", async () => {
    const patientId = "auto-" + Date.now();

    setStatus("ingest","מעבד מסמך...","loading");
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
            res = await fetch(location.origin + "/ingest/pdf-base64", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({patient_id: patientId, pdf_base64: base64}),
            });
        } else {
            const text = document.getElementById("raw-text").value.trim();
            if (!text) throw new Error("נא להדביק טקסט רפואי");
            res = await fetch("/ingest/text", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({patient_id: patientId, text}),
            });
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `שגיאת שרת (${res.status})`);
        }

        const tx = await res.json();
        currentPatientId = tx.patient_id;
        renderRecord(tx.extracted);
        recordCard.classList.remove("hidden");
        setStep(2);
        setStatus("ingest","הופק בהצלחה ✓","success");

        // Load full transaction history
        try {
            const txRes = await fetch(`/patients/${encodeURIComponent(currentPatientId)}/transactions`);
            if (txRes.ok) {
                const transactions = await txRes.json();
                renderTimeline(transactions, tx.transaction_id);
            }
        } catch(e) { /* non-critical */ }

    } catch (e) {
        setStatus("ingest", e.message, "error");
    } finally {
        ingestBtn.disabled = false;
    }
});

// ─── Vitals ───
vitalsBtn.addEventListener("click", async () => {
    if (!currentPatientId) return;
    setStatus("vitals","שומר...","loading");
    vitalsBtn.disabled = true;

    const body = {};
    const map = {hr:"heart_rate",sys:"blood_pressure_systolic",dia:"blood_pressure_diastolic",temp:"temperature_celsius",spo2:"spo2_percent",rr:"respiratory_rate"};
    for (const [id, key] of Object.entries(map)) {
        const v = document.getElementById("v-"+id).value;
        if (v) body[key] = parseFloat(v);
    }

    try {
        const res = await fetch(`/patients/${encodeURIComponent(currentPatientId)}/vitals`, {
            method: "PATCH",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const record = await res.json();
        renderRecord(record);
        setStatus("vitals","מדדים עודכנו ✓","success");
    } catch (e) {
        setStatus("vitals", e.message, "error");
    } finally {
        vitalsBtn.disabled = false;
    }
});

// ─── Decision ───
decisionBtn.addEventListener("click", async () => {
    if (!currentPatientId) return;
    setStatus("decision","מנתח נתונים קליניים...","loading");
    decisionBtn.disabled = true;

    try {
        const res = await fetch(`/decision/${encodeURIComponent(currentPatientId)}`, {method:"POST"});
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const result = await res.json();
        renderDecision(result);
        decisionCard.classList.remove("hidden");
        setStep(3);
        setStatus("decision","","");
    } catch (e) {
        setStatus("decision", e.message, "error");
    } finally {
        decisionBtn.disabled = false;
    }
});

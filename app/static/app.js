// ─── Elements ───
const ingestBtn       = document.getElementById("ingest-btn");
const decisionBtn     = document.getElementById("decision-btn");
const vitalsBtn       = document.getElementById("vitals-btn");
const interactionsBtn = document.getElementById("interactions-btn");
const validityBtn     = document.getElementById("validity-btn");
const dischargeBtn    = document.getElementById("discharge-btn");
const printBtn        = document.getElementById("print-btn");
const searchBtn       = document.getElementById("search-btn");
const decisionCard        = document.getElementById("decision-card");
const interactionsCard    = document.getElementById("interactions-card");
const recordContent       = document.getElementById("record-content");
const decisionContent     = document.getElementById("decision-content");
const interactionsContent = document.getElementById("interactions-content");

let currentPatientId = null;
let currentPatientInternalId = null;
let currentRecord = null;

// ─── Auto-logout after 15 minutes inactivity ───
const INACTIVITY_MS = 15 * 60 * 1000;
const WARN_MS       = 14 * 60 * 1000;
let inactivityTimer, warnTimer;

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    clearTimeout(warnTimer);
    const warning = document.getElementById("inactivity-warning");
    if (warning) warning.classList.add("hidden");

    warnTimer = setTimeout(() => {
        const w = document.getElementById("inactivity-warning");
        if (w) w.classList.remove("hidden");
    }, WARN_MS);

    inactivityTimer = setTimeout(async () => {
        await fetch("/auth/logout", { method: "POST", credentials: "include" });
        location.href = "/login";
    }, INACTIVITY_MS);
}

["mousemove", "keydown", "click", "scroll", "touchstart"].forEach(evt =>
    document.addEventListener(evt, resetInactivityTimer, { passive: true })
);
resetInactivityTimer();

let currentTab = "text";

function networkErrMsg(e) {
    if (!e.message || e.message === "Failed to fetch" || e.name === "TypeError")
        return "השרת לא זמין — נסה שוב בעוד מספר שניות";
    return e.message;
}

// ─── Sidebar Navigation ───
function showView(viewName) {
    document.querySelectorAll(".view").forEach(v => v.classList.add("hidden"));
    document.querySelectorAll(".sidebar-item").forEach(b => b.classList.remove("active"));
    const view = document.getElementById("view-" + viewName);
    if (view) view.classList.remove("hidden");
    const btn = document.getElementById("nav-" + viewName);
    if (btn) btn.classList.add("active");
}

document.querySelectorAll(".sidebar-item[data-view]").forEach(btn => {
    btn.addEventListener("click", () => showView(btn.dataset.view));
});

function unlockClinicalNav(patientId) {
    document.querySelectorAll(".sidebar-clinical").forEach(el => el.classList.remove("hidden"));
    document.getElementById("sidebar-patient").classList.remove("hidden");
}

function updateSidebarPatient(name, id) {
    document.getElementById("sidebar-patient-name").textContent = name || "—";
    document.getElementById("sidebar-patient-id").textContent = id || "";
}

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

function conditionList(items) {
    if (!items?.length) return "<span style='color:var(--muted);font-size:.85rem'>אין נתונים</span>";
    return `<div class="tag-list">${items.map((c, i) => {
        const name = typeof c === 'string' ? c : c.name;
        const active = typeof c === 'string' ? true : c.active;
        const date = typeof c === 'object' && c.onset_date ? ` (${esc(c.onset_date)})` : "";
        const style = active ? "" : "color:#9ca3af;text-decoration:line-through;opacity:.7";
        return `<span class="tag" style="${style}" title="${active ? 'לחץ לסימון כהיסטורי' : 'לחץ לסימון כפעיל'}" data-condition-idx="${i}" onclick="toggleCondition(${i})">${esc(name)}${date}</span>`;
    }).join("")}</div>`;
}

async function toggleCondition(idx) {
    if (!currentRecord || !currentRecord.medical_history) return;
    const cond = currentRecord.medical_history[idx];
    if (!cond || typeof cond === 'string') return;
    cond.active = !cond.active;
    const conditionsUrl = currentPatientInternalId
        ? `/p/${encodeURIComponent(currentPatientInternalId)}/conditions`
        : `/patients/${encodeURIComponent(currentPatientId)}/conditions`;
    try {
        const res = await fetch(conditionsUrl, {
            method: "PATCH",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({conditions: currentRecord.medical_history}),
            credentials: "include",
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const updated = await res.json();
        currentRecord = updated;
        renderRecord(updated);
    } catch (e) {
        // Revert on error
        cond.active = !cond.active;
        console.error(e);
    }
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
        <table class="clinical-table" style="border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:1rem">
            ${clinicalRow("שם מלא", `<span id="patient-name-display" style="cursor:pointer;border-bottom:1px dashed var(--border)" title="לחץ לעריכה" onclick="editPatientName(this)">${esc(r.full_name) || "—"}</span>`)}
            ${clinicalRow("תאריך לידה", `<span style="white-space:nowrap">${esc(r.date_of_birth) || "—"}</span>`)}
            ${clinicalRow("מגדר", esc(r.gender) || "—")}
            ${v.heart_rate ? clinicalRow("דופק", v.heart_rate + " bpm") : ""}
            ${v.blood_pressure_systolic ? clinicalRow('ל"ד', bp) : ""}
            ${v.spo2_percent ? clinicalRow("חמצן בדם SpO2", v.spo2_percent + "%") : ""}
        </table>
        <table class="clinical-table" style="border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:1rem">
            ${clinicalRow("תלונה עיקרית", esc(r.chief_complaint) || "—")}
            ${clinicalRow("תסמינים", tagList(r.symptoms))}
            ${clinicalRow("היסטוריה רפואית", conditionList(r.medical_history))}
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


// ─── Render decision ───
function renderDelta(delta) {
    if (!delta) return "";
    const rows = [
        ["תרופות חדשות", delta.new_medications],
        ["תרופות שהופסקו", delta.removed_medications],
        ["תסמינים חדשים", delta.new_symptoms],
        ["תסמינים שנפתרו", delta.resolved_symptoms],
        ["שינויים במדדים", delta.changed_vitals],
    ].filter(([_, items]) => items?.length);
    if (!rows.length) return "";
    return `<div class="delta-box">${rows.map(([l,items])=>`<div><strong>${l}:</strong> ${items.map(esc).join(", ")}</div>`).join("")}</div>`;
}

function renderDecision(result) {
    const sortedFlags = (result.flags || []).slice().sort((a, b) => {
        if (a.relevance === "urgent" && b.relevance !== "urgent") return -1;
        if (a.relevance !== "urgent" && b.relevance === "urgent") return 1;
        return 0;
    });

    const flags = sortedFlags.map(f => `
        <div class="flag ${f.severity}${f.relevance === 'urgent' ? ' flag-urgent' : ''}">
            <div class="flag-dot"></div>
            <div class="flag-body">
                ${f.relevance === 'urgent' ? '<span class="flag-relevance-badge">דחוף</span>' : ''}
                <div class="flag-severity">${esc(f.severity)}</div>
                <div class="flag-msg">${esc(f.message)}</div>
            </div>
        </div>`).join("");

    const dxItems = (result.differential_diagnosis || [])
        .map(d => `<li>${esc(d)}</li>`).join("");

    const actionItems = (result.recommended_actions || [])
        .map(a => `<li>${esc(a)}</li>`).join("");

    const icdCodes = result.icd_codes || [];
    const icdHtml = icdCodes.length
        ? `<div class="section-title" style="margin-top:1.25rem">קודי ICD-10</div>
           <div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.4rem">${icdCodes.map(c =>
               `<span style="background:#eff6ff;border:1px solid #bfdbfe;color:#1e40af;border-radius:6px;padding:.15rem .55rem;font-size:.8rem;font-family:monospace;font-weight:600">${esc(c)}</span>`
           ).join("")}</div>`
        : "";

    decisionContent.innerHTML = `
        ${renderDelta(result.visit_delta)}
        <div class="section-title">דגלים קליניים</div>
        ${flags || "<p style='color:var(--muted);font-size:.88rem'>אין דגלים</p>"}
        <div class="section-title" style="margin-top:1.25rem">אבחנה מבדלת</div>
        <ul class="dx-list">${dxItems}</ul>
        <div class="section-title" style="margin-top:1.25rem">המלצות פעולה</div>
        <ul class="action-list">${actionItems}</ul>
        <div class="section-title" style="margin-top:1.25rem">סיכום קליני</div>
        <div class="summary-box">${esc(result.summary)}</div>
        ${icdHtml}
    `;
}


// ─── Ingest ───
ingestBtn.addEventListener("click", async () => {
    const patientId = "auto-" + Date.now();
    ingestBtn.disabled = true;
    decisionCard.classList.add("hidden");

    // Step-by-step progress messages
    const isPdf = currentTab === "pdf";
    const steps = isPdf
        ? [
            [0,    "קורא קובץ PDF..."],
            [1500, "שולח מסמך לשרת..."],
            [3500, "AI מנתח את המסמך הרפואי..."],
            [8000, "מחלץ אבחנות, תרופות ומדדים..."],
            [14000,"מסיים עיבוד נתונים קליניים..."],
          ]
        : [
            [0,    "שולח טקסט לניתוח..."],
            [2000, "AI מנתח את המסמך הרפואי..."],
            [7000, "מחלץ אבחנות, תרופות ומדדים..."],
            [13000,"מסיים עיבוד נתונים קליניים..."],
          ];

    const timers = steps.map(([delay, msg]) =>
        setTimeout(() => setStatus("ingest", msg, "loading"), delay)
    );
    const clearTimers = () => timers.forEach(clearTimeout);

    try {
        let res;
        if (isPdf) {
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

        clearTimers();
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `שגיאת שרת (${res.status})`);
        }

        const tx = await res.json();
        currentPatientId = tx.patient_id;
        currentPatientInternalId = tx.extracted.internal_id || null;
        currentRecord = tx.extracted;
        const titleEl = document.getElementById("record-card-title");
        if (titleEl) titleEl.textContent = `תיק מטופל · ${tx.extracted?.full_name || tx.patient_id}`;
        renderRecord(tx.extracted);
        unlockClinicalNav(tx.patient_id);
        updateSidebarPatient(tx.extracted.full_name, tx.patient_id);
        showView("record");
        setStatus("ingest", "✓ המסמך עובד בהצלחה", "success");

    } catch (e) {
        clearTimers();
        setStatus("ingest", networkErrMsg(e), "error");
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
        const vitalsUrl = currentPatientInternalId
            ? `/p/${encodeURIComponent(currentPatientInternalId)}/vitals`
            : `/patients/${encodeURIComponent(currentPatientId)}/vitals`;
        const res = await fetch(vitalsUrl, {
            method: "PATCH",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify(body),
            credentials: "include",
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

// ─── Voice Recording ───
let recognition = null;
let isRecording = false;

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;
    const r = new SpeechRecognition();
    r.lang = "he-IL";
    r.continuous = true;
    r.interimResults = true;
    return r;
}

function setMicState(recording) {
    isRecording = recording;
    const btn = document.getElementById("mic-btn");
    const lbl = document.getElementById("mic-label");
    const status = document.getElementById("mic-status");
    if (recording) {
        btn.style.borderColor = "#dc2626";
        btn.style.color = "#dc2626";
        btn.style.background = "#fef2f2";
        lbl.textContent = "עצור";
        status.textContent = "🔴 מקליט... דבר בעברית";
    } else {
        btn.style.borderColor = "";
        btn.style.color = "";
        btn.style.background = "";
        lbl.textContent = "הקלט";
        status.textContent = "";
    }
}

document.getElementById("mic-btn").addEventListener("click", () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        document.getElementById("mic-status").textContent = "הדפדפן לא תומך בהקלטה קולית. השתמש ב-Chrome.";
        return;
    }

    if (isRecording && recognition) {
        recognition.stop();
        return;
    }

    recognition = initSpeechRecognition();
    const notesEl = document.getElementById("summary-notes");
    let interim = "";

    recognition.onresult = (e) => {
        let finalChunk = "";
        interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) finalChunk += e.results[i][0].transcript;
            else interim += e.results[i][0].transcript;
        }
        if (finalChunk) {
            notesEl.value += (notesEl.value ? " " : "") + finalChunk;
        }
        document.getElementById("mic-status").textContent = interim
            ? `🔴 מקליט... ${interim}`
            : "🔴 מקליט... דבר בעברית";
    };

    recognition.onend = () => setMicState(false);
    recognition.onerror = (e) => {
        setMicState(false);
        document.getElementById("mic-status").textContent = `שגיאת הקלטה: ${e.error}`;
    };

    recognition.start();
    setMicState(true);
});

// ─── Session Summary Panel ───
// Summary is now opened via the sidebar nav (showView("summary"))

document.getElementById("summary-generate-btn").addEventListener("click", async () => {
    const notes = document.getElementById("summary-notes").value.trim();
    if (!notes) { setStatus("summary", "נא להכניס הערות מהפגישה", "error"); return; }

    setStatus("summary", "מייצר סיכום...", "loading");
    document.getElementById("summary-generate-btn").disabled = true;

    try {
        const summaryUrl = currentPatientInternalId
            ? `/p/${encodeURIComponent(currentPatientInternalId)}/session-summary`
            : `/patients/${encodeURIComponent(currentPatientId)}/session-summary`;
        const res = await fetch(summaryUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ notes }),
            credentials: "include",
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const data = await res.json();
        document.getElementById("summary-text").textContent = data.summary;
        document.getElementById("doc-patient-name").textContent = "מטופל: " + (currentRecord?.full_name || "—");
        document.getElementById("doc-date").textContent = "תאריך: " + new Date().toLocaleDateString("he-IL");
        document.getElementById("summary-result").classList.remove("hidden");
        document.getElementById("save-summary-msg").textContent = "";
        setStatus("summary", "", "");
        setTimeout(() => {
            document.getElementById("summary-result").scrollIntoView({ behavior: "smooth", block: "start" });
        }, 100);
    } catch (e) {
        setStatus("summary", networkErrMsg(e), "error");
    } finally {
        document.getElementById("summary-generate-btn").disabled = false;
    }
});

document.getElementById("summary-copy-btn").addEventListener("click", () => {
    const text = document.getElementById("summary-text").innerText;
    navigator.clipboard.writeText(text).then(() => {
        document.getElementById("summary-copy-btn").textContent = "✓ הועתק";
        setTimeout(() => { document.getElementById("summary-copy-btn").textContent = "📋 העתק"; }, 2000);
    });
});

document.getElementById("summary-save-btn").addEventListener("click", async () => {
    const summary = document.getElementById("summary-text").innerText;
    const doctorName = document.getElementById("doctor-name").value.trim();
    if (!summary) return;

    document.getElementById("summary-save-btn").disabled = true;
    document.getElementById("save-summary-msg").textContent = "שומר...";
    document.getElementById("save-summary-msg").className = "loading";

    try {
        const saveSummaryUrl = currentPatientInternalId
            ? `/p/${encodeURIComponent(currentPatientInternalId)}/save-summary`
            : `/patients/${encodeURIComponent(currentPatientId)}/save-summary`;
        const res = await fetch(saveSummaryUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ summary, doctor_name: doctorName || null }),
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        document.getElementById("save-summary-msg").textContent = "✓ נשמר בתיק המטופל";
        document.getElementById("save-summary-msg").className = "success";
    } catch (e) {
        document.getElementById("save-summary-msg").textContent = networkErrMsg(e);
        document.getElementById("save-summary-msg").className = "error";
    } finally {
        document.getElementById("summary-save-btn").disabled = false;
    }
});

// ─── Medication Validity ───
const VALIDITY_COLORS = { "דורש בדיקה": "warning", "בתוקף": "info", "פג תוקף": "critical", "לאימות": "warning", "לחידוש מרשם": "warning" };
const VALIDITY_ICONS  = { "דורש בדיקה": "🟡", "בתוקף": "🟢", "פג תוקף": "🔴", "לאימות": "🟡", "לחידוש מרשם": "🟡" };

validityBtn?.addEventListener("click", async () => {
    if (!currentPatientInternalId) return;
    setStatus("validity", "בודק תוקף מרשמים...", "loading");
    validityBtn.disabled = true;
    document.getElementById("validity-content").innerHTML = "";
    try {
        const res = await fetch(`/p/${encodeURIComponent(currentPatientInternalId)}/medication-validity`, {
            method: "POST", credentials: "include"
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const result = await res.json();
        setStatus("validity", "", "");
        const items = result.medications || [];
        if (!items.length) {
            document.getElementById("validity-content").innerHTML = "<p style='color:var(--success)'>✓ לא נמצאו תרופות לבדיקה</p>";
            return;
        }
        document.getElementById("validity-content").innerHTML = items.map(item => `
            <div class="flag ${esc(VALIDITY_COLORS[item.status] || 'info')}" style="margin-bottom:.6rem">
                <div class="flag-dot"></div>
                <div class="flag-body">
                    <div style="font-weight:700;margin-bottom:.2rem">${VALIDITY_ICONS[item.status] || ''} ${esc(item.name)}</div>
                    <div style="font-size:.8rem;color:var(--text-secondary);margin-bottom:.2rem">
                        <span style="background:#f3f4f6;padding:.1rem .4rem;border-radius:3px;margin-left:.4rem">${esc(item.category)}</span>
                        <span style="background:#f3f4f6;padding:.1rem .4rem;border-radius:3px">${esc(item.status)}</span>
                    </div>
                    <div class="flag-msg">${esc(item.message)}</div>
                    ${item.patient_question ? `<div style="margin-top:.4rem;padding:.4rem .6rem;background:#eff6ff;border-radius:6px;font-size:.78rem;color:#1e40af;border-right:3px solid #3b82f6">
                        💬 <strong>שאל את המטופל:</strong> ${esc(item.patient_question)}
                    </div>` : ''}
                </div>
            </div>`).join("");
    } catch(e) {
        setStatus("validity", networkErrMsg(e), "error");
    } finally {
        validityBtn.disabled = false;
    }
});

// ─── Print / PDF Export ───
printBtn.addEventListener("click", () => {
    if (!currentPatientId) return;
    const printUrl = currentPatientInternalId
        ? `/p/${encodeURIComponent(currentPatientInternalId)}/print`
        : `/patients/${encodeURIComponent(currentPatientId)}/print`;
    window.open(printUrl, "_blank");
});

// ─── Patient Search ───
function renderSearchResults(patients, resultsEl) {
    if (!patients.length) {
        resultsEl.innerHTML = `<div class="search-results"><div class="search-empty">לא נמצאו מטופלים</div></div>`;
        return;
    }
    resultsEl.innerHTML = `<div class="search-results">${patients.map(p => {
        const meds = (p.medications || []).slice(0, 3).join(", ");
        const history = (p.medical_history || []).slice(0, 2).map(c => c.name || c).join(", ");
        return `<div class="search-item" data-id="${esc(p.patient_id)}" data-internal="${esc(p.internal_id||'')}">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span class="search-item-name">${esc(p.full_name || "ללא שם")}</span>
                <span class="search-item-id">${esc(p.patient_id)}</span>
            </div>
            ${meds ? `<div style="font-size:.74rem;color:var(--muted);margin-top:.2rem">💊 ${esc(meds)}</div>` : ""}
            ${history ? `<div style="font-size:.74rem;color:var(--muted)">🏥 ${esc(history)}</div>` : ""}
        </div>`;
    }).join("")}</div>`;

    resultsEl.querySelectorAll(".search-item").forEach(item => {
        item.addEventListener("click", async () => {
            const pid = item.dataset.id;
            try {
                const recRes = await fetch(`/patients/${encodeURIComponent(pid)}`, { credentials: "include" });
                if (!recRes.ok) throw new Error("מטופל לא נמצא");
                const record = await recRes.json();
                currentPatientId = pid;
                currentPatientInternalId = record.internal_id || null;
                currentRecord = record;
                const titleEl = document.getElementById("record-card-title");
                if (titleEl) titleEl.textContent = `תיק מטופל · ${record.full_name || pid}`;
                renderRecord(record);
                unlockClinicalNav(pid);
                updateSidebarPatient(record.full_name, pid);
                showView("record");
                resultsEl.innerHTML = "";
                document.getElementById("search-input").value = "";
            } catch(e) {
                resultsEl.innerHTML = `<div class="search-results"><div class="search-empty">${esc(e.message)}</div></div>`;
            }
        });
    });
}

searchBtn.addEventListener("click", async () => {
    const query = document.getElementById("search-input").value.trim();
    const resultsEl = document.getElementById("search-results");
    if (!query) { resultsEl.innerHTML = ""; return; }

    resultsEl.innerHTML = `<div style="color:var(--muted);font-size:.85rem;padding:.5rem">מחפש...</div>`;
    try {
        const res = await fetch(`/patients/search?q=${encodeURIComponent(query)}`, { credentials: "include" });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const patients = await res.json();
        renderSearchResults(patients, resultsEl);
    } catch(e) {
        resultsEl.innerHTML = `<div class="search-results"><div class="search-empty">${esc(e.message)}</div></div>`;
    }
});

document.getElementById("search-input").addEventListener("keydown", e => {
    if (e.key === "Enter") searchBtn.click();
});

// ─── Excel Export ───
const exportExcelBtn = document.getElementById("export-excel-btn");
if (exportExcelBtn) {
    exportExcelBtn.addEventListener("click", async () => {
        exportExcelBtn.disabled = true;
        exportExcelBtn.textContent = "⏳ מייצא...";
        try {
            const res = await fetch("/patients/export/excel", { credentials: "include" });
            if (!res.ok) throw new Error(`שגיאה (${res.status})`);
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `neocortex_patients_${new Date().toISOString().slice(0,10)}.xlsx`;
            a.click();
            URL.revokeObjectURL(url);
        } catch(e) {
            alert("שגיאה בייצוא: " + e.message);
        } finally {
            exportExcelBtn.disabled = false;
            exportExcelBtn.textContent = "📊 ייצוא Excel";
        }
    });
}

// ─── Drug Interactions ───
interactionsBtn.addEventListener("click", async () => {
    if (!currentPatientId) return;
    interactionsCard.classList.remove("hidden");
    setStatus("interactions", "בודק אינטראקציות תרופות...", "loading");
    interactionsBtn.disabled = true;
    interactionsContent.innerHTML = "";

    try {
        const interactionsUrl = currentPatientInternalId
            ? `/p/${encodeURIComponent(currentPatientInternalId)}/interactions`
            : `/patients/${encodeURIComponent(currentPatientId)}/interactions`;
        const res = await fetch(interactionsUrl, {
            method: "POST",
            credentials: "include",
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `שגיאת שרת (${res.status})`);
        }
        const result = await res.json();
        setStatus("interactions", "", "");
        renderInteractions(result);
    } catch(e) {
        setStatus("interactions", networkErrMsg(e), "error");
    } finally {
        interactionsBtn.disabled = false;
    }
});

function renderInteractions(result) {
    const items = result.interactions || [];
    if (items.length === 0) {
        interactionsContent.innerHTML = `<p style="color:var(--success);font-size:.9rem;margin-top:.5rem">✓ לא נמצאו אינטראקציות תרופתיות ידועות</p>`;
        return;
    }
    interactionsContent.innerHTML = items.map(item => `
        <div class="flag ${esc(item.severity)}">
            <div class="flag-dot"></div>
            <div class="flag-body">
                <div class="flag-severity">${esc(item.severity)}</div>
                <div style="font-size:.82rem;color:var(--text-secondary);margin-bottom:.25rem;font-weight:600">${item.drugs.map(d => esc(d)).join(" + ")}</div>
                <div class="flag-msg">${esc(item.description)}</div>
                ${item.mechanism ? `<div style="font-size:.8rem;color:var(--text-secondary);margin-top:.35rem"><strong>מנגנון:</strong> ${esc(item.mechanism)}</div>` : ""}
                ${item.clinical_context ? `<div style="font-size:.8rem;color:var(--text-secondary);margin-top:.25rem"><strong>הקשר קליני:</strong> ${esc(item.clinical_context)}</div>` : ""}
                <div style="font-size:.72rem;color:var(--muted);margin-top:.4rem;font-style:italic;border-top:1px solid var(--border);padding-top:.3rem">מידע זה מבוסס על מקורות רפואיים מוכרים ואינו מחליף שיקול דעת קליני</div>
            </div>
        </div>
    `).join("");
}

// ─── Decision ───
decisionBtn.addEventListener("click", async () => {
    if (!currentPatientId) return;
    setStatus("decision","מנתח נתונים קליניים...","loading");
    decisionBtn.disabled = true;

    try {
        const decisionUrl = currentPatientInternalId
            ? `/p/${encodeURIComponent(currentPatientInternalId)}/decision`
            : `/decision/${encodeURIComponent(currentPatientId)}`;
        const res = await fetch(decisionUrl, {method:"POST", credentials:"include"});
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const result = await res.json();
        renderDecision(result);
        decisionCard.classList.remove("hidden");
        setStatus("decision","","");
    } catch (e) {
        setStatus("decision", networkErrMsg(e), "error");
    } finally {
        decisionBtn.disabled = false;
    }
});

// ─── Auth / Header + Role-based UI ───
let currentUser = null;

(async () => {
    try {
        const res = await fetch("/auth/me", {credentials: "include"});
        if (res.status === 401) { location.href = "/login"; return; }
        if (!res.ok) return;
        currentUser = await res.json();

        const nameEl = document.getElementById("header-user-name");
        const roleEl = document.getElementById("header-user-role");
        const adminLink = document.getElementById("admin-link");
        if (nameEl) nameEl.textContent = currentUser.full_name || "";
        if (roleEl) {
            const roleMap = { doctor: "רופא", admin: "מנהל", secretary: "מזכירה", nurse: "אחות", intern: "רופא מתמחה" };
            const roleLabel = roleMap[currentUser.role] || currentUser.role;
            roleEl.textContent = currentUser.specialty ? `${roleLabel} · ${currentUser.specialty}` : roleLabel;
        }

        const role = currentUser.role;

        // Admin → redirect to admin panel
        if (role === "admin") {
            location.href = "/admin";
            return;
        }

        // Secretary → hide everything clinical, show read-only patient list
        if (role === "secretary") {
            applySecretaryView();
            return;
        }

        // Doctor/nurse/intern → apply permission-based UI
        applyPermissions(currentUser.permissions || []);


    } catch(e) { /* ignore */ }
})();

function applyPermissions(perms) {
    const has = p => perms.includes(p);

    // Hide ingest card if no edit_records
    if (!has("edit_records")) {
        const ingestCard = document.querySelector(".card:has(#ingest-btn)");
        if (ingestCard) ingestCard.style.display = "none";
    }

    // Hide vitals save button if no edit_records
    if (!has("edit_records")) {
        const vitalsBtn = document.getElementById("vitals-btn");
        if (vitalsBtn) vitalsBtn.style.display = "none";
    }

    // Hide clinical analysis if no permission
    if (!has("clinical_analysis")) {
        const decisionBtn = document.getElementById("decision-btn");
        if (decisionBtn) decisionBtn.style.display = "none";
    }

    // Hide drug interactions if no permission
    if (!has("drug_interactions")) {
        const interactionsBtn = document.getElementById("interactions-btn");
        if (interactionsBtn) interactionsBtn.style.display = "none";
    }

    // Hide session summary if no permission
    if (!has("session_summary")) {
        const summaryBtn = document.getElementById("summary-btn");
        if (summaryBtn) summaryBtn.style.display = "none";
    }

    // Hide record card entirely if no view_records
    if (!has("view_records")) {
        const recordCard = document.getElementById("record-card");
        if (recordCard) recordCard.style.display = "none";
    }
}

function applySecretaryView() {
    // Hide ingest card
    const ingestCard = document.querySelector(".card:has(#ingest-btn)");
    if (ingestCard) ingestCard.style.display = "none";

    // Hide stepper
    const stepper = document.querySelector(".stepper");
    if (stepper) stepper.style.display = "none";

    // Replace search card with a full patient list
    const searchCard = document.getElementById("search-card");
    if (searchCard) {
        searchCard.querySelector(".card-header h2").textContent = "רשימת מטופלים";
        searchCard.querySelector(".card-body").innerHTML = `
            <div id="secretary-patient-list" style="margin-top:.5rem"></div>
        `;
        loadSecretaryPatientList();
    }
}

async function loadSecretaryPatientList() {
    const listEl = document.getElementById("secretary-patient-list");
    if (!listEl) return;
    listEl.innerHTML = `<div style="color:var(--muted);font-size:.85rem">טוען...</div>`;
    try {
        const res = await fetch("/patients", { credentials: "include" });
        if (!res.ok) throw new Error();
        const patients = await res.json();
        if (patients.length === 0) {
            listEl.innerHTML = `<div style="color:var(--muted);font-size:.85rem">אין מטופלים רשומים</div>`;
            return;
        }
        listEl.innerHTML = `
            <table style="width:100%;border-collapse:collapse;font-size:.87rem">
                <thead>
                    <tr style="border-bottom:2px solid var(--border)">
                        <th style="text-align:right;padding:.5rem .75rem;color:var(--text-secondary);font-weight:700">שם מלא</th>
                        <th style="text-align:right;padding:.5rem .75rem;color:var(--text-secondary);font-weight:700">ת.ז</th>
                        <th style="text-align:right;padding:.5rem .75rem;color:var(--text-secondary);font-weight:700">תאריך לידה</th>
                        <th style="text-align:right;padding:.5rem .75rem;color:var(--text-secondary);font-weight:700">מגדר</th>
                    </tr>
                </thead>
                <tbody>
                    ${patients.map(p => `
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:.5rem .75rem;font-weight:600;color:var(--text)">${esc(p.full_name || "ללא שם")}</td>
                            <td style="padding:.5rem .75rem;color:var(--text-secondary)">${esc(p.patient_id)}</td>
                            <td style="padding:.5rem .75rem;color:var(--text-secondary)">${esc(p.date_of_birth || "—")}</td>
                            <td style="padding:.5rem .75rem;color:var(--text-secondary)">${esc(p.gender || "—")}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    } catch(e) {
        listEl.innerHTML = `<div style="color:var(--error);font-size:.85rem">שגיאה בטעינת המטופלים</div>`;
    }
}

// ─── Discharge Letter ───
async function generateDischargeLetter() {
    if (!currentPatientInternalId) return;
    const card = document.getElementById("discharge-card");
    card.classList.add("hidden");
    setStatus("discharge", "יוצר מכתב שחרור...", "loading");
    try {
        const res = await fetch(`/p/${encodeURIComponent(currentPatientInternalId)}/discharge-letter`, {
            method: "POST", credentials: "include"
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const result = await res.json();
        setStatus("discharge", "", "");
        const letter = result.letter || "";
        document.getElementById("discharge-letter-text").textContent = letter;
        document.getElementById("discharge-patient-name").textContent = currentRecord?.full_name || "";
        document.getElementById("discharge-date").textContent = new Date().toLocaleDateString("he-IL");
        card.classList.remove("hidden");
    } catch(e) {
        setStatus("discharge", e.message, "error");
    }
}

if (dischargeBtn) dischargeBtn.addEventListener("click", generateDischargeLetter);

const dischargeCopyBtn = document.getElementById("discharge-copy-btn");
if (dischargeCopyBtn) {
    dischargeCopyBtn.addEventListener("click", () => {
        const text = document.getElementById("discharge-letter-text").textContent;
        navigator.clipboard.writeText(text).then(() => {
            dischargeCopyBtn.textContent = "✓ הועתק";
            setTimeout(() => { dischargeCopyBtn.textContent = "📋 העתק"; }, 2000);
        });
    });
}

const dischargePrintBtn = document.getElementById("discharge-print-btn");
if (dischargePrintBtn) {
    dischargePrintBtn.addEventListener("click", () => {
        const letter = document.getElementById("discharge-letter-text").textContent;
        const doctorName = document.getElementById("discharge-doctor-name").value;
        const patientName = currentRecord?.full_name || "";
        const date = new Date().toLocaleDateString("he-IL");
        const w = window.open("", "_blank");
        w.document.write(`<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="UTF-8">
<title>סיכום ביקור</title>
<style>body{font-family:Arial,sans-serif;font-size:13px;padding:32px;direction:rtl;color:#111}
h1{font-size:18px;margin-bottom:4px}.meta{color:#666;font-size:11px;margin-bottom:20px;border-bottom:1px solid #e5e7eb;padding-bottom:8px}
pre{white-space:pre-wrap;font-family:Arial,sans-serif;font-size:13px;line-height:1.6}
.footer{margin-top:32px;border-top:1px solid #e5e7eb;padding-top:12px;font-size:12px}
.disclaimer{font-size:10px;color:#9ca3af;margin-top:12px}
@media print{button{display:none}}</style></head><body>
<h1>סיכום ביקור / מכתב למומחה</h1>
<div class="meta">${patientName} &nbsp;|&nbsp; ${date}</div>
<pre>${letter}</pre>
<div class="footer">חתימת הרופא: ${doctorName || "_________________"}</div>
<div class="disclaimer">מסמך זה הופק כטיוטה על ידי מערכת NeoCortex AI ומחייב עיון ואישור הרופא המטפל לפני שליחה.</div>
<script>window.onload=function(){window.print()}<\/script>
</body></html>`);
        w.document.close();
    });
}

// ─── Visit History ───
async function loadVisitHistory() {
    if (!currentPatientId) return;
    setStatus("history", "טוען היסטוריה...", "loading");
    document.getElementById("history-content").innerHTML = "";
    try {
        const res = await fetch(`/patients/${encodeURIComponent(currentPatientId)}/transactions`, {
            credentials: "include"
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const transactions = await res.json();
        setStatus("history", "", "");
        renderHistory(transactions);
    } catch(e) {
        setStatus("history", networkErrMsg(e), "error");
    }
}

function renderHistory(transactions) {
    const container = document.getElementById("history-content");
    if (!transactions.length) {
        container.innerHTML = `<div class="card"><div class="card-body" style="color:var(--muted);font-size:.88rem;text-align:center;padding:2rem">אין ביקורים רשומים</div></div>`;
        return;
    }
    const sorted = [...transactions].sort((a, b) => new Date(b.date) - new Date(a.date));
    container.innerHTML = `
        <div style="font-size:.8rem;color:var(--muted);margin-bottom:.75rem">${sorted.length} פעולות רשומות · לחץ על שורה להרחבה</div>
        <div class="timeline">${sorted.map((tx, idx) => {
            const r = tx.extracted || {};
            const typeLabel = TX_TYPE_LABELS[tx.transaction_type] || tx.transaction_type;
            const badgeClass = TX_TYPE_COLORS[tx.transaction_type] || "";
            const meds = (r.medications || []).slice(0, 5);
            const symptoms = (r.symptoms || []).slice(0, 4);
            const isOpen = idx === 0;
            return `<div class="timeline-item">
                <div class="timeline-dot ${isOpen ? 'timeline-dot-current' : ''}"></div>
                <div class="card" style="flex:1;margin-bottom:0">
                    <div style="padding:.65rem 1rem;cursor:pointer;display:flex;align-items:center;gap:.6rem;user-select:none" onclick="toggleHistoryItem(this)">
                        <span class="tx-badge ${badgeClass}">${esc(typeLabel)}</span>
                        <span style="flex:1;font-weight:600;font-size:.88rem">${esc(r.chief_complaint || "ביקור")}</span>
                        <span style="color:var(--muted);font-size:.78rem;white-space:nowrap">${esc(tx.date)}</span>
                        <span class="history-chevron" style="color:var(--muted);font-size:.75rem;transition:transform .2s;${isOpen ? 'transform:rotate(180deg)' : ''}">▼</span>
                    </div>
                    <div class="${isOpen ? '' : 'hidden'}" style="border-top:1px solid var(--border)">
                        <div class="card-body" style="padding:1rem">
                            <table class="clinical-table" style="border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:.75rem">
                                ${r.full_name ? `<tr><td class="ct-label">שם מלא</td><td class="ct-value">${esc(r.full_name)}</td></tr>` : ""}
                                ${r.chief_complaint ? `<tr><td class="ct-label">תלונה עיקרית</td><td class="ct-value">${esc(r.chief_complaint)}</td></tr>` : ""}
                                ${symptoms.length ? `<tr><td class="ct-label">תסמינים</td><td class="ct-value">${tagList(symptoms)}</td></tr>` : ""}
                                ${meds.length ? `<tr><td class="ct-label">תרופות</td><td class="ct-value">${tagList(meds)}</td></tr>` : ""}
                                ${(r.allergies||[]).length ? `<tr><td class="ct-label">אלרגיות</td><td class="ct-value">${tagList(r.allergies)}</td></tr>` : ""}
                                ${r.vitals?.heart_rate ? `<tr><td class="ct-label">דופק</td><td class="ct-value">${r.vitals.heart_rate} bpm</td></tr>` : ""}
                                ${r.vitals?.blood_pressure_systolic ? `<tr><td class="ct-label">ל"ד</td><td class="ct-value">${r.vitals.blood_pressure_systolic}/${r.vitals.blood_pressure_diastolic} mmHg</td></tr>` : ""}
                            </table>
                            ${tx.raw_text ? `<details><summary style="cursor:pointer;font-size:.78rem;color:var(--muted);font-weight:600;padding:.25rem 0">📄 טקסט מקורי</summary><pre style="font-size:.75rem;color:var(--text-secondary);white-space:pre-wrap;margin-top:.4rem;padding:.6rem;background:#f9fafb;border-radius:6px;max-height:180px;overflow-y:auto;border:1px solid var(--border)">${esc(tx.raw_text.slice(0, 800))}${tx.raw_text.length > 800 ? '...' : ''}</pre></details>` : ""}
                        </div>
                    </div>
                </div>
            </div>`;
        }).join("")}</div>`;
}

function toggleHistoryItem(header) {
    const body = header.nextElementSibling;
    const chevron = header.querySelector(".history-chevron");
    const isNowHidden = body.classList.toggle("hidden");
    if (chevron) chevron.style.transform = isNowHidden ? "" : "rotate(180deg)";
}

document.getElementById("nav-history")?.addEventListener("click", loadVisitHistory);
document.getElementById("history-refresh-btn")?.addEventListener("click", loadVisitHistory);

const logoutBtn = document.getElementById("logout-btn");
if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
        await fetch("/auth/logout", {method: "POST", credentials: "include"});
        location.href = "/login";
    });
}

// ─── Change Password Modal ───
const changePwBtn = document.getElementById("change-password-btn");
const changePwModal = document.getElementById("change-pw-modal");
const cpMsgEl = document.getElementById("change-pw-msg");

function showChangePwModal() {
    document.getElementById("cp-current").value = "";
    document.getElementById("cp-new").value = "";
    document.getElementById("cp-confirm").value = "";
    cpMsgEl.style.display = "none";
    changePwModal.style.display = "flex";
}

if (changePwBtn) changePwBtn.addEventListener("click", showChangePwModal);
document.getElementById("cp-cancel-btn")?.addEventListener("click", () => { changePwModal.style.display = "none"; });

document.getElementById("cp-submit-btn")?.addEventListener("click", async () => {
    const current_password = document.getElementById("cp-current").value;
    const new_password = document.getElementById("cp-new").value;
    const confirm = document.getElementById("cp-confirm").value;
    cpMsgEl.style.display = "none";

    if (!current_password || !new_password || !confirm) {
        cpMsgEl.style.cssText = "display:block;background:#fef2f2;border:1px solid #fca5a5;color:#c81e1e;border-radius:8px;padding:.6rem .9rem;font-size:.85rem;margin-bottom:1rem";
        cpMsgEl.textContent = "נא למלא את כל השדות"; return;
    }
    if (new_password.length < 6) {
        cpMsgEl.style.cssText = "display:block;background:#fef2f2;border:1px solid #fca5a5;color:#c81e1e;border-radius:8px;padding:.6rem .9rem;font-size:.85rem;margin-bottom:1rem";
        cpMsgEl.textContent = "הסיסמה החדשה חייבת להכיל לפחות 6 תווים"; return;
    }
    if (new_password !== confirm) {
        cpMsgEl.style.cssText = "display:block;background:#fef2f2;border:1px solid #fca5a5;color:#c81e1e;border-radius:8px;padding:.6rem .9rem;font-size:.85rem;margin-bottom:1rem";
        cpMsgEl.textContent = "הסיסמאות אינן תואמות"; return;
    }
    try {
        const res = await fetch("/auth/change-password", {
            method: "POST", headers: {"Content-Type": "application/json"},
            credentials: "include",
            body: JSON.stringify({current_password, new_password})
        });
        if (res.ok) {
            cpMsgEl.style.cssText = "display:block;background:#f0fdf4;border:1px solid #86efac;color:#166534;border-radius:8px;padding:.6rem .9rem;font-size:.85rem;margin-bottom:1rem";
            cpMsgEl.textContent = "✓ הסיסמה שונתה בהצלחה";
            setTimeout(() => { changePwModal.style.display = "none"; }, 1500);
        } else {
            const data = await res.json();
            cpMsgEl.style.cssText = "display:block;background:#fef2f2;border:1px solid #fca5a5;color:#c81e1e;border-radius:8px;padding:.6rem .9rem;font-size:.85rem;margin-bottom:1rem";
            cpMsgEl.textContent = data.detail || "שגיאה";
        }
    } catch(e) {
        cpMsgEl.style.cssText = "display:block;background:#fef2f2;border:1px solid #fca5a5;color:#c81e1e;border-radius:8px;padding:.6rem .9rem;font-size:.85rem;margin-bottom:1rem";
        cpMsgEl.textContent = "שגיאת רשת, נסה שוב";
    }
});

// ─── Document Generation ───
const DOC_TYPE_LABELS = {
    sick_note: "אישור מחלה",
    referral: "מכתב הפניה",
    prescription: "מרשם",
    fitness: "תעודת כשירות",
};
const DOC_FIELDS = {
    sick_note: [
        { id: "df_from", label: "מתאריך", type: "date" },
        { id: "df_to",   label: "עד תאריך", type: "date" },
        { id: "df_dest", label: "מיועד ל (עבודה / לימודים)", type: "text", placeholder: "עבודה" },
    ],
    referral: [
        { id: "df_specialist", label: "הפניה אל (מומחה / מחלקה)", type: "text", placeholder: "קרדיולוג" },
        { id: "df_urgency",    label: "דחיפות", type: "text", placeholder: "רגיל / דחוף" },
        { id: "df_reason",     label: "סיבת ההפניה (אפשרות לשנות)", type: "text" },
    ],
    prescription: [
        { id: "df_drug",  label: "שם התרופה", type: "text", placeholder: "Metformin" },
        { id: "df_dose",  label: "מינון", type: "text", placeholder: "500mg" },
        { id: "df_freq",  label: "תדירות", type: "text", placeholder: "פעמיים ביום" },
        { id: "df_days",  label: "משך טיפול", type: "text", placeholder: "30 יום" },
    ],
    fitness: [
        { id: "df_purpose", label: "מטרת הכשירות", type: "text", placeholder: "ספורט / נהיגה / עבודה" },
        { id: "df_result",  label: "מסקנה", type: "text", placeholder: "כשיר" },
        { id: "df_valid",   label: "תוקף (חודשים)", type: "text", placeholder: "12" },
    ],
};

let currentDocType = null;

document.querySelectorAll(".doc-type-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        currentDocType = btn.dataset.type;
        const formArea = document.getElementById("doc-form-area");
        const fieldsEl = document.getElementById("doc-form-fields");
        document.querySelectorAll(".doc-type-btn").forEach(b => b.classList.remove("btn-primary"));
        btn.classList.add("btn-primary");
        const fields = DOC_FIELDS[currentDocType] || [];
        fieldsEl.innerHTML = fields.map(f => `
            <div>
                <label style="font-size:.78rem;font-weight:700;color:var(--text-secondary);display:block;margin-bottom:.2rem">${f.label}</label>
                <input id="${f.id}" type="${f.type}" placeholder="${f.placeholder || ''}" style="width:100%" />
            </div>
        `).join("");
        formArea.classList.remove("hidden");
        document.getElementById("doc-result-card").classList.add("hidden");
        setStatus("docs", "", "");
        // Auto-fill referral reason from patient record
        if (currentDocType === "referral" && currentRecord?.chief_complaint) {
            const el = document.getElementById("df_reason");
            if (el) el.value = currentRecord.chief_complaint;
        }
    });
});

document.getElementById("doc-generate-btn")?.addEventListener("click", async () => {
    if (!currentDocType || !currentPatientInternalId) {
        setStatus("docs", "יש לטעון מטופל תחילה", "error"); return;
    }
    const fields = DOC_FIELDS[currentDocType] || [];
    const details = {};
    const labelMap = {
        sick_note: { df_from: "מתאריך", df_to: "עד תאריך", df_dest: "מיועד ל" },
        referral:  { df_specialist: "הפניה אל", df_urgency: "דחיפות", df_reason: "סיבת הפניה" },
        prescription: { df_drug: "תרופה", df_dose: "מינון", df_freq: "תדירות", df_days: "משך טיפול" },
        fitness: { df_purpose: "מטרה", df_result: "מסקנה", df_valid: "תוקף" },
    };
    fields.forEach(f => {
        const val = document.getElementById(f.id)?.value?.trim();
        if (val) details[labelMap[currentDocType]?.[f.id] || f.id] = val;
    });
    // Add patient context
    if (currentRecord?.date_of_birth) details["תאריך לידה"] = currentRecord.date_of_birth;
    if (currentRecord?.patient_id) details["ת.ז"] = currentRecord.patient_id;

    setStatus("docs", `מייצר ${DOC_TYPE_LABELS[currentDocType]}...`, "loading");
    document.getElementById("doc-generate-btn").disabled = true;
    try {
        const res = await fetch(`/p/${encodeURIComponent(currentPatientInternalId)}/generate-doc`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ doc_type: currentDocType, details }),
            credentials: "include",
        });
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const data = await res.json();
        document.getElementById("doc-result-text").textContent = data.document;
        document.getElementById("doc-result-card").classList.remove("hidden");
        setStatus("docs", "", "");
        document.getElementById("doc-result-card").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch(e) {
        setStatus("docs", e.message, "error");
    } finally {
        document.getElementById("doc-generate-btn").disabled = false;
    }
});

document.getElementById("doc-copy-btn")?.addEventListener("click", () => {
    const text = document.getElementById("doc-result-text").textContent;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById("doc-copy-btn");
        btn.textContent = "✓ הועתק";
        setTimeout(() => { btn.textContent = "📋 העתק"; }, 2000);
    });
});

document.getElementById("doc-print-btn")?.addEventListener("click", () => {
    const text = document.getElementById("doc-result-text").textContent;
    const sig = document.getElementById("doc-doctor-sig")?.value || "";
    const label = DOC_TYPE_LABELS[currentDocType] || "מסמך רפואי";
    const patientName = currentRecord?.full_name || "";
    const date = new Date().toLocaleDateString("he-IL");
    const w = window.open("", "_blank");
    w.document.write(`<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="UTF-8">
<title>${label}</title>
<style>body{font-family:Arial,sans-serif;font-size:13px;padding:32px;direction:rtl;color:#111}
h1{font-size:18px;margin-bottom:4px}.meta{color:#666;font-size:11px;margin-bottom:20px;border-bottom:1px solid #e5e7eb;padding-bottom:8px}
pre{white-space:pre-wrap;font-family:Arial,sans-serif;font-size:13px;line-height:1.6}
.footer{margin-top:32px;border-top:1px solid #e5e7eb;padding-top:12px;font-size:12px}
.disclaimer{font-size:10px;color:#9ca3af;margin-top:12px}
@media print{button{display:none}}</style></head><body>
<h1>${label}</h1>
<div class="meta">${patientName} &nbsp;|&nbsp; ${date}</div>
<pre>${text}</pre>
<div class="footer">חתימת הרופא: ${sig || "_________________"}</div>
<div class="disclaimer">מסמך זה הופק כטיוטה על ידי מערכת NeoCortex AI ומחייב עיון ואישור הרופא המטפל לפני שימוש.</div>
<script>window.onload=function(){window.print()}<\/script>
</body></html>`);
    w.document.close();
});

document.getElementById("nav-docs")?.addEventListener("click", () => {
    if (!currentPatientInternalId) {
        setStatus("docs", "יש לטעון מטופל תחילה", "error");
    }
});

// ─── Reminders ───
async function loadReminders() {
    if (!currentPatientInternalId) return;
    const listEl = document.getElementById("reminders-list");
    try {
        const res = await fetch(`/p/${encodeURIComponent(currentPatientInternalId)}/reminders`, { credentials: "include" });
        if (!res.ok) return;
        const reminders = await res.json();
        renderReminders(reminders);
        updateReminderBadge(reminders);
    } catch(e) { /* silent */ }
}

function updateReminderBadge(reminders) {
    const badge = document.getElementById("reminder-badge");
    if (!badge) return;
    const today = new Date().toISOString().slice(0, 10);
    const upcoming = reminders.filter(r => r.date >= today);
    if (upcoming.length > 0) {
        badge.textContent = upcoming.length;
        badge.style.display = "inline";
    } else {
        badge.style.display = "none";
    }
}

function renderReminders(reminders) {
    const listEl = document.getElementById("reminders-list");
    if (!reminders.length) {
        listEl.innerHTML = `<div class="card"><div class="card-body" style="color:var(--muted);font-size:.88rem;text-align:center;padding:2rem">אין תזכורות</div></div>`;
        return;
    }
    const today = new Date().toISOString().slice(0, 10);
    const sorted = [...reminders].sort((a, b) => a.date.localeCompare(b.date));
    listEl.innerHTML = sorted.map(r => {
        const isPast = r.date < today;
        const isToday = r.date === today;
        const dateObj = new Date(r.date + "T00:00:00");
        const dateStr = dateObj.toLocaleDateString("he-IL", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
        const borderColor = isPast ? "#9ca3af" : isToday ? "#dc2626" : "#1a56db";
        const bg = isToday ? "#fef2f2" : isPast ? "#f9fafb" : "#fff";
        return `<div class="card" style="margin-bottom:.5rem;border-right:3px solid ${borderColor};background:${bg}">
            <div class="card-body" style="display:flex;align-items:center;gap:.75rem;padding:.65rem 1rem">
                <div style="flex:1">
                    <div style="font-size:.78rem;color:${borderColor};font-weight:700">${dateStr}${isToday ? " — היום!" : isPast ? " — עבר" : ""}</div>
                    <div style="font-size:.9rem;margin-top:.2rem">${esc(r.note)}</div>
                    ${r.created_by ? `<div style="font-size:.72rem;color:var(--muted);margin-top:.15rem">נוצר ע"י ${esc(r.created_by)}</div>` : ""}
                </div>
                <button onclick="deleteReminder('${r.reminder_id}')" style="background:none;border:none;color:#dc2626;cursor:pointer;font-size:1rem;padding:.2rem .4rem" title="מחק תזכורת">🗑</button>
            </div>
        </div>`;
    }).join("");
}

document.getElementById("reminder-add-btn")?.addEventListener("click", async () => {
    if (!currentPatientInternalId) {
        setStatus("reminder", "יש לטעון מטופל תחילה", "error"); return;
    }
    const date = document.getElementById("reminder-date").value;
    const note = document.getElementById("reminder-note").value.trim();
    if (!date || !note) {
        const msg = document.getElementById("reminder-msg");
        msg.textContent = "נא למלא תאריך והערה";
        msg.style.color = "#dc2626";
        return;
    }
    try {
        const res = await fetch(`/p/${encodeURIComponent(currentPatientInternalId)}/reminders`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ date, note }),
            credentials: "include",
        });
        if (!res.ok) throw new Error();
        const reminders = await res.json();
        renderReminders(reminders);
        updateReminderBadge(reminders);
        document.getElementById("reminder-date").value = "";
        document.getElementById("reminder-note").value = "";
        const msg = document.getElementById("reminder-msg");
        msg.textContent = "✓ תזכורת נוספה";
        msg.style.color = "#166534";
        setTimeout(() => { msg.textContent = ""; }, 2000);
    } catch(e) {
        const msg = document.getElementById("reminder-msg");
        msg.textContent = "שגיאה בשמירת תזכורת";
        msg.style.color = "#dc2626";
    }
});

async function deleteReminder(reminderId) {
    if (!currentPatientInternalId) return;
    try {
        const res = await fetch(`/p/${encodeURIComponent(currentPatientInternalId)}/reminders/${reminderId}`, {
            method: "DELETE", credentials: "include",
        });
        if (!res.ok) throw new Error();
        const reminders = await res.json();
        renderReminders(reminders);
        updateReminderBadge(reminders);
    } catch(e) { /* silent */ }
}

document.getElementById("nav-reminders")?.addEventListener("click", loadReminders);

// ─── Inline patient name edit ───
function editPatientName(span) {
    const current = span.textContent;
    const input = document.createElement("input");
    input.value = current === "—" ? "" : current;
    input.style.cssText = "font-size:inherit;font-family:inherit;border:none;border-bottom:2px solid var(--primary);outline:none;background:transparent;width:200px;padding:0";
    span.replaceWith(input);
    input.focus();

    async function save() {
        const newName = input.value.trim() || current;
        const newSpan = document.createElement("span");
        newSpan.id = "patient-name-display";
        newSpan.style.cssText = "cursor:pointer;border-bottom:1px dashed var(--border)";
        newSpan.title = "לחץ לעריכה";
        newSpan.textContent = newName;
        newSpan.onclick = function() { editPatientName(this); };
        input.replaceWith(newSpan);
        if (newName === current) return;
        if (currentRecord) currentRecord.full_name = newName;
        const titleEl = document.getElementById("record-card-title");
        if (titleEl) titleEl.textContent = `תיק מטופל · ${newName}`;
        updateSidebarPatient(newName, currentPatientId);
        if (currentPatientInternalId) {
            try {
                await fetch(`/p/${encodeURIComponent(currentPatientInternalId)}/name`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ full_name: newName }),
                    credentials: "include",
                });
            } catch(e) { /* silent */ }
        }
    }
    input.addEventListener("blur", save);
    input.addEventListener("keydown", e => { if (e.key === "Enter") input.blur(); if (e.key === "Escape") { input.value = current; input.blur(); } });
}

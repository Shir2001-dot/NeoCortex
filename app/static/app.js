// ─── Elements ───
const ingestBtn       = document.getElementById("ingest-btn");
const decisionBtn     = document.getElementById("decision-btn");
const vitalsBtn       = document.getElementById("vitals-btn");
const interactionsBtn = document.getElementById("interactions-btn");
const printBtn        = document.getElementById("print-btn");
const searchBtn       = document.getElementById("search-btn");
const decisionCard        = document.getElementById("decision-card");
const interactionsCard    = document.getElementById("interactions-card");
const recordContent       = document.getElementById("record-content");
const decisionContent     = document.getElementById("decision-content");
const interactionsContent = document.getElementById("interactions-content");

let currentPatientId = null;
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

// Warn before page refresh if patient is open
window.addEventListener("beforeunload", (e) => {
    if (currentPatientId) {
        e.preventDefault();
        e.returnValue = "";
    }
});
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
            ${clinicalRow("שם מלא", esc(r.full_name) || "—")}
            ${clinicalRow("תאריך לידה", esc(r.date_of_birth) || "—")}
            ${clinicalRow("מגדר", esc(r.gender) || "—")}
            ${v.heart_rate ? clinicalRow("דופק", v.heart_rate + " bpm") : ""}
            ${v.blood_pressure_systolic ? clinicalRow('ל"ד', bp) : ""}
            ${v.spo2_percent ? clinicalRow("חמצן בדם SpO2", v.spo2_percent + "%") : ""}
        </table>
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
        currentRecord = tx.extracted;
        const titleEl = document.getElementById("record-card-title");
        if (titleEl) titleEl.textContent = `תיק מטופל · ת.ז ${tx.patient_id}`;
        renderRecord(tx.extracted);
        unlockClinicalNav(tx.patient_id);
        updateSidebarPatient(tx.extracted.full_name, tx.patient_id);
        showView("record");
        setStatus("ingest","הופק בהצלחה ✓","success");


    } catch (e) {
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
        const res = await fetch(`/patients/${encodeURIComponent(currentPatientId)}/session-summary`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ notes }),
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
        const res = await fetch(`/patients/${encodeURIComponent(currentPatientId)}/save-summary`, {
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

// ─── Print / PDF Export ───
printBtn.addEventListener("click", () => {
    if (!currentPatientId) return;
    window.open(`/patients/${encodeURIComponent(currentPatientId)}/print`, "_blank");
});

// ─── Patient Search ───
searchBtn.addEventListener("click", async () => {
    const query = document.getElementById("search-input").value.trim().toLowerCase();
    const resultsEl = document.getElementById("search-results");
    if (!query) { resultsEl.innerHTML = ""; return; }

    try {
        const res = await fetch("/patients");
        if (!res.ok) throw new Error(`שגיאת שרת (${res.status})`);
        const patients = await res.json();
        const filtered = patients.filter(p =>
            (p.full_name || "").toLowerCase().includes(query) ||
            (p.patient_id || "").toLowerCase().includes(query)
        );

        if (filtered.length === 0) {
            resultsEl.innerHTML = `<div class="search-results"><div class="search-empty">לא נמצאו מטופלים</div></div>`;
            return;
        }

        resultsEl.innerHTML = `<div class="search-results">${filtered.map(p => `
            <div class="search-item" data-id="${esc(p.patient_id)}">
                <span class="search-item-name">${esc(p.full_name || "ללא שם")}</span>
                <span class="search-item-id">${esc(p.patient_id)}</span>
            </div>
        `).join("")}</div>`;

        resultsEl.querySelectorAll(".search-item").forEach(item => {
            item.addEventListener("click", async () => {
                const pid = item.dataset.id;
                try {
                    const recRes = await fetch(`/patients/${encodeURIComponent(pid)}`);
                    if (!recRes.ok) throw new Error("מטופל לא נמצא");
                    const record = await recRes.json();
                    currentPatientId = pid;
                    currentRecord = record;
                    const titleEl = document.getElementById("record-card-title");
                    if (titleEl) titleEl.textContent = `תיק מטופל · ת.ז ${pid}`;
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
    } catch(e) {
        resultsEl.innerHTML = `<div class="search-results"><div class="search-empty">${esc(e.message)}</div></div>`;
    }
});

document.getElementById("search-input").addEventListener("keydown", e => {
    if (e.key === "Enter") searchBtn.click();
});

// ─── Drug Interactions ───
interactionsBtn.addEventListener("click", async () => {
    if (!currentPatientId) return;
    interactionsCard.classList.remove("hidden");
    setStatus("interactions", "בודק אינטראקציות תרופות...", "loading");
    interactionsBtn.disabled = true;
    interactionsContent.innerHTML = "";

    try {
        const res = await fetch(`/patients/${encodeURIComponent(currentPatientId)}/interactions`, {
            method: "POST",
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
                <div style="font-size:.82rem;color:var(--text-secondary);margin-bottom:.2rem">${item.drugs.map(d => esc(d)).join(" ← ")}</div>
                <div class="flag-msg">${esc(item.description)}</div>
                <div style="font-size:.75rem;color:var(--muted);margin-top:.3rem;font-style:italic">⚠️ יש לאמת מידע זה מול מקור רפואי מוסמך</div>
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
        const res = await fetch(`/decision/${encodeURIComponent(currentPatientId)}`, {method:"POST"});
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
        const res = await fetch("/patients");
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

const logoutBtn = document.getElementById("logout-btn");
if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
        await fetch("/auth/logout", {method: "POST", credentials: "include"});
        location.href = "/login";
    });
}

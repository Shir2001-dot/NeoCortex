from app.models import PatientRecord, VisitDelta

def compute_delta(current: PatientRecord, previous: PatientRecord) -> VisitDelta:
    def names(meds): return set(m.strip().lower() for m in (meds or []))
    cur_meds = names(current.medications)
    prev_meds = names(previous.medications)
    cur_sym = names(current.symptoms)
    prev_sym = names(previous.symptoms)

    changed_vitals = []
    if current.vitals and previous.vitals:
        cv, pv = current.vitals, previous.vitals
        for field, label in [("heart_rate","דופק"),("blood_pressure_systolic",'ל"ד סיסטולי'),("spo2_percent","SpO2")]:
            c_val = getattr(cv, field, None)
            p_val = getattr(pv, field, None)
            if c_val and p_val and c_val != p_val:
                changed_vitals.append(f"{label}: {p_val} → {c_val}")

    return VisitDelta(
        new_medications=sorted(cur_meds - prev_meds),
        removed_medications=sorted(prev_meds - cur_meds),
        new_symptoms=sorted(cur_sym - prev_sym),
        resolved_symptoms=sorted(prev_sym - cur_sym),
        changed_vitals=changed_vitals,
    )

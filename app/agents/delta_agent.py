from app.models import PatientRecord, VisitDelta


def compute_delta(current: PatientRecord, previous: PatientRecord) -> VisitDelta:
    """Compare two PatientRecords and return what changed between visits."""

    def meds_set(r: PatientRecord) -> set:
        return set(r.medications or [])

    def symptoms_set(r: PatientRecord) -> set:
        return set(r.symptoms or [])

    curr_meds = meds_set(current)
    prev_meds = meds_set(previous)
    curr_syms = symptoms_set(current)
    prev_syms = symptoms_set(previous)

    changed_vitals = []
    if current.vitals and previous.vitals:
        cv = current.vitals
        pv = previous.vitals
        vitals_fields = [
            ("heart_rate", "דופק"),
            ("blood_pressure_systolic", 'ל"ד סיסטולי'),
            ("blood_pressure_diastolic", 'ל"ד דיאסטולי'),
            ("temperature_celsius", "טמפרטורה"),
            ("spo2_percent", "SpO2"),
            ("respiratory_rate", "קצב נשימה"),
        ]
        for field, label in vitals_fields:
            c_val = getattr(cv, field, None)
            p_val = getattr(pv, field, None)
            if c_val is not None and p_val is not None and c_val != p_val:
                changed_vitals.append(f"{label}: {p_val} → {c_val}")

    return VisitDelta(
        new_medications=sorted(curr_meds - prev_meds),
        removed_medications=sorted(prev_meds - curr_meds),
        new_symptoms=sorted(curr_syms - prev_syms),
        resolved_symptoms=sorted(prev_syms - curr_syms),
        changed_vitals=changed_vitals,
    )

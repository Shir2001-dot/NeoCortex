"""
Test suite for drug interactions agent.
Run: python -m pytest tests/test_interactions.py -v

Purpose: Catch hallucinations and validate clinical accuracy.
Update this file whenever a false positive/negative is found.
"""
import pytest
from app.agents.interactions_agent import check_interactions


# ─── CRITICAL interactions (must be detected) ───────────────────────────────

def test_sildenafil_nitrate_is_critical():
    """Sildenafil + Nitrates = absolute contraindication (severe hypotension, death risk)."""
    result = check_interactions("test", ["Sildenafil 50mg", "Isosorbide Mononitrate 20mg"])
    severities = [i["severity"] for i in result.interactions]
    assert "critical" in severities, "Sildenafil + Nitrate must be flagged as CRITICAL"


def test_warfarin_aspirin_is_warning():
    """Warfarin + Aspirin = increased bleeding risk (well documented)."""
    result = check_interactions("test", ["Warfarin 5mg", "Aspirin 100mg"])
    severities = [i["severity"] for i in result.interactions]
    assert any(s in ("warning", "critical") for s in severities), \
        "Warfarin + Aspirin must be flagged as warning or critical"


def test_ssri_maoi_is_critical():
    """SSRI + MAOI = serotonin syndrome risk (life threatening)."""
    result = check_interactions("test", ["Fluoxetine 20mg", "Phenelzine 15mg"])
    severities = [i["severity"] for i in result.interactions]
    assert "critical" in severities, "SSRI + MAOI must be flagged as CRITICAL"


# ─── NON-interactions (must NOT be flagged or flagged as info only) ──────────

def test_omeprazole_sildenafil_not_critical():
    """
    Omeprazole + Sildenafil: Sildenafil is metabolized mainly by CYP3A4, NOT CYP2C19.
    Omeprazole's CYP2C19 inhibition has negligible clinical effect on Sildenafil levels.
    Must NOT be flagged as warning or critical.
    """
    result = check_interactions("test", ["Omeprazole 20mg", "Sildenafil 50mg"])
    for interaction in result.interactions:
        drugs = [d.lower() for d in interaction["drugs"]]
        if "omeprazole" in " ".join(drugs) and "sildenafil" in " ".join(drugs):
            assert interaction["severity"] == "info", \
                f"Omeprazole + Sildenafil should be 'info' at most, got: {interaction['severity']}"


def test_no_interaction_for_single_drug():
    """Single drug cannot have interactions."""
    result = check_interactions("test", ["Metformin 500mg"])
    assert result.interactions == [], "Single drug must return empty interactions"


def test_no_interaction_for_safe_combination():
    """Paracetamol + Vitamin D — no known significant interaction."""
    result = check_interactions("test", ["Paracetamol 500mg", "Vitamin D3 1000IU"])
    critical_or_warning = [i for i in result.interactions if i["severity"] in ("critical", "warning")]
    assert len(critical_or_warning) == 0, \
        "Paracetamol + Vitamin D should have no critical/warning interactions"


# ─── Edge cases ──────────────────────────────────────────────────────────────

def test_empty_medication_list():
    """Empty list must return empty interactions."""
    result = check_interactions("test", [])
    assert result.interactions == []


def test_fictitious_drugs_no_critical():
    """Made-up drug names must not produce critical interactions."""
    result = check_interactions("test", ["Xylotonin 10mg", "Flamberazol 5mg"])
    critical = [i for i in result.interactions if i["severity"] == "critical"]
    assert len(critical) == 0, "Fictitious drugs must not produce critical interactions"

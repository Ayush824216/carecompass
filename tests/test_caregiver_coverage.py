import json
from pathlib import Path

from app import data_adapter
from app.schemas import CARE_TYPES, EMERGENCY_CARE_TYPE

ROOT = Path(__file__).resolve().parents[1]
MAP = json.loads((ROOT / "config" / "care_type_to_roles.json").read_text(encoding="utf-8"))
REQUIRED_SPECIALTIES = ["dermatology", "orthopedics", "cardiology", "pediatrics", "ent", "gynecology", "neurology", "pulmonology"]


def test_every_care_type_is_mapped():
    for ct in CARE_TYPES:
        assert ct in MAP, f"{ct} has no role mapping"
    assert MAP[EMERGENCY_CARE_TYPE]["roles"] == []


def test_enough_caregivers_per_care_type():
    cgs = data_adapter.load_caregivers()
    for ct in CARE_TYPES:
        if ct == EMERGENCY_CARE_TYPE:
            continue
        n = sum(1 for c in cgs if c["role"] in MAP[ct]["roles"])
        assert n >= 3, f"{ct}: only {n} eligible caregivers"


def test_dev_data_depth():
    cgs = data_adapter.load_caregivers()
    for role in ("paramedic", "nurse", "gp", "specialist"):
        assert sum(c["role"] == role for c in cgs) >= 12, role
    specs = {c.get("specialty") for c in cgs if c["role"] == "specialist"}
    assert set(REQUIRED_SPECIALTIES) <= specs
    for sp in REQUIRED_SPECIALTIES:
        assert sum(c.get("specialty") == sp for c in cgs) >= 3, sp
    for c in cgs:
        for k in ("caregiver_id", "name", "role", "skills", "lat", "lng", "languages", "rating", "availability_slots",
                  "qualification", "years_experience", "locality", "consultation_modes"):
            assert k in c, (c["caregiver_id"], k)

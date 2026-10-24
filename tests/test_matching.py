from datetime import datetime, timedelta

from app import matching
from app.data_adapter import IST

NOW = datetime(2026, 10, 24, 10, 0, tzinfo=IST)


def slot(hours: float) -> str:
    return (NOW + timedelta(hours=hours)).isoformat()


def cg(cid, role, lat, lng, slots, langs, rating, skills=()):
    return {"caregiver_id": cid, "name": cid, "role": role, "skills": list(skills), "lat": lat, "lng": lng,
            "availability_slots": slots, "languages": langs, "rating": rating}


LOC = {"lat": 28.54, "lng": 77.27}
FIXTURE = [
    # near, hindi, free in 2h, right skills -> should win
    cg("P_BEST", "paramedic", 28.55, 77.28, [slot(2)], ["hi", "en"], 4.6, ["fever_assessment", "elderly_care"]),
    # far (beyond cutoff) -> filtered for home visit
    cg("P_FAR", "paramedic", 28.80, 77.40, [slot(1)], ["hi"], 5.0, ["fever_assessment", "elderly_care"]),
    # near but only free tomorrow -> excluded for same_day
    cg("P_TOMORROW", "paramedic", 28.541, 77.271, [slot(26)], ["hi"], 5.0, ["fever_assessment"]),
    # near, english only, free later today
    cg("P_EN", "paramedic", 28.56, 77.30, [slot(6)], ["en"], 4.0, ["vitals_check"]),
    cg("N_1", "nurse", 28.54, 77.27, [slot(1)], ["hi"], 5.0, ["injection"]),
    cg("G_HI", "gp", 28.70, 77.10, [slot(1)], ["hi"], 4.5, ["general_medicine"]),
    cg("G_EN", "gp", 28.54, 77.27, [slot(1)], ["en"], 4.5, ["general_medicine"]),
    cg("S_ORTHO", "specialist", 28.60, 77.20, [slot(30)], ["hi"], 4.2, ["orthopedics"]),
    cg("S_DERM", "specialist", 28.54, 77.27, [slot(3)], ["hi"], 4.9, ["dermatology"]),
]


def ids(res):
    return [r.cg["caregiver_id"] for r in res]


def test_paramedic_ranking_order():
    res = matching.rank("paramedic_home_visit", "same_day", "hinglish", LOC, ["fever", "cough"], "elderly",
                        now=NOW, caregivers=FIXTURE)
    assert ids(res)[0] == "P_BEST"
    assert "P_FAR" not in ids(res) and "P_TOMORROW" not in ids(res) and "N_1" not in ids(res)
    assert all(0 <= r.score <= 1 for r in res)
    assert res == sorted(res, key=lambda r: -r.score)


def test_teleconsult_ignores_distance_prefers_language():
    res = matching.rank("gp_teleconsult", "routine", "hi", LOC, ["cold"], now=NOW, caregivers=FIXTURE)
    assert ids(res)[0] == "G_HI"


def test_specialist_hard_filter_on_specialty():
    res = matching.rank("specialist_referral", "routine", "en", LOC, ["joint pain"], "elderly", now=NOW, caregivers=FIXTURE)
    assert ids(res) == ["S_ORTHO"]


def test_emergency_has_no_matches():
    assert matching.rank("emergency_referral", "immediate", "en", LOC, [], now=NOW, caregivers=FIXTURE) == []


def test_reason_uses_components():
    res = matching.rank("paramedic_home_visit", "same_day", "en", LOC, ["fever"], "elderly", now=NOW, caregivers=FIXTURE)
    r = matching.reason(res[0], "paramedic_home_visit", "en", now=NOW)
    assert "Hindi" not in r or "speaking" in r
    assert "km away" in r and "today" in r and "rated 4.6" in r
    rh = matching.reason(res[0], "paramedic_home_visit", "hi", now=NOW)
    assert "किमी" in rh and "हिंदी" in rh


def test_relaxes_when_nothing_eligible():
    only_far = [FIXTURE[1]]
    res = matching.rank("paramedic_home_visit", "same_day", "hi", LOC, ["fever"], now=NOW, caregivers=only_far)
    assert ids(res) == ["P_FAR"]

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
    # 3 paramedics within 5 km -> the far one is not needed; nurse is not eligible
    assert "P_FAR" not in ids(res) and "N_1" not in ids(res)
    # only free tomorrow: still listed (never empty), but ranked below those free today
    assert ids(res).index("P_TOMORROW") > ids(res).index("P_BEST")
    assert not next(r for r in res if r.cg["caregiver_id"] == "P_TOMORROW").in_window
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
    assert "km away" in r and "free today" in r and "4.6★" in r
    rg = matching.reason(res[0], "paramedic_home_visit", "hinglish", now=NOW)
    assert "Hindi bolte hain" in rg and "km door" in rg and "aaj" in rg
    rh = matching.reason(res[0], "paramedic_home_visit", "hi", now=NOW)
    assert "किमी" in rh and "हिंदी" in rh


def test_relaxes_when_nothing_eligible():
    only_far = [FIXTURE[1]]
    res = matching.rank("paramedic_home_visit", "same_day", "hi", LOC, ["fever"], now=NOW, caregivers=only_far)
    assert ids(res) == ["P_FAR"]



def test_radius_widens_until_enough():
    far = [cg(f"F{i}", "paramedic", 28.80 + i * 0.01, 77.40, [slot(2)], ["hi"], 4.5) for i in range(4)]
    res, info = matching.rank_with_info("paramedic_home_visit", "routine", "hi", LOC, ["fever"], now=NOW, caregivers=far)
    assert len(res) >= 3 and info.radius_km in (None, 20.0) or info.radius_km is None


def test_specialty_inferred_from_text():
    res, info = matching.rank_with_info("specialist_referral", "routine", "hinglish", LOC, [], text="skin pe rash hai 2 hafte se",
                                        now=NOW, caregivers=FIXTURE)
    assert info.specialties[0] == "dermatology" and ids(res) == ["S_DERM"]


def test_child_accepts_pediatrics():
    assert "pediatrics" in matching.infer_specialties(["rash"], "child", "beti ko rash hai")


def test_never_empty_when_nobody_free_today():
    busy = [cg(f"B{i}", "nurse", 28.54, 77.27 + i * 0.01, [slot(30)], ["hi"], 4.0) for i in range(3)]
    res = matching.rank("nurse_home_visit", "same_day", "hi", LOC, ["wound"], now=NOW, caregivers=busy)
    assert len(res) == 3 and all(not r.in_window for r in res)
    assert "sabse pehle" in matching.reason(res[0], "nurse_home_visit", "hinglish", now=NOW)


def test_real_data_every_care_type_returns_at_least_3():
    for ct, sym in (("paramedic_home_visit", ["fever"]), ("nurse_home_visit", ["wound"]),
                    ("gp_teleconsult", ["cold"]), ("specialist_referral", ["rash"])):
        for loc in ({"lat": 28.5245, "lng": 77.2066}, {"lat": 28.6270, "lng": 77.3649}, {"lat": 28.3955, "lng": 77.3188}):
            for urg in ("routine", "same_day"):
                assert len(matching.rank(ct, urg, "hi", loc, sym)) >= 3, (ct, loc, urg)

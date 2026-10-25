"""Privacy: PII redaction, incognito, LOCAL_ONLY, anonymised metrics, no text in logs; device memory hints."""
import logging

import pytest
from fastapi.testclient import TestClient

from app import cache, llm, privacy
from app.config import get_settings
from app.main import app
from app.redact import redact

client = TestClient(app)
LOC = {"lat": 28.5245, "lng": 77.2066}


def _post(text, hist=None, headers=None, **extra):
    return client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist or [], "location": LOC,
                                                "debug": True, **extra}, headers=headers or {}).json()


# ---------------------------------------------------------------- E. redaction
@pytest.mark.parametrize("text,gone,kept", [
    ("Mera naam Rahul Sharma hai, papa ko 3 din se bukhar hai", ["Rahul", "Sharma"], ["bukhar", "3 din"]),
    ("call me at 9876543210, dadi gir gayi", ["9876543210"], ["dadi gir gayi"]),
    ("+91 98765 43210 pe call karo, seene mein dard", ["98765"], ["seene mein dard"]),
    ("my email is priya.k@gmail.com and I have cough", ["priya.k@gmail.com"], ["cough"]),
    ("Aadhaar 1234 5678 9012, khansi 2 hafte se", ["1234 5678 9012"], ["khansi 2 hafte se"]),
    ("H.No 23, Sector 15, Rohini, bukhar 102", ["H.No 23", "Sector 15"], ["bukhar 102"]),
    ("I am Priya, I have fever", ["Priya"], ["fever"]),
    ("मेरा नाम सुनीता है, सिर दर्द है", ["सुनीता"], ["सिर दर्द है"]),
    ("pin code 110085, ulti ho rahi hai", ["110085"], ["ulti ho rahi hai"]),
])
def test_redaction_removes_pii_keeps_symptoms(text, gone, kept):
    out = redact(text)
    assert not any(g in out for g in gone), out
    assert all(k in out for k in kept), out


@pytest.mark.parametrize("text", ["platelets 150000, BP 140/90, temp 39 C", "I am feeling sick", "bukhar 102.5 hai",
                                  "sugar 250 hai, 4 din se"])
def test_redaction_keeps_readings(text):
    assert redact(text) == text


def test_llm_receives_redacted_text(monkeypatch):
    seen = {}
    monkeypatch.setattr(llm, "available", lambda: True)

    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "{}"}}]}

    class C:
        def post(self, url, **kw):
            seen["body"] = kw["json"]["messages"][1]["content"]
            return R()
    monkeypatch.setattr(llm, "_http", lambda: C())
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "openai")
    llm.chat_json("sys", "Mera naam Rahul hai, phone 9876543210, bukhar hai")
    assert "Rahul" not in seen["body"] and "9876543210" not in seen["body"] and "bukhar" in seen["body"]


# ---------------------------------------------------------------- A/F/G. incognito, LOCAL_ONLY, metrics, logs
def test_incognito_skips_cache_metrics_and_llm(monkeypatch):
    rc = cache.ResponseCache(900)
    monkeypatch.setattr(cache, "response_cache", lambda: rc)
    calls = []
    monkeypatch.setattr("app.llm_triage.llm_decision", lambda *a, **k: calls.append(1))
    privacy.reset_metrics()
    r = _post("mujhe 3 din se bukhar hai", headers={"X-Incognito": "1"})
    assert r["debug"]["processing"]["incognito"] and r["debug"]["processing"]["local"]
    assert len(rc._d) == 0 and privacy.metrics()["requests"] == 0 and not calls
    r2 = _post("mujhe 3 din se bukhar hai")
    assert privacy.metrics()["requests"] == 1 and len(rc._d) == 1
    assert {k: r[k] for k in ("care_type", "urgency", "follow_up_question")} == {k: r2[k] for k in ("care_type", "urgency", "follow_up_question")}


def test_local_only_disables_llm(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_only", True)
    monkeypatch.setattr(s, "llm_provider", "openai")
    monkeypatch.setattr(s, "llm_api_key", "x")
    monkeypatch.setattr(s, "llm_model", "m")
    assert llm.available() is False
    assert _post("papa ko bukhar hai")["debug"]["processing"]["local"] is True


def test_metrics_are_anonymous():
    privacy.reset_metrics()
    _post("Mera naam Rahul hai, papa ko 3 din se bukhar hai")
    m = client.get("/metrics").json()
    flat = str(m).lower()
    assert m["requests"] == 1 and "rahul" not in flat and "bukhar" not in flat and "papa" not in flat


def test_no_user_text_in_logs(caplog):
    caplog.set_level(logging.DEBUG)
    _post("Mera naam Rahul hai, 9876543210, papa ko seene mein dard")
    _post("Mera naam Rahul hai, phone 9876543210, bukhar 3 din se")
    logged = " ".join(r.getMessage() for r in caplog.records).lower()
    assert "rahul" not in logged and "9876543210" not in logged and "bukhar" not in logged and "seene" not in logged


def test_location_never_logged(caplog):
    caplog.set_level(logging.DEBUG)
    client.post("/api/v1/triage", json={"user_input": "bukhar 3 din se", "conversation_history": [],
                                        "location": {"lat": 19.07612, "lng": 72.87765}})
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "19.076" not in logged and "72.877" not in logged


# ---------------------------------------------------------------- B/D. device memory hints
def _flow(start, answers, memory=None):
    hist, text, qids, r = [], start, [], None
    answers = list(answers)
    for _ in range(10):
        r = _post(text, hist, memory=memory) if memory else _post(text, hist)
        qids.append(r["debug"]["followup"].get("question_id"))
        if not r["follow_up_question"]:
            break
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        text = answers.pop(0) if answers else ("18–64 saal" if qids[-1] == "common.age" else "Kuch nahi")
    return r, qids


MEM = {"age_group": "elderly", "conditions": ["diabetes"]}


def test_memory_confirmed_once_and_not_counted():
    r = _post("Kuch nahi", [{"role": "user", "content": "mujhe bukhar hai"},
                            {"role": "assistant", "content": "Bukhar ke saath inme se kuch ho raha hai?"}], memory=MEM)
    f = r["debug"]["followup"]
    assert f["question_id"] == "memory.confirm" and f["asked_so_far"] == 1
    assert "sugar" in r["follow_up_question"].lower() and "65+" in r["follow_up_question"]


def test_memory_yes_adds_risk_no_ignores_it():
    yes, q_yes = _flow("mujhe bukhar hai", ["Kuch nahi", "Haan, abhi bhi"], MEM)
    no, q_no = _flow("mujhe bukhar hai", ["Kuch nahi", "Nahi, ab nahi"], MEM)
    none, _ = _flow("mujhe bukhar hai", ["Kuch nahi"])
    rank = {"routine": 0, "same_day": 1, "immediate": 2}
    assert q_yes.count("memory.confirm") == 1 and "common.age" not in q_yes  # age came from the confirmed memory
    assert "common.age" in q_no
    assert rank[yes["urgency"]] >= rank[none["urgency"]]  # memory never lowers urgency
    assert yes["debug"]["age"]["group"] == "elderly"


def test_sensitive_items_marked():
    r, _ = _flow("Mann / mood", ["Nahi, aise khayal nahi", "18–64 saal", "Kai mahino se", "Thoda asar"])
    cands = {c["id"]: c for c in r["debug"]["memory_candidates"]}
    assert cands["mental_health"]["sensitive"] is True and cands["age_group"]["sensitive"] is False
    assert r["debug"]["memory_summary"]["sensitive"] is True
    r, _ = _flow("main pregnant hoon aur 2 din se bukhar hai, sugar bhi hai", [])
    cands = {c["id"]: c for c in r["debug"]["memory_candidates"]}
    assert cands["pregnancy"]["sensitive"] is True and cands["diabetes"]["sensitive"] is False


def test_official_schema_unchanged_without_debug():
    r = client.post("/api/v1/triage", json={"user_input": "mujhe bukhar hai", "memory": MEM}).json()
    assert set(r) == {"follow_up_question", "care_type", "urgency", "red_flags", "reasoning", "matched_caregivers"}

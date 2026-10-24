"""Hallucination control (judge feedback, round 2).

For 30+ inputs, run the conversation to its end (answering "none" to every chip question) and assert that the output
contains no symptom, number or disease name unless it is supported by the user's input or by our closed lists:
- every symptom / sign shown as present carries an evidence span that is literally in the user's words;
- every number in user-facing text appears in the input (or is the °F of a °C reading the user gave), or in our
  curated config / fixed templates (112, 108, "65+");
- no disease or medicine name appears unless the user said it, except in the "possible causes" and "tests" sections,
  whose items must be ids from the closed lists in config/assessment.json.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import llm_triage
from app.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
LOC = {"lat": 28.5245, "lng": 77.2066}
NUM = re.compile(r"\d+(?:[.,]\d+)*")

INPUTS = [
    "Papa ko do din se bukhar hai aur khansi bhi",
    "dadi ko 4 din se bukhar hai 101, platelets 90000",
    "Papa ko 39 C bukhar hai 3 din se",
    "bukhar 102 hai 2 din se",
    "mujhe 3 hafte se khansi hai",
    "My mother has had a cough for 3 weeks",
    "dadi ko chalne par saans phoolti hai",
    "bachche ko 2 din se dast ho rahe hain, 5 baar",
    "mummy ko 10 baar ulti hui",
    "sir dard ho raha hai subah se",
    "peshab mein jalan hai 2 din se",
    "pet mein dard hai kal se",
    "need a nurse at home for injections",
    "dadaji gir gaye, ghutne mein chot hai",
    "मुझे दो दिन से बुखार है",
    "बच्चे को खांसी और जुकाम है",
    "abba ko bukhar hai",
    "I have had acne on the face for 6 months",
    "papa ki tabiyat theek nahi hai",
    "BP 150/95 hai aur sir dard",
    "My 70 year old father has fever since yesterday",
    "8 mahine ke baby ko bukhar hai",
    "mujhe dengue hua tha pichle saal, ab bukhar hai 2 din se",
    "seene mein jalan hoti hai khane ke baad, 25 saal",
    "chakkar aa rahe hain uthne par",
    "kamar mein dard hai 2 hafte se",
    "aankh laal hai aur paani aa raha hai",
    "mujhe xyzitis hai",
    "abba dabba jabba",
    "2+2",
    "hello, papa behosh ho gaye",
    "platelets 15000 reh gaye",
]


def _run(text):
    hist, user_turns, r = [], [], None
    for _ in range(8):
        user_turns.append(text)
        r = client.post("/api/v1/triage", json={"user_input": text, "conversation_history": hist, "location": LOC,
                                                "debug": True}).json()
        if not r["follow_up_question"] or r["debug"].get("domain_class") != "health_request":
            break
        opts = r["debug"]["followup"].get("options") or []
        hist += [{"role": "user", "content": text}, {"role": "assistant", "content": r["follow_up_question"]}]
        text = next((o["label"] for o in opts if o["id"] == "none"), opts[-1]["label"] if opts else "Nahi")
    return r, user_turns


def _closed_corpus() -> str:
    """Text we wrote ourselves: configs and the fixed templates in the backend."""
    files = list((ROOT / "config").rglob("*.json")) + list((ROOT / "backend" / "app").rglob("*.py"))
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


CORPUS_NUMS = {n.replace(",", "") for n in NUM.findall(_closed_corpus())}


def _strings(x, skip=()):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k not in skip:
                yield from _strings(v, skip)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v, skip)


def _user_facing(r) -> list[str]:
    card = (r.get("debug") or {}).get("assessment") or {}
    sections = card.get("sections", {})
    texts = [r["follow_up_question"] or "", r["reasoning"] or ""]
    # possible causes and tests are closed lists (ids checked below); everything else is free-standing text
    texts += list(_strings({k: v for k, v in sections.items() if k not in ("causes", "tests")}, skip=("id", "evidence", "sources", "source")))
    return texts


def _allowed_numbers(user_turns) -> set[str]:
    nums = {n.replace(",", "") for t in user_turns for n in NUM.findall(t)}
    for n in list(nums):  # a Celsius reading is also shown as the Fahrenheit value it equals
        try:
            nums.add(f"{float(n) * 9 / 5 + 32:g}")
        except ValueError:
            pass
    return nums | CORPUS_NUMS


def test_input_count():
    assert len(INPUTS) >= 30


@pytest.mark.parametrize("text", INPUTS)
def test_numbers_come_from_input_or_closed_lists(text):
    r, turns = _run(text)
    allowed = _allowed_numbers(turns)
    for s in _user_facing(r):
        for n in NUM.findall(s):
            assert n.replace(",", "") in allowed, (n, s)


@pytest.mark.parametrize("text", INPUTS)
def test_present_symptoms_have_spans_in_user_words(text):
    r, turns = _run(text)
    said = " ".join(turns).lower()
    d = r["debug"]
    for sym, sp in (d.get("extracted_slots") or {}).get("evidence", {}).items():
        assert sp and (sp["text"] is None or sp["text"].lower() in said), (sym, sp)
    card = d.get("assessment") or {}
    for row in card.get("sections", {}).get("symptoms", {}).get("items", []):
        if row["status"] in ("present", "measured"):
            assert row["evidence"], row
            if row["evidence"]["text"] and row["evidence"]["kind"] != "earlier_answer":
                assert row["evidence"]["text"].lower() in said, row


@pytest.mark.parametrize("text", INPUTS)
def test_no_disease_or_medicine_names_unless_said(text):
    r, turns = _run(text)
    said = " ".join(turns).lower()
    bl = llm_triage._blocklist()
    for s in _user_facing(r):
        for m in bl.finditer(s):
            assert m.group(0).lower() in said, (m.group(0), s)


@pytest.mark.parametrize("text", INPUTS)
def test_possible_causes_only_from_closed_list(text):
    r, _ = _run(text)
    causes = (((r.get("debug") or {}).get("assessment") or {}).get("sections", {}).get("causes") or {}).get("items", [])
    for c in causes:
        assert c["id"] in llm_triage.pattern_ids(), c


@pytest.mark.parametrize("text", INPUTS)
def test_tests_only_from_closed_list(text):
    from app.assessment import load_cfg
    r, _ = _run(text)
    tests = (((r.get("debug") or {}).get("assessment") or {}).get("sections", {}).get("tests") or {}).get("items", [])
    for t in tests:
        assert t["id"] in load_cfg()["tests"], t


def test_unsupported_number_is_dropped():
    """A value the parser cannot point back to in the user's words is removed, never kept or estimated."""
    from app import evidence
    from app.pathways.slots import Slots
    s = Slots(temp_f=103.0, platelets=50000)
    spans = evidence.enforce_value_spans(s, ["papa ko bukhar hai"])
    assert s.temp_f is None and s.platelets is None and spans == {}


def test_citations_are_kb_chunks_and_deterministic():
    from app import kb
    r, _ = _run("Papa ko 39 C bukhar hai 3 din se")
    why = r["debug"]["assessment"]["sections"]["why"]
    assert why["sources"] and why["sources"][0]["id"].startswith("pathway:fever:")
    ids = {c["id"] for c in kb.chunks()}
    assert all(x["id"] in ids for x in why["sources"])
    assert kb.retrieve("abba dabba jabba") == []  # nothing relevant -> nothing cited
    assert len({tuple(x["id"] for x in kb.retrieve("fever cough breathing")) for _ in range(10)}) == 1

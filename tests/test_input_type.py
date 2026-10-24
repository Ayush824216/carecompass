"""Input-type classifier (scripts/train_input_type.py) and the model-free gibberish features."""
import pytest

from app import input_type as it
from app.config import get_settings

HAS_MODEL = (get_settings().models_dir / "input_type.joblib").exists()
needs_model = pytest.mark.skipif(not HAS_MODEL, reason="run scripts/train_input_type.py first")


@pytest.mark.parametrize("text", ["abba dabba jabba", "lala lala", "qwe rty", "asdf jkl", "zzzz", "kkkk"])
def test_gibberish_features_without_model(text):
    assert it.looks_gibberish(text)


@pytest.mark.parametrize("text", ["papa ko bukhar hai", "my mother has a cough", "early morning walk",
                                  "tell me something interesting", "मुझे दो दिन से बुखार है"])
def test_real_words_are_not_gibberish(text):
    assert not it.looks_gibberish(text)


def test_repeated_syllables():
    assert it.repeated_syllables("abba dabba jabba") and it.repeated_syllables("hahaha")
    assert not it.repeated_syllables("papa ko bukhar hai")


@needs_model
@pytest.mark.parametrize("text,cls", [
    ("dabba jabba tabba", "unclear_or_gibberish"), ("मकज फतल", "unclear_or_gibberish"),
    ("aaj ka panchang batao", "off_topic"), ("rcb ka next match kab hai", "off_topic"),
    ("hello bhaiya kaise ho", "greeting_smalltalk"), ("37*12", "math_or_code"),
])
def test_model_on_unseen_lines(text, cls):
    assert it.predict(text) == cls


@needs_model
def test_model_is_deterministic():
    assert len({it.predict("dabba jabba tabba") for _ in range(20)}) == 1


@needs_model
def test_report_has_per_class_f1_and_confusion():
    import json
    r = json.loads((get_settings().models_dir / "input_type_report.json").read_text(encoding="utf-8"))
    assert set(r["per_class_f1"]) == set(it.CLASSES) and len(r["confusion"]) == len(it.CLASSES)
    assert r["rows"]["gibberish"] >= 2000 and r["rows"]["off_topic"] + r["rows"]["greeting_smalltalk"] >= 1500

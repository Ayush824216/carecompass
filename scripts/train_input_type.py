"""Train the input-type classifier: health | greeting_smalltalk | off_topic | gibberish | math_or_code, plus the
intent classes joke_or_lyric | hypothetical | absurd_or_impossible | animal_patient | deceased_patient | past_event
(scripts/intent_data.py: generated EN / HI / Hinglish rows, >= 300 per class, with real-health look-alikes).

    python scripts/train_input_type.py [--seed 7]

Features: TF-IDF char_wb 2-5 grams + word 1-2 grams. Model: LogisticRegression, sigmoid-calibrated (3-fold).
Data (no real patients):
  health        our synthetic vignettes incl. clinical pathway cases (dev_data/vignettes.csv) + a sample of the
                public Symptoms-to-Diseases symptom text (data/public/symptoms_to_diseases, cited in DECLARATIONS)
  gibberish     generated: keyboard mashes, rhyming repeated syllables ("abba dabba jabba"), random Latin and
                Devanagari strings, emoji-only, very short noise (>= 2,000)
  math_or_code  generated arithmetic, equations, Hinglish sums, code snippets
  off_topic +   generated from templates plus hand-written English / Hinglish / Hindi lines (cricket, weather,
  greeting      politics, jokes, "kaise ho", "tum kaun ho") (>= 1,500 together)
The hand-written challenge sets are not used, so they stay unseen for the triage evaluation.

Evaluation: a group split by template id (no template is in both train and validation), per-class F1 and the
confusion matrix, written to models/input_type_report.json (docs/EVAL.md reads it). The final model is refit on
all rows and saved to models/input_type.joblib (gitignored, like every model file).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.input_type import CLASSES, build_pipeline  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from intent_data import intent_rows  # noqa: E402

# ---------------------------------------------------------------- generators
KEYROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890"]
CONS = "bcdfghjklmnpqrstvwxyz"
VOW = "aeiou"
EMOJI = ["\U0001F600", "\U0001F602", "\U0001F60D", "\U0001F44D", "\U0001F64F", "\U0001F525", "\U0001F389", "\U0001F914",
         "\U0001F60E", "\U0001F622", "❤️", "\U0001F44B", "\U0001F4AF", "✨", "\U0001F648"]
DEVA_LETTERS = [chr(c) for c in range(0x0915, 0x0939)]
DEVA_MATRA = ["", "ा", "ि", "ी", "ु", "ू", "े", "ै", "ो", "ं"]
NOISE = ["?", "??", "...", ".", "!!!", "k", "kk", "hm", "hmm", "hmmm", "a", "x", "xd", "zz", "zzz", "mmm", "uh", "umm",
         "asd", "-", "...?", "a1b2", "123abc", "@@", "#", "ok?!?", "jjj", "qq", "ppp", "aaaaa", "nnnn", ";;"]
SUFFIXES = ["bba", "ppa", "nga", "kka", "tta", "lla", "mma", "ddu", "ppu", "nku", "lli", "nki", "bbo", "ggi"]


def g_keymash(rng, variant):
    row = KEYROWS[variant % 3]
    words = []
    for _ in range(rng.randint(1, 4)):
        i = rng.randint(0, len(row) - 3)
        w = row[i:i + rng.randint(3, min(9, len(row) - i))]
        words.append(w if rng.random() < 0.7 else w[::-1])
    return " ".join(words)


def g_rhyme(rng, variant):
    suf = SUFFIXES[variant % len(SUFFIXES)]
    n = rng.randint(2, 4)
    return " ".join(rng.choice(CONS) + rng.choice(VOW) + suf if rng.random() < 0.85 else rng.choice(VOW) + suf
                    for _ in range(n))


def g_syllables(rng, variant):
    syl = [rng.choice(CONS) + rng.choice(VOW) for _ in range(2)]
    return " ".join("".join(rng.choice(syl) for _ in range(rng.randint(2, 3 + variant % 3))) for _ in range(rng.randint(1, 4)))


def g_latin(rng, variant):
    return " ".join("".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(2, 6 + variant % 6)))
                    for _ in range(rng.randint(1, 5)))


def g_deva(rng, variant):
    return " ".join("".join(rng.choice(DEVA_LETTERS) + rng.choice(DEVA_MATRA) for _ in range(rng.randint(1, 3 + variant % 3)))
                    for _ in range(rng.randint(1, 4)))


def g_emoji(rng, variant):
    return ("" if variant % 2 else " ").join(rng.choice(EMOJI) for _ in range(rng.randint(1, 6)))


def g_noise(rng, variant):
    return rng.choice(NOISE) if variant % 2 else "".join(rng.choice("?!.,;:-_*#@") for _ in range(rng.randint(1, 6)))


GIBBERISH = [("keymash", g_keymash, 6), ("rhyme", g_rhyme, 14), ("syllables", g_syllables, 6), ("latin", g_latin, 8),
             ("deva", g_deva, 6), ("emoji", g_emoji, 4), ("noise", g_noise, 4)]

NAMES = ["x", "y", "n", "total", "a", "b", "arr", "user", "data", "i"]
OPS = ["+", "-", "*", "/", "x"]


def _n(rng):
    return str(rng.randint(1, 999))


MATH_T = [
    lambda r: f"{_n(r)}{r.choice(OPS)}{_n(r)}",
    lambda r: f"{_n(r)} {r.choice(OPS)} {_n(r)} = ?",
    lambda r: f"what is {_n(r)} {r.choice(['plus', 'minus', 'times', 'divided by'])} {_n(r)}",
    lambda r: f"{_n(r)} aur {_n(r)} kitna hota hai",
    lambda r: f"{_n(r)} ko {_n(r)} se {r.choice(['guna', 'divide', 'plus', 'minus'])} karo",
    lambda r: f"solve {r.randint(2, 9)}x + {_n(r)} = {_n(r)}",
    lambda r: f"x^2 + {r.randint(1, 9)}x - {r.randint(1, 9)} = 0",
    lambda r: f"{r.randint(1, 99)}% of {_n(r)}",
    lambda r: f"integrate x^{r.randint(2, 5)} dx",
    lambda r: f"square root of {_n(r)}",
    lambda r: f"{_n(r)} का {r.randint(2, 20)} गुना कितना है",
    lambda r: f"calculate {_n(r)}*{_n(r)}+{_n(r)}",
]
CODE_T = [
    lambda r: f"print('{r.choice(['hello', 'hi', 'test', 'ok'])}')",
    lambda r: f"for {r.choice(NAMES)} in range({r.randint(1, 20)}): print({r.choice(NAMES)})",
    lambda r: f"def {r.choice(['add', 'f', 'sum2', 'calc'])}(a, b): return a {r.choice(OPS[:4])} b",
    lambda r: f"SELECT * FROM {r.choice(['users', 'orders', 'patients_demo'])} WHERE id = {_n(r)};",
    lambda r: f"console.log({r.choice(NAMES)});",
    lambda r: f"const {r.choice(NAMES)} = {_n(r)};",
    lambda r: f"int main() {{ return {r.randint(0, 9)}; }}",
    lambda r: f"<div class=\"{r.choice(['box', 'row'])}\">{r.choice(['hello', 'text'])}</div>",
    lambda r: f"git commit -m \"{r.choice(['fix', 'update', 'init'])}\"",
    lambda r: f"import {r.choice(['numpy', 'pandas', 'os', 'sys'])} as {r.choice(['np', 'pd', 'o'])}",
    lambda r: f"if ({r.choice(NAMES)} > {_n(r)}) {{ {r.choice(NAMES)}++; }}",
    lambda r: f"{r.choice(NAMES)} = [{_n(r)}, {_n(r)}, {_n(r)}].map(v => v * 2)",
]

GREET_HAND = [
    "hi", "hello", "hey", "hii", "hello ji", "namaste", "namaste ji", "namaskar", "good morning", "good evening",
    "good night", "kaise ho", "kaise ho aap", "aap kaise hain", "kya haal hai", "kya haal chaal", "sab theek?",
    "tum kaun ho", "aap kaun ho", "tumhara naam kya hai", "who are you", "what is your name", "how are you",
    "how r u", "what's up", "thank you", "thanks a lot", "shukriya", "dhanyavad", "ok", "okay", "theek hai",
    "achha", "bye", "alvida", "see you", "nice to meet you", "kya kar rahe ho", "aur batao", "aur sunao",
    "नमस्ते", "नमस्कार", "आप कैसे हैं", "तुम कौन हो", "धन्यवाद", "शुक्रिया", "शुभ प्रभात", "ठीक है", "राम राम",
    "sat sri akal", "salaam", "hello bhai", "hi didi", "good afternoon sir", "jai shri krishna", "hello there",
]
OFF_HAND = [
    "who won the cricket match yesterday", "aaj ka match kaun jeeta", "india ka score kya hai", "ipl final kab hai",
    "aaj mausam kaisa hai", "kal baarish hogi kya", "what is the weather in delhi", "delhi mein garmi kitni hai",
    "election kaun jeetega", "pm kaun hai", "who is the president of america", "ek joke sunao", "tell me a joke",
    "ek shayari sunao", "koi gaana sunao", "best movie of this year", "new film kab release hogi",
    "paneer butter masala kaise banate hain", "chai kaise banaye", "train ticket kaise book kare", "flight ka price",
    "mera phone hang ho raha hai", "laptop slow hai kya karu", "wifi password kya hai", "bitcoin ka rate",
    "share market aaj upar hai kya", "capital of france", "translate hello in french", "homework kar do",
    "essay likh do pollution par", "meri girlfriend naraz hai", "job kaise milegi", "salary kab aayegi",
    "recharge kaise kare", "instagram followers kaise badhaye", "pubg kaise khele", "mujhe ghoomne jana hai",
    "best hotel in goa", "क्रिकेट मैच कौन जीता", "आज मौसम कैसा है", "एक चुटकुला सुनाओ", "चुनाव कौन जीतेगा",
    "मेरा फोन खराब है", "नौकरी कैसे मिलेगी", "कहानी सुनाओ", "write a poem about the moon", "what time is it",
    "aaj kaun sa din hai", "tum kya kar sakte ho baaki", "python seekhna hai", "bike ki service kab karwani chahiye",
]
OFF_T = [
    lambda r: f"{r.choice(['india', 'australia', 'csk', 'mi', 'rcb'])} ka match {r.choice(['kaun jeeta', 'kab hai', 'kitne baje hai'])}",
    lambda r: f"who won the {r.choice(['cricket', 'football', 'hockey', 'kabaddi'])} {r.choice(['match', 'final', 'series'])}",
    lambda r: f"{r.choice(['kohli', 'dhoni', 'rohit'])} ne kitne run banaye",
    lambda r: f"aaj {r.choice(['delhi', 'mumbai', 'noida', 'lucknow', 'patna'])} mein mausam kaisa hai",
    lambda r: f"weather in {r.choice(['delhi', 'mumbai', 'pune', 'jaipur'])} {r.choice(['today', 'tomorrow'])}",
    lambda r: f"{r.choice(['bjp', 'congress', 'aap'])} election {r.choice(['jeetegi kya', 'kab hai', 'mein kitni seat'])}",
    lambda r: f"ek {r.choice(['joke', 'chutkula', 'kahani', 'shayari', 'kavita'])} {r.choice(['sunao', 'batao', 'likho'])}",
    lambda r: f"{r.choice(['biryani', 'dal makhani', 'poha', 'halwa', 'maggi'])} kaise {r.choice(['banate hain', 'banaye'])}",
    lambda r: f"{r.choice(['train', 'bus', 'flight', 'metro'])} ka {r.choice(['ticket', 'time', 'kiraya'])} {r.choice(['kitna hai', 'kaise milega'])}",
    lambda r: f"mera {r.choice(['phone', 'laptop', 'tv', 'fridge'])} {r.choice(['kharab ho gaya', 'chal nahi raha', 'slow hai'])}",
    lambda r: f"{r.choice(['best', 'sasta', 'accha'])} {r.choice(['mobile', 'laptop', 'scooter'])} kaunsa hai",
    lambda r: f"tell me about {r.choice(['history of india', 'the moon', 'dinosaurs', 'the taj mahal'])}",
    lambda r: f"{r.choice(['movie', 'film', 'web series'])} {r.choice(['suggest karo', 'kaunsi dekhu', 'recommend karo'])}",
    lambda r: f"{r.choice(['exam', 'result', 'admission'])} {r.choice(['kab aayega', 'kaise hoga', 'ki date'])}",
]
GREET_T = [
    lambda r: f"{r.choice(['hi', 'hello', 'hey', 'namaste'])} {r.choice(['bhai', 'didi', 'sir', 'madam', 'ji', 'dost', 'yaar'])}",
    lambda r: f"{r.choice(['hi', 'hello', 'namaste'])}, {r.choice(['kaise ho', 'kya haal hai', 'how are you', 'tum kaun ho'])}",
    lambda r: f"good {r.choice(['morning', 'evening', 'night', 'afternoon'])} {r.choice(['', 'ji', 'sir', 'everyone'])}".strip(),
    lambda r: f"{r.choice(['thank you', 'thanks', 'shukriya', 'dhanyavad'])} {r.choice(['', 'ji', 'so much', 'bhai'])}".strip(),
    lambda r: f"{r.choice(['tum', 'aap'])} {r.choice(['kaun ho', 'kya karte ho', 'kahan se ho', 'bot ho kya'])}",
]


def generate(rng: random.Random) -> list[dict]:
    rows = []
    for name, fn, nvar in GIBBERISH:
        for v in range(nvar):
            for _ in range(2400 // sum(n for *_, n in GIBBERISH) + 2):
                rows.append({"text": fn(rng, v), "label": "gibberish", "group": f"gib_{name}_{v}"})
    for i, fn in enumerate(MATH_T):
        rows += [{"text": fn(rng), "label": "math_or_code", "group": f"math_{i}"} for _ in range(70)]
    for i, fn in enumerate(CODE_T):
        rows += [{"text": fn(rng), "label": "math_or_code", "group": f"code_{i}"} for _ in range(50)]
    for i, fn in enumerate(OFF_T):
        rows += [{"text": fn(rng), "label": "off_topic", "group": f"off_{i}"} for _ in range(80)]
    for i, fn in enumerate(GREET_T):
        rows += [{"text": fn(rng), "label": "greeting_smalltalk", "group": f"greet_{i}"} for _ in range(130)]
    for i, t in enumerate(OFF_HAND):
        rows.append({"text": t, "label": "off_topic", "group": f"off_hand_{i % 10}"})
    for i, t in enumerate(GREET_HAND):
        rows.append({"text": t, "label": "greeting_smalltalk", "group": f"greet_hand_{i % 10}"})
    return rows


def health_rows(rng: random.Random, n_public: int = 1200) -> list[dict]:
    import pandas as pd
    rows = []
    v = pd.read_csv(ROOT / "dev_data" / "vignettes.csv")
    tid = v["template_id"] if "template_id" in v else pd.Series(range(len(v)))
    for t, g in zip(v["text"], tid.fillna("").astype(str)):
        rows.append({"text": str(t), "label": "health", "group": f"vig_{g or rng.randint(0, 50)}"})
    p = ROOT / "data" / "public" / "symptoms_to_diseases" / "final_symptoms_to_disease.csv"
    if p.exists():
        df = pd.read_csv(p, usecols=["diseases", "symptom_text"]).dropna()
        df = df.sample(min(n_public, len(df)), random_state=rng.randint(0, 10**6))
        for d, t in zip(df["diseases"], df["symptom_text"]):
            text = ", ".join(s.strip() for s in str(t).split(",")[:4])
            rows.append({"text": f"I have {text}", "label": "health", "group": f"s2d_{str(d).lower()}"})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    import joblib
    import numpy as np
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.model_selection import StratifiedGroupKFold

    rng = random.Random(a.seed)
    rows = health_rows(rng) + generate(rng) + intent_rows(rng)
    X = np.array([r["text"] for r in rows], dtype=object)
    y = np.array([r["label"] for r in rows])
    g = np.array([r["group"] for r in rows])
    counts = {c: int((y == c).sum()) for c in CLASSES}
    print("rows per class:", counts, file=sys.stderr)

    # every class keeps unseen groups (templates / frames) in validation
    tr, va = next(StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=a.seed).split(X, y, g))
    m = build_pipeline(a.seed).fit(X[tr], y[tr])
    pred = m.predict(X[va])
    rep = classification_report(y[va], pred, labels=list(CLASSES), output_dict=True, zero_division=0)
    cm = confusion_matrix(y[va], pred, labels=list(CLASSES)).tolist()
    report = {"classes": list(CLASSES), "rows": counts, "n_train": int(len(tr)), "n_val": int(len(va)),
              "split": "StratifiedGroupKFold by template/generator id (1 of 4 folds)", "seed": a.seed,
              "per_class_f1": {c: round(rep[c]["f1-score"], 3) for c in CLASSES},
              "support": {c: int(rep[c]["support"]) for c in CLASSES},
              "macro_f1": round(rep["macro avg"]["f1-score"], 3), "confusion": cm}
    print(json.dumps({k: report[k] for k in ("per_class_f1", "macro_f1")}), file=sys.stderr)

    final = build_pipeline(a.seed).fit(X, y)
    out = ROOT / "models"
    out.mkdir(exist_ok=True)
    joblib.dump(final, out / "input_type.joblib")
    (out / "input_type_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"wrote {out / 'input_type.joblib'}", file=sys.stderr)


if __name__ == "__main__":
    main()

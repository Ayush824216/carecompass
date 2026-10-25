"""Build config/medical_lexicon.json: the broad medical vocabulary used by the domain guard and evidence gate.

Sources (names only, never records):
  data/public/symptoms_to_diseases/data.csv    symptom columns + disease names
  data/public/symptom_severity/*.csv           itachi9604 disease-symptom dataset (symptoms + diseases)
  data/public/icd10/icd10cm_order_<year>.txt   CMS ICD-10-CM (public domain): 3-character categories A00-U85
plus the curated Hindi / Hinglish body parts and abnormal descriptors below.

Run:  python scripts/build_lexicon.py
"""
from __future__ import annotations

import csv
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "data" / "public"
OUT = ROOT / "config" / "medical_lexicon.json"

# body part -> spellings (EN / Hinglish / Devanagari). A body part with a descriptor is health evidence.
BODY_PARTS = {
    "aankh": ["aankh", "aankhe", "aankhen", "aankhon", "ankh", "ankhe", "ankhen", "eye", "eyes", "आँख", "आंख", "आँखें", "आंखें", "आँखों"],
    "kaan": ["kaan", "kan", "ear", "ears", "कान"],
    "naak": ["naak", "nak", "nose", "नाक"],
    "gala": ["gala", "gale", "galaa", "throat", "गला", "गले"],
    "daant": ["daant", "dant", "daant", "daanton", "teeth", "tooth", "masoode", "masude", "gums", "दाँत", "दांत", "मसूड़े"],
    "muh": ["muh", "munh", "mooh", "mouth", "hont", "honth", "lips", "jeebh", "tongue", "मुँह", "मुंह", "होंठ", "जीभ"],
    "pet": ["pet", "stomach", "tummy", "belly", "abdomen", "पेट"],
    "sir": ["sir", "sar", "head", "सिर", "सर"],
    "haath": ["haath", "hath", "hand", "hands", "arm", "arms", "ungli", "finger", "fingers", "हाथ", "उंगली"],
    "pair": ["pair", "pair", "pairon", "leg", "legs", "foot", "feet", "taang", "tang", "edi", "पैर", "टांग", "एड़ी"],
    "kamar": ["kamar", "peeth", "back", "spine", "कमर", "पीठ"],
    "chhati": ["chhati", "chati", "seena", "seene", "chest", "छाती", "सीना", "सीने"],
    "twacha": ["twacha", "tvacha", "chamdi", "chamri", "skin", "त्वचा", "चमड़ी"],
    "gardan": ["gardan", "neck", "गर्दन"],
    "ghutna": ["ghutna", "ghutne", "knee", "knees", "joint", "joints", "jod", "घुटना", "घुटने", "जोड़"],
    "nakhun": ["nakhun", "nakhoon", "nail", "nails", "नाखून"],
    "baal": ["baal", "hair", "scalp", "बाल"],
    "peshab": ["peshab", "urine", "पेशाब"],
    "sharir": ["sharir", "shareer", "badan", "body", "शरीर", "बदन"],
}
# abnormal descriptor -> spellings
DESCRIPTORS = {
    "peela": ["peela", "peeli", "peele", "pila", "pili", "pile", "yellow", "पीला", "पीली", "पीले"],
    "laal": ["laal", "lal", "red", "redness", "लाल"],
    "soojan": ["soojan", "sujan", "soojna", "sooj", "swelling", "swollen", "सूजन", "सूज"],
    "dard": ["dard", "dardh", "pain", "painful", "ache", "aching", "दर्द"],
    "khujli": ["khujli", "khujlee", "itch", "itching", "itchy", "खुजली"],
    "jalan": ["jalan", "jalna", "burning", "जलन"],
    "khoon": ["khoon", "khun", "blood", "bleeding", "खून"],
    "sunn": ["sunn", "sun", "numb", "numbness", "सुन्न"],
    "pani": ["paani aana", "pani aana", "paani aa raha", "pani aa raha", "discharge", "watery", "पानी आना"],
    "mavaad": ["mavaad", "mawad", "pus", "पस", "मवाद"],
    "daane": ["daane", "dane", "rash", "rashes", "spots", "pimples", "दाने"],
    "kharab": ["kharab", "kamzor", "dhundhla", "blurry", "blurred", "weak", "खराब", "कमज़ोर", "धुंधला"],
    "kala": ["neela", "neeli", "blue", "kaala pad", "black", "नीला", "नीली"],
}
GENERIC_ICD = set("""other unspecified specified disorders disorder diseases disease conditions condition due with without and
of in the to or by not elsewhere classified certain types type sequelae following complications complication abnormal findings
person persons encounter contact status history family examination problems problem factors care services related health
special personal procedures procedure effects effect late acute chronic primary secondary multiple single site sites region
regions part parts organs organ system systems general symptoms signs involving affecting injury injuries unknown cause
causes newborn perinatal period maternal mother fetus pregnancy childbirth puerperium medical surgical inner outer upper
lower middle anterior posterior right left nature mental behavioural behavioral respiratory involvement artificial
opening elevated decreased increased reduced presence absence deficiency poisoning exposure foreign object complications
congenital malformations deformations chromosomal acquired transport accidents legal intervention operations assault
specific applied mechanical personality conduct breaks solid recent occur uncertain transmitted disseminated
localized dietary postprocedural behaviour behavior noninfective noninfectious pressure""".split())


MED_SUFFIX = re.compile(r"(itis|osis|oses|emia|aemia|oma|omas|pathy|algia|plegia|iasis|rrhoea|rrhea|uria|cele|ectomy|"
                        r"cocc\w*|virus|viral|bacter\w*|fung\w*|ulcer\w*|cancer\w*|tumou?r\w*|neoplasm\w*|fever|infect\w*)$")


def _norm(s: str) -> str:
    s = s.replace("_", " ").strip().lower()
    s = re.sub(r"\s+", " ", re.sub(r"[()\[\],;:]", " ", s))
    return s.strip()


def symptoms_and_diseases() -> tuple[set[str], set[str]]:
    syms, dis = set(), set()
    f = PUB / "symptoms_to_diseases" / "data.csv"
    if f.exists():
        with f.open(encoding="utf-8", errors="ignore") as fh:
            r = csv.reader(fh)
            header = next(r)
            syms |= {_norm(h) for h in header[1:]}
            for row in r:
                if row:
                    dis.add(_norm(row[0]))
    for f in glob.glob(str(PUB / "symptom_severity" / "*.csv")):
        with open(f, encoding="utf-8", errors="ignore") as fh:
            r = csv.reader(fh)
            header = [h.strip().lower() for h in next(r)]
            for row in r:
                if not row:
                    continue
                if header[0] == "disease":
                    dis.add(_norm(row[0]))
                    if len(header) > 1 and header[1].startswith("symptom"):  # not the description / precaution text
                        syms |= {_norm(x) for x in row[1:] if x.strip()}
                elif header[0] == "symptom":
                    syms.add(_norm(row[0]))
    return {s for s in syms if len(s) >= 3}, {d for d in dis if len(d) >= 3}


def icd10() -> list[dict]:
    files = sorted(glob.glob(str(PUB / "icd10" / "icd10cm_order_*.txt")))
    files = [f for f in files if "addenda" not in f]
    if not files:
        return []
    out = []
    for line in Path(files[-1]).read_text(encoding="utf-8", errors="ignore").splitlines():
        code = line[6:13].strip()
        if len(code) != 3 or code[0] in "VWXYZ":  # external causes and encounter / status codes are not complaints
            continue
        out.append({"code": code, "name": line[77:].strip() or line[16:76].strip()})
    return out


def main() -> int:
    syms, dis = symptoms_and_diseases()
    cats = icd10()
    if not cats:
        print("ICD-10-CM order file not found in data/public/icd10/ (download the CMS code descriptions)", file=sys.stderr)
    icd_terms = {_norm(c["name"]) for c in cats}
    # single words that are medical on their own: one-word disease / symptom / ICD names, words with a medical
    # suffix, and nouns that recur across ICD category names (never generic words such as "other", "inner")
    from collections import Counter
    names = dis | icd_terms
    recur = Counter(w for t in icd_terms for w in set(t.split()))
    words = {t for t in names | syms if " " not in t and t.isalpha() and len(t) >= 4}
    words |= {w for t in names | syms for w in t.split() if w.isalpha() and MED_SUFFIX.search(w)}
    words |= {w for w, n in recur.items() if n >= 3 and len(w) >= 6 and w.isalpha()}
    words -= GENERIC_ICD
    lex = {
        "_note": "Generated by scripts/build_lexicon.py. Names only (no records): symptoms_to_diseases, itachi9604 "
                 "disease-symptom dataset, CMS ICD-10-CM 3-character categories (public domain), curated body parts and descriptors.",
        "symptoms": sorted(syms),
        "diseases": sorted(dis),
        "icd10": cats,
        "terms": sorted(words),
        "body_parts": BODY_PARTS,
        "descriptors": DESCRIPTORS,
    }
    OUT.write_text(json.dumps(lex, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"symptoms={len(syms)} diseases={len(dis)} icd10={len(cats)} terms={len(words)} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

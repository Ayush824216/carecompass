"""Clinical pathway engine (docs/CLINICAL_PATHWAYS.md).

Each pathway (config/pathways/<id>.json) has a trigger, signs, stage rules, default routing per stage and a
4-question senior-doctor tree. Shared signs, risk modifiers and the S0-S3 ladder live in _common.json.

Flow: parse slots + signs from the patient's own, current clauses -> merge chip answers -> for every triggered
pathway evaluate its rules (highest stage wins) -> apply risk modifiers -> result. Missing information can only
leave a rule unfired; it never lowers urgency.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

from ..config import get_settings
from ..lang import clean, normalise
from ..safety import _negated
from . import expr
from .slots import Slots, parse, split_clauses

STAGES = ["S0", "S1", "S2", "S3"]
URG_RANK = {"routine": 0, "same_day": 1, "immediate": 2}
LANGS = ("en", "hi", "hinglish")


def _stage_i(s: str) -> int:
    return STAGES.index(s)


@dataclass
class Pathway:
    id: str
    cfg: dict

    @property
    def label(self) -> dict:
        return self.cfg["label"]

    def stage_route(self, stage: str) -> dict:
        return self.cfg["stages"][stage]


@lru_cache
def load() -> tuple[dict, dict[str, Pathway], dict[str, dict]]:
    """(common config, pathways by id, all signs by id). Validates every rule expression at load time."""
    d = get_settings().config_dir / "pathways"
    common = json.loads((d / "_common.json").read_text(encoding="utf-8"))
    pathways: dict[str, Pathway] = {}
    signs: dict[str, dict] = dict(common["signs"])
    for pid in common["priority"]:
        cfg = json.loads((d / f"{pid}.json").read_text(encoding="utf-8"))
        pathways[pid] = Pathway(pid, cfg)
        signs.update(cfg.get("signs", {}))
    for p in pathways.values():
        exprs = [p.cfg["trigger"], p.cfg.get("sufficient", "False")] + [r["when"] for r in p.cfg["rules"]]
        exprs += [q.get("skip_if", "False") for q in p.cfg["questions"]] + [q.get("only_if", "True") for q in p.cfg["questions"]]
        for e in exprs:
            expr.compile_expr(e)
    for m in common["modifiers"]:
        expr.compile_expr(m["when"])
    return common, pathways, signs


@lru_cache
def _compiled_signs() -> dict[str, list[re.Pattern]]:
    _, _, signs = load()
    return {sid: [re.compile(p, re.I) for p in spec["patterns"]] for sid, spec in signs.items()}


def sign_label(sid: str, lang: str) -> str:
    _, _, signs = load()
    lab = signs.get(sid, {}).get("label", {})
    return lab.get(lang) or lab.get("en") or sid.replace("_", " ")


def detect_signs(slots: Slots) -> dict[str, bool]:
    """sign -> True (affirmed) / False (explicitly negated). Only the patient's current clauses are scanned."""
    out: dict[str, bool] = {}
    for cl in slots.patient_clauses:
        for variant in (cl.lower(), normalise(cl)):
            for sid, pats in _compiled_signs().items():
                if out.get(sid) is True:
                    continue
                for p in pats:
                    for m in p.finditer(variant):
                        if _negated(variant, m.start(), m.end()):
                            out.setdefault(sid, False)
                        else:
                            out[sid] = True
                            break
                    if out.get(sid) is True:
                        break
    if slots.correction:  # "khoon nahi... nahi ruko, thoda sa aaya tha": the later statement wins (safer)
        for sid, v in list(out.items()):
            if v is False:
                out[sid] = True
    return out


# ---------------------------------------------------------------- answers to pathway questions
@lru_cache
def question_index() -> dict[str, tuple[str, dict]]:
    """Normalised question text (any language) -> (pathway id, question)."""
    _, pathways, _ = load()
    idx = {}
    for p in pathways.values():
        for q in p.cfg["questions"]:
            for lang in LANGS:
                key = _norm(q["text"][lang])
                if key in idx and idx[key][1]["id"] != q["id"]:  # answers are matched by question text
                    raise ValueError(f"question text not unique: {q['text'][lang]!r} ({q['id']} vs {idx[key][1]['id']})")
                idx[key] = (p.id, q)
    return idx


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", clean(s).lower()).strip()


def identify_question(text: str) -> Optional[str]:
    hit = question_index().get(_norm(text or ""))
    return hit[1]["id"] if hit else None


def _none_label(q: dict) -> dict:
    common, _, _ = load()
    return q.get("none_label") or common["none_chip"]["label"]


def chip_options(q: dict, lang: str) -> list[dict]:
    """Chips for the client. `severity`: definite_S3 (emergency at once) | needs_confirmation (one targeted
    follow-up) | None. `single`: pick one chip (e.g. a temperature band) instead of multi-select."""
    opts = [{"id": c["id"], "label": c["label"].get(lang) or c["label"]["en"], "severity": c.get("severity")}
            for c in q["chips"]]
    if not q.get("no_none_chip"):
        nl = _none_label(q)
        opts.append({"id": "none", "label": nl.get(lang) or nl["en"], "exclusive": True, "severity": None})
    return opts


@dataclass
class Answers:
    facts: dict[str, Any] = field(default_factory=dict)
    negated: set[str] = field(default_factory=set)
    asked: list[str] = field(default_factory=list)
    confirm_asked: list[str] = field(default_factory=list)  # danger-confirmation questions (not counted in the 4)
    definite: list[str] = field(default_factory=list)  # chip ids answered that are definite_S3
    chips: dict[str, list[str]] = field(default_factory=dict)  # question id -> chip ids chosen ("none" included)

    @property
    def n_clinical(self) -> int:
        return len([q for q in self.asked if q not in self.confirm_asked])


def parse_answers(history: list[dict], user_input: str) -> Answers:
    """Read chip / free-text answers to pathway questions out of the (stateless) conversation history."""
    turns = [(t.get("role", "user"), t.get("content", "") or "") for t in history]
    if not turns or turns[-1] != ("user", user_input):
        turns.append(("user", user_input))
    ans = Answers()
    pending: Optional[dict] = None
    for role, content in turns:
        if role == "assistant":
            hit = question_index().get(_norm(content))
            pending = hit[1] if hit else None
            if pending:
                ans.asked.append(pending["id"])
                if pending.get("kind") == "confirm":
                    ans.confirm_asked.append(pending["id"])
            continue
        if role != "user" or pending is None:
            continue
        apply_chip_answer(ans, pending, _chosen_chips(pending, content), _is_none(pending, content))
        pending = None
    return ans


def _chosen_chips(q: dict, content: str) -> list[dict]:
    low = _norm(content)
    # longest labels first, so "Aaram mein bhi saans phool rahi" is not also read as a shorter overlapping label
    found, rest = [], low
    for c in sorted(q["chips"], key=lambda c: -max(len(c["label"][l]) for l in LANGS)):
        for l in LANGS:
            lab = _norm(c["label"][l])
            if lab and lab in rest:
                found.append(c)
                rest = rest.replace(lab, " ")
                break
    return found


def _is_none(q: dict, content: str) -> bool:
    if q.get("no_none_chip"):
        return False
    nl = _none_label(q)
    return any(_norm(nl[l]) in _norm(content) for l in LANGS)


def apply_chip_answer(ans: Answers, q: dict, chosen: list[dict], none: bool) -> None:
    """Merge one answer into the facts. Positive answers only ever add; "None" negates the chips' signs."""
    for c in chosen:
        for k, v in c["facts"].items():
            if isinstance(v, bool):
                ans.facts[k] = ans.facts.get(k, False) or v
            else:
                ans.facts[k] = max(ans.facts.get(k) or v, v)
        if c.get("severity") == "definite_S3":
            ans.facts["definite_s3_answer"] = True
            ans.definite.append(c["id"])
    if none and not chosen:
        for c in q["chips"]:
            ans.negated |= {k for k, v in c["facts"].items() if v is True}
    ans.chips[q["id"]] = [c["id"] for c in chosen] + (["none"] if none and not chosen else [])


# ---------------------------------------------------------------- facts
def build_facts(slots: Slots, signs: dict[str, bool], answers: Optional[Answers] = None) -> tuple[dict, set[str], set[str]]:
    """facts for rule evaluation, explicitly negated names, and names known (asked/stated)."""
    f: dict[str, Any] = {sid: v is True for sid, v in signs.items()}
    neg = {sid for sid, v in signs.items() if v is False}
    age = slots.age_years
    f.update({
        "temp_f": slots.effective_temp_f, "measured_temp": slots.temp_f, "duration_days": slots.duration_days,
        "age_years": age, "platelets": slots.platelets, "bp_sys": slots.bp_sys, "bp_dia": slots.bp_dia,
        "vomit_count": slots.vomit_count, "stool_count": slots.stool_count, "urine_absent_hours": slots.urine_absent_hours,
        "pregnancy_weeks": slots.pregnancy_weeks, "high_fever_reported": slots.high_fever_reported,
        "mild_fever": slots.mild_fever_reported, "blood_large": slots.blood_amount == "large",
        "blood_small": slots.blood_amount == "small", "pregnant": slots.pregnant, "comorbid": bool(slots.comorbidities),
        "diabetes": "diabetes" in slots.comorbidities, "heart": "heart" in slots.comorbidities,
        "hypertension": slots.hypertension or slots.bp_high_reported, "smoker": slots.smoker or f.get("smoker", False),
        "bedridden": slots.bedridden,
        "infant": slots.age_group == "infant" or (age is not None and age < 1),
        "young_infant": age is not None and age < 0.25,
        "child": slots.age_group in ("infant", "child") or (age is not None and age < 12),
        "elderly": slots.age_group == "elderly" or (age is not None and age >= 65),
        "age40": age is not None and age >= 40,
    })
    for d in slots.named_diseases:
        f[f"named_{d}"] = True
    known: set[str] = {k for k, v in f.items() if v not in (None, False)} | neg
    if answers:
        for k, v in answers.facts.items():
            if isinstance(v, bool):
                f[k] = bool(f.get(k)) or v
            else:
                f[k] = max(f[k], v) if f.get(k) is not None else v
            known.add(k)
        for k in answers.negated:
            if not f.get(k):
                neg.add(k)
                known.add(k)
    f["under5"] = f.get("under5") or (f["child"] and (f["age_years"] is None or f["age_years"] < 5))
    if f["age_years"] is not None:
        f["age40"] = f["age40"] or f["age_years"] >= 40
        f["elderly"] = f["elderly"] or f["age_years"] >= 65
    if f.get("temp_f") is not None and f["temp_f"] >= 100.4:
        f["fever"] = True
    return f, neg, known


def _funcs(facts: dict, neg: set[str], known: set[str]) -> dict:
    return {
        "known": lambda name: name in known or (facts.get(name) not in (None, False)),
        "no": lambda name: name in neg,
        "named": lambda name: bool(facts.get(f"named_{name}")),
    }


# ---------------------------------------------------------------- evaluation
@dataclass
class PathwayResult:
    pathway: str
    stage: str
    care_type: str
    urgency: str
    explicit: bool
    rule_ids: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    signs: list[str] = field(default_factory=list)
    slot_refs: list[str] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _sign_names(src: str, facts: dict) -> list[str]:
    _, _, signs = load()
    return [n for n in expr.names_in(src) if n in signs and facts.get(n) is True]


SLOT_NAMES = ("temp_f", "duration_days", "platelets", "bp_sys", "vomit_count", "stool_count", "urine_absent_hours", "age_years")


def evaluate_pathway(p: Pathway, facts: dict, neg: set[str], known: set[str]) -> PathwayResult:
    common, _, _ = load()
    fn = _funcs(facts, neg, known)
    matched = [r for r in p.cfg["rules"] if expr.evaluate(r["when"], facts, fn)]
    if matched:
        top = max(_stage_i(r["stage"]) for r in matched)
        best = [r for r in matched if _stage_i(r["stage"]) == top]
        r0 = best[0]
        stage = r0["stage"]
        route = p.stage_route(stage)
        res = PathwayResult(p.id, stage, r0.get("care_type", route["care_type"]), r0.get("urgency", route["urgency"]), True)
        for r in best:
            res.rule_ids.append(r["id"])
            if r.get("pattern") and r["pattern"] not in res.patterns:
                res.patterns.append(r["pattern"])
            if r.get("note"):
                res.notes.append(r["note"])
            for s in _sign_names(r["when"], facts):
                if s not in res.signs:
                    res.signs.append(s)
            res.slot_refs += [n for n in expr.names_in(r["when"]) if n in SLOT_NAMES and facts.get(n) is not None and n not in res.slot_refs]
    else:
        route = p.stage_route("S0")
        res = PathwayResult(p.id, "S0", route["care_type"], route["urgency"], False)

    raised = 0
    for m in common["modifiers"]:
        if m["pathways"] != "*" and p.id not in m["pathways"]:
            continue
        if not expr.evaluate(m["when"], facts, fn):
            continue
        eff = m["effect"]
        if eff == "min_stage" and _stage_i(res.stage) < _stage_i(m["stage"]):
            res.stage = m["stage"]
            route = p.stage_route(res.stage)
            res.care_type, res.urgency = route["care_type"], route["urgency"]
            res.explicit = True
            res.modifiers.append(m["id"])
        elif eff == "raise" and raised < common.get("max_total_raise", 1) and res.stage != "S3":
            base = res.stage
            res.stage = STAGES[_stage_i(res.stage) + 1]
            route = p.stage_route(res.stage)
            # care after a raise: the new stage's default when coming from S0 or when the pathway says so
            # (cough, stomach); fever keeps the base rule's care (spec 1.6: elderly chikungunya-like stays home visit)
            if res.stage == "S3" or base == "S0" or p.cfg.get("raise_care", "stage_default") == "stage_default":
                res.care_type = route["care_type"]
            res.urgency = max(res.urgency, route["urgency"], key=lambda u: URG_RANK[u])
            res.explicit = True
            raised += 1
            res.modifiers.append(m["id"])
        elif eff == "prefer_home" and res.care_type == "gp_teleconsult":
            res.care_type = "paramedic_home_visit"
            res.modifiers.append(m["id"])
    if res.stage == "S3":
        res.care_type, res.urgency = "emergency_referral", "immediate"
    return res


@dataclass
class PathwayOutcome:
    results: list[PathwayResult]
    facts: dict
    neg: set[str]
    known: set[str]
    slots: Slots
    answers: Answers

    @property
    def primary(self) -> Optional[PathwayResult]:
        """Most severe pathway; ties broken by the spec priority (chest pain dominates)."""
        if not self.results:
            return None
        common, _, _ = load()
        pr = common["priority"]
        return sorted(self.results, key=lambda r: (-_stage_i(r.stage), pr.index(r.pathway)))[0]

    @property
    def urgency(self) -> Optional[str]:
        return max((r.urgency for r in self.results), key=lambda u: URG_RANK[u], default=None)


def run(user_texts: list[str], history: Optional[list[dict]] = None, user_input: str = "") -> PathwayOutcome:
    common, pathways, _ = load()
    slots = parse(user_texts)
    signs = detect_signs(slots)
    answers = parse_answers(history or [], user_input) if history is not None else Answers()
    facts, neg, known = build_facts(slots, signs, answers)
    fn = _funcs(facts, neg, known)
    results = []
    for pid in common["priority"]:
        p = pathways[pid]
        if expr.evaluate(p.cfg["trigger"], facts, fn):
            results.append(evaluate_pathway(p, facts, neg, known))
    return PathwayOutcome(results, facts, neg, known, slots, answers)


# ---------------------------------------------------------------- senior-doctor questioning
def next_question(out: PathwayOutcome, n_clinical_asked: int, max_q: int = 4) -> Optional[dict]:
    """Next question of the primary pathway's tree, or None to decide now.
    Stop immediately on S3. A triggered danger confirmation comes first (one per conversation, outside the cap of
    max_q clinical questions). Then danger screen first, skipping what is known."""
    prim = out.primary
    if prim is None or prim.stage == "S3":
        return None
    _, pathways, _ = load()
    p = pathways[prim.pathway]
    trigger_names = set(expr.names_in(p.cfg["trigger"]))
    n_signs = sum(1 for k, v in out.facts.items() if v is True and k in _compiled_signs() and k not in trigger_names)
    facts = dict(out.facts, n_signs=n_signs)
    fn = _funcs(facts, out.neg, out.known)
    if not out.answers.confirm_asked:
        for res in [prim] + [r for r in out.results if r is not prim]:
            for q in pathways[res.pathway].cfg["questions"]:
                if q.get("kind") == "confirm" and expr.evaluate(q.get("only_if", "False"), facts, fn) \
                        and not expr.evaluate(q.get("skip_if", "False"), facts, fn):
                    return q
    if n_clinical_asked >= max_q:
        return None
    if expr.evaluate(p.cfg.get("sufficient", "False"), facts, fn):
        return None
    for q in p.cfg["questions"]:
        if q["id"] in out.answers.asked or q.get("kind") == "confirm":
            continue
        if not expr.evaluate(q.get("only_if", "True"), facts, fn):
            continue
        if expr.evaluate(q.get("skip_if", "False"), facts, fn):
            continue
        return q
    return None


def question_text(q: dict, lang: str) -> str:
    return q["text"].get(lang) or q["text"]["en"]

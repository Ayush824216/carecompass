"""Orchestration: lang -> normalise -> safety -> (emergency | intake -> follow-up | triage -> safety re-check -> matching)."""
from __future__ import annotations

import logging
import time
from dataclasses import asdict
from typing import Optional

from . import domain_guard, explain, intake, llm_triage, matching, pathways, safety
from .config import get_settings
from .pathways import route as proute
from .lang import detect_language, normalise, resolve_language, term_matches
from .llm import available as llm_available
from .schemas import (EMERGENCY_CARE_TYPE, MOST_URGENT, URGENCY_RANK, MatchedCaregiver, TriageRequest,
                      TriageResponse)
from .triage import Decision, combine, decide_from_probs, local_decision
from .textclf import best_local_model

log = logging.getLogger("carecompass.pipeline")

FALLBACK_REASON = {
    "en": "We could not fully assess this automatically, so a doctor should speak to you today.",
    "hi": "हम इसे पूरी तरह से नहीं समझ पाए, इसलिए आज ही डॉक्टर से बात करना ठीक रहेगा।",
    "hinglish": "Hum ise poori tarah samajh nahi paaye, isliye aaj hi doctor se baat karna theek rahega.",
}
MODEL_EMERGENCY = {
    "en": "The details you shared suggest this may be serious. ",
    "hi": "आपकी बताई बातों से यह गंभीर लग सकता है। ",
    "hinglish": "Aapki batayi baaton se yeh gambhir lag sakta hai. ",
}


def _user_turns(req: TriageRequest) -> list[str]:
    turns = [t.content for t in req.conversation_history if t.role == "user" and t.content]
    if not turns or turns[-1] != req.user_input:
        turns.append(req.user_input)
    return turns


def _language(req: TriageRequest, user_turns: list[str]) -> str:
    if req.language != "auto":
        return req.language
    # a bare answer ("haan", "2 din") is weak evidence: use the longest user turn
    return detect_language(max(user_turns, key=len)) if user_turns else "en"


def _extra_flags(state: intake.IntakeState) -> list[str]:
    flags = list(state.extra_flags)
    if state.slots.answers.get("drinking") == "no" and state.slots.age_group == "infant":
        flags.append("infant_danger_signs")
    return flags


def apply_persistence_rule(dec: Decision, slots, text: str) -> bool:
    """Long-standing, organ-specific problems favour a specialist over a GP teleconsult (taxonomy definition).
    Only flips GP -> specialist when the local model already gives the specialist some probability."""
    if dec.care_type != "gp_teleconsult" or slots.duration not in ("week", "chronic"):
        return False
    if not matching.infer_specialties(slots.symptoms, None, text):
        return False
    p_spec = (dec.probs or {}).get("care_type", {}).get("specialist_referral", 0.0)
    if p_spec < 0.15:
        return False
    dec.care_type = "specialist_referral"
    dec.source = f"{dec.source}+persistence_rule"
    return True


def emergency_response(flags: list[str], lang: str, prefix: str = "") -> TriageResponse:
    return TriageResponse(follow_up_question=None, care_type=EMERGENCY_CARE_TYPE, urgency=MOST_URGENT,
                          red_flags=flags, reasoning=prefix + safety.emergency_reasoning(flags, lang)
                          if flags else prefix + safety.STEPS.get(lang, safety.STEPS["en"]),
                          matched_caregivers=[])


def pathway_flags(pout) -> list[str]:
    """Red-flag ids for a pathway decision: its signs and modifiers, else neutral reading-based ids
    (rule ids are internal and may carry concern-pattern words, so they never reach red_flags)."""
    prim = pout.primary
    flags = prim.signs + prim.modifiers + [proute.SLOT_FLAGS[s] for s in prim.slot_refs if s in proute.SLOT_FLAGS]
    return list(dict.fromkeys(flags)) or ["pathway_danger_sign"]


def pathway_emergency(pout, lang: str, safety_flags: list[str]) -> TriageResponse:
    """S3 from a pathway: emergency path with the pathway's danger signs in plain words."""
    flags = list(dict.fromkeys(list(safety_flags) + pathway_flags(pout)))
    return TriageResponse(follow_up_question=None, care_type=EMERGENCY_CARE_TYPE, urgency=MOST_URGENT, red_flags=flags,
                          reasoning=proute.emergency_reasoning(pout, lang, safety_flags), matched_caregivers=[])


def _pending_clinical_question(req: TriageRequest):
    """Id of the clinical follow-up the user is answering now, if the last assistant turn was one."""
    for t in reversed(req.conversation_history):
        if t.role == "assistant":
            return intake.identify_question(t.content)
        if t.role == "user" and t.content and t.content != req.user_input:
            return None
    return None


def _history_text(req: TriageRequest) -> str:
    return "\n".join(f"{t.role}: {t.content}" for t in req.conversation_history[-8:] if t.content)


def run(req: TriageRequest, use_llm: bool = True, trace: Optional[dict] = None) -> TriageResponse:
    """Run the pipeline. If `trace` is a dict it is filled with a decision trace (used only for ?debug=true)."""
    timings: dict[str, float] = {}
    tr = trace if trace is not None else {}
    t0 = time.perf_counter()
    lang = "en"
    turns: list[str] = [req.user_input]
    try:
        turns = _user_turns(req)
        lang = _language(req, turns)
        timings["language"] = time.perf_counter() - t0
        tr["detected_language"] = lang
        tr["normalised_text"] = normalise(" . ".join(turns))
        tr["term_matches"] = term_matches(" . ".join(turns))

        t = time.perf_counter()
        state = intake.build_state(req.user_input, [h.model_dump() for h in req.conversation_history])
        timings["intake"] = time.perf_counter() - t
        tr["extracted_slots"] = asdict(state.slots)
        tr["followup"] = {"asked_so_far": state.n_assistant_questions, "max": get_settings().max_followups,
                          "question_id": None}

        t = time.perf_counter()
        sres = safety.check(turns + [state.model_text], extra_flags=_extra_flags(state))
        timings["safety"] = time.perf_counter() - t
        tr["safety_checks"] = {"red_flags": sres.red_flags, "evidence": sres.evidence,
                               "categories_checked": len(safety.FLAG_LABELS), "stage": "pre_model"}
        if sres.is_emergency:
            tr["domain_class"] = domain_guard.HEALTH
            tr["model_used"] = "rules"
            return emergency_response(sres.red_flags, lang)

        # domain guard: only health requests go further (safety above always runs first)
        answering = _pending_clinical_question(req) is not None
        dclass = domain_guard.classify(req.user_input, answering_clinical_question=answering)
        tr["domain_class"] = dclass
        if dclass != domain_guard.HEALTH:
            tr["model_used"] = "domain_guard"
            return TriageResponse(follow_up_question=domain_guard.redirect_text(dclass, lang), care_type=None,
                                  urgency=None, red_flags=[], reasoning="", matched_caregivers=[])

        # clinical pathways (fever, cough, stomach, chest pain, headache): stage rules + senior-doctor questions
        t = time.perf_counter()
        pout = pathways.run(turns, history=[h.model_dump() for h in req.conversation_history], user_input=req.user_input)
        prim = pout.primary
        timings["pathways"] = time.perf_counter() - t
        tr["pathways"] = proute.trace(pout, lang)
        if prim is not None and prim.stage == "S3":
            tr["model_used"] = f"pathway:{prim.pathway}"
            return pathway_emergency(pout, lang, sres.red_flags)

        t = time.perf_counter()
        local = local_decision(state.model_text)
        timings["local_model"] = time.perf_counter() - t
        if local:
            tr["local_model"] = {"name": local.source, "care_type": local.care_type, "urgency": local.urgency,
                                 "probs": {k: {c: round(p, 3) for c, p in v.items()} for k, v in local.probs.items()}}

        if prim is not None:  # pathway complaint: the pathway's question tree replaces the generic follow-ups
            pq = pathways.next_question(pout, state.n_assistant_questions, get_settings().max_followups)
            if pq:
                tr["followup"].update({"question_id": pq["id"], "pathway": prim.pathway, "multi": True,
                                       "options": pathways.chip_options(pq, lang)})
                tr["model_used"] = f"pathway:{prim.pathway}"
                return TriageResponse(follow_up_question=pathways.question_text(pq, lang), care_type=None,
                                      urgency=None, red_flags=[], reasoning="", matched_caregivers=[])
        else:
            q = intake.choose_followup(state, local.probs if local else None)
            if q:
                tr["followup"]["question_id"] = q
                tr["model_used"] = local.source if local else "default"
                return TriageResponse(follow_up_question=intake.question_text(q, lang), care_type=None, urgency=None,
                                      red_flags=[], reasoning="", matched_caregivers=[])

        t = time.perf_counter()
        llm = llm_triage.llm_decision(state.model_text, lang, _history_text(req)) if use_llm else None
        timings["llm"] = time.perf_counter() - t
        tr["llm"] = {"available": llm_available(), "used": llm is not None}
        dec = combine(local, llm)
        if dec is None and prim is None:  # no model at all: conservative default
            dec = Decision("gp_teleconsult", "same_day", "default")
        dec = proute.merge(dec, pout)  # most urgent of (pathway, ML); pathway care type when rules decided
        tr["model_used"] = dec.source

        # safety re-check: rules over everything, union with any LLM red flags
        flags = sorted(set(sres.red_flags) | set(dec.red_flags))
        tr["safety_checks"]["recheck_flags"] = flags
        if flags:
            return emergency_response(flags, lang)
        if dec.care_type == EMERGENCY_CARE_TYPE or dec.urgency == MOST_URGENT:
            tr["safety_checks"]["model_emergency"] = True
            return emergency_response([], lang, prefix=MODEL_EMERGENCY.get(lang, MODEL_EMERGENCY["en"]))

        pathway_decided = prim is not None and prim.explicit
        if not pathway_decided:
            apply_persistence_rule(dec, state.slots, " ".join(turns))
        tr["model_used"] = dec.source

        # elderly / infant who cannot drink: never leave as routine
        if state.slots.answers.get("drinking") == "no" and URGENCY_RANK[dec.urgency] < URGENCY_RANK["same_day"]:
            dec.urgency = "same_day"

        if pathway_decided:  # plain-language danger signs from the pathway; never a disease name
            reasoning = proute.reasoning(pout, dec.care_type, dec.urgency, lang)
        else:
            reasoning = dec.llm_reasoning or explain.reasoning(state.slots, dec.care_type, dec.urgency, lang)

        t = time.perf_counter()
        loc = req.location.model_dump() if req.location else None
        ranked, minfo = matching.rank_with_info(dec.care_type, dec.urgency, lang, loc, state.slots.symptoms,
                                                state.slots.age_group, text=" ".join(turns))
        matched = [MatchedCaregiver(caregiver_id=s.cg["caregiver_id"], score=s.score,
                                    reason=matching.reason(s, dec.care_type, lang)) for s in ranked]
        timings["matching"] = time.perf_counter() - t
        tr["location_received"] = loc
        tr["matching_filters"] = asdict(minfo)
        tr["matching"] = [{"caregiver_id": s.cg["caregiver_id"], "name": s.cg.get("name"), "role": s.cg.get("role"),
                           "specialty": s.cg.get("specialty"), "locality": s.cg.get("locality"),
                           "distance_km": None if s.dist_km is None else round(s.dist_km, 2),
                           "next_slot": s.slot.isoformat() if s.slot else None, "free_in_window": s.in_window,
                           "skills_hit": s.skills_hit, "language_match": s.lang_ok, "score": s.score} for s in ranked]
        return TriageResponse(follow_up_question=None, care_type=dec.care_type, urgency=dec.urgency, red_flags=[],
                              reasoning=reasoning, matched_caregivers=matched)
    except Exception:
        log.exception("pipeline error; returning safe response")
        tr["error"] = True
        try:
            doubt = safety.check(turns)
            if doubt.is_emergency:
                return emergency_response(doubt.red_flags, lang)
        except Exception:
            return emergency_response([], lang)
        return TriageResponse(follow_up_question=None, care_type="gp_teleconsult", urgency="same_day", red_flags=[],
                              reasoning=FALLBACK_REASON.get(lang, FALLBACK_REASON["en"]), matched_caregivers=[])
    finally:
        timings["total"] = time.perf_counter() - t0
        tr["per_stage_latency_ms"] = {k: round(v * 1000, 2) for k, v in timings.items()}
        log.info("triage latency_ms %s", " ".join(f"{k}={v * 1000:.1f}" for k, v in timings.items()))


def final_decision(text: str, model=None, cfg: Optional[dict] = None, use_llm: bool = False,
                   lang: Optional[str] = None) -> dict:
    """Single-shot decision with no follow-ups (offline evaluation / predictions CSV)."""
    lang = resolve_language(lang or "auto", text)
    state = intake.build_state(text, [])
    sres = safety.check([text, state.model_text])
    if sres.is_emergency:
        return {"care_type": EMERGENCY_CARE_TYPE, "urgency": MOST_URGENT, "red_flags": sres.red_flags,
                "reasoning": safety.emergency_reasoning(sres.red_flags, lang), "source": "rules"}
    pout = pathways.run([text])
    prim = pout.primary
    if prim is not None and prim.stage == "S3":
        r = pathway_emergency(pout, lang, [])
        return {"care_type": r.care_type, "urgency": r.urgency, "red_flags": r.red_flags, "reasoning": r.reasoning,
                "source": f"pathway:{prim.pathway}", "stage": prim.stage, "pathway": prim.pathway}
    m = model or best_local_model()
    local = None
    if m is not None:
        probs = m.predict_proba(state.model_text)
        care, urg, conf = decide_from_probs(probs, cfg)
        local = Decision(care, urg, getattr(m, "name", "local"), conf, probs)
    llm = llm_triage.llm_decision(state.model_text, lang) if use_llm else None
    dec = combine(local, llm)
    if dec is None and prim is None:
        dec = Decision("gp_teleconsult", "same_day", "default")
    dec = proute.merge(dec, pout)
    extra = {"stage": prim.stage, "pathway": prim.pathway} if prim else {}
    if dec.red_flags:
        return {"care_type": EMERGENCY_CARE_TYPE, "urgency": MOST_URGENT, "red_flags": dec.red_flags,
                "reasoning": safety.emergency_reasoning(dec.red_flags, lang), "source": dec.source, **extra}
    pathway_decided = prim is not None and prim.explicit
    if dec.care_type == EMERGENCY_CARE_TYPE or dec.urgency == MOST_URGENT:
        dec.care_type, dec.urgency = EMERGENCY_CARE_TYPE, MOST_URGENT
    elif not pathway_decided:
        apply_persistence_rule(dec, state.slots, text)
    if dec.care_type == EMERGENCY_CARE_TYPE:
        reasoning = safety.STEPS.get(lang, safety.STEPS["en"])
    elif pathway_decided:
        reasoning = proute.reasoning(pout, dec.care_type, dec.urgency, lang)
    else:
        reasoning = dec.llm_reasoning or explain.reasoning(state.slots, dec.care_type, dec.urgency, lang)
    return {"care_type": dec.care_type, "urgency": dec.urgency, "red_flags": [], "reasoning": reasoning,
            "source": dec.source, **extra}

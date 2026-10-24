"""PII redaction before any LLM call or log line: names, phone numbers, emails, addresses and Aadhaar-like numbers
become [NAME], [PHONE], [EMAIL], [ADDRESS], [ID]. Symptoms, durations and readings (temperature, BP, platelets)
are kept, so the text still routes the same way.
"""
from __future__ import annotations

import re

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b")
AADHAAR = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
PHONE = re.compile(r"(?<![\d/.])(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?![\d/.])")
PIN = re.compile(r"\b(?:pin(?:\s*code)?|pincode)\s*[:\-]?\s*\d{6}\b", re.I)  # a bare 6-digit number may be a reading
# "mera naam Rahul hai", "my name is Priya Sharma", "I am Ankit", "naam: Sunita"
NAME = re.compile(
    r"\b((?i:my\s+name\s+is|this\s+is|i\s+am|i'm|mera\s+naam|meri\s+naam|naam|name)|मेरा\s+नाम|नाम)\s*[:\-]?\s+"
    r"((?:[A-Z][a-z]+|[ऀ-ॿ]+)(?:\s+(?:[A-Z][a-z]+|[ऀ-ॿ]+))?)", re.UNICODE)
NAME_NOT = {"not", "having", "feeling", "very", "in", "a", "an", "the", "sick", "unwell", "fine", "ok", "okay", "worried",
            "बहुत", "है", "hai", "hoon", "hun"}
ADDRESS = re.compile(
    r"\b(?:h\.?\s*no\.?|house\s+no\.?|flat\s+(?:no\.?\s*)?|plot\s+(?:no\.?\s*)?|ghar\s+no\.?|makan\s+no\.?)\s*[\w/-]+"
    r"(?:[,\s]+(?:sector|block|gali|lane|street|road|marg|nagar|colony|vihar|enclave|phase)\s*[\w-]*)*"
    r"|\b(?:sector|block|gali|lane)\s+\d+[a-z]?\b(?:[,\s]+[A-Z][a-z]+(?:\s+(?:nagar|colony|vihar|enclave))?)?",
    re.I)


def redact(text: str) -> str:
    if not text:
        return text
    t = EMAIL.sub("[EMAIL]", text)
    t = AADHAAR.sub("[ID]", t)
    t = PHONE.sub("[PHONE]", t)
    t = ADDRESS.sub("[ADDRESS]", t)
    t = PIN.sub("[ADDRESS]", t)

    def _name(m: re.Match) -> str:
        words = m.group(2).split()
        n = next((i for i, w in enumerate(words) if w.lower() in NAME_NOT), len(words))
        if n == 0:
            return m.group(0)
        rest = " ".join(words[n:])
        return f"{m.group(1)} [NAME]" + (f" {rest}" if rest else "")
    return NAME.sub(_name, t)

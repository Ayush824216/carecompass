"""Optional SOS SMS sending. Off by default: without SMS_PROVIDER the client opens the user's own SMS app.

SMS_PROVIDER=twilio with TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM sends one SMS per contact (max 5)
through the Twilio Messages API. The response says "sent" only for numbers the provider accepted; the client
shows "Sent" only then. Numbers and the message are never logged or stored.
"""
from __future__ import annotations

import logging
import os
import re

import httpx

log = logging.getLogger("carecompass.sms")
MAX_TO = 5
MAX_LEN = 600
IN_MOBILE = re.compile(r"^(?:\+?91)?([6-9]\d{9})$")


def provider() -> str:
    return os.getenv("SMS_PROVIDER", "").strip().lower()


def enabled() -> bool:
    return provider() == "twilio" and all(os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"))


def normalise(phone: str):
    m = IN_MOBILE.match(re.sub(r"[^\d+]", "", phone or ""))
    return f"+91{m.group(1)}" if m else None


def send(to: list[str], message: str) -> dict:
    """{"enabled", "sent": all accepted, "results": [{"to": masked, "ok"}]}. Never raises."""
    if not enabled():
        return {"enabled": False, "sent": False, "results": []}
    nums = [n for n in (normalise(x) for x in to[:MAX_TO]) if n]
    body = (message or "")[:MAX_LEN]
    sid, token, frm = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"), os.getenv("TWILIO_FROM")
    results = []
    for n in nums:
        ok = False
        try:
            r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, token),
                           data={"To": n, "From": frm, "Body": body}, timeout=8.0)
            ok = r.status_code in (200, 201) and r.json().get("status") in ("queued", "accepted", "sending", "sent")
        except Exception as e:  # network / provider error: reported as not sent
            log.warning("sms provider error %s", e.__class__.__name__)
        results.append({"to": f"******{n[-4:]}", "ok": ok})
    return {"enabled": True, "sent": bool(results) and all(r["ok"] for r in results), "results": results}

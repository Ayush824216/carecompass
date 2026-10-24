"""SOS SMS: off by default; 'sent' only when the provider accepts every message; numbers never echoed in full."""
from fastapi.testclient import TestClient

from app import sms
from app.main import app

client = TestClient(app)


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("SMS_PROVIDER", raising=False)
    assert client.get("/api/v1/sos/status").json() == {"enabled": False}
    r = client.post("/api/v1/sos/send", json={"to": ["9876543210"], "message": "SOS"}).json()
    assert r == {"enabled": False, "sent": False, "results": []}


def _twilio(monkeypatch, status_code, status):
    for k, v in {"SMS_PROVIDER": "twilio", "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "t", "TWILIO_FROM": "+100"}.items():
        monkeypatch.setenv(k, v)
    sent = []

    class R:
        def __init__(self): self.status_code = status_code
        def json(self): return {"status": status}

    def post(url, **kw):
        sent.append(kw["data"]["To"])
        return R()
    monkeypatch.setattr(sms.httpx, "post", post)
    return sent


def test_sent_only_when_provider_accepts(monkeypatch):
    sent = _twilio(monkeypatch, 201, "queued")
    r = client.post("/api/v1/sos/send", json={"to": ["9876543210", "+91 91234 56789", "12345"], "message": "SOS"}).json()
    assert r["sent"] is True and sent == ["+919876543210", "+919123456789"]
    assert all(x["to"].startswith("******") and "9876543210" not in x["to"] for x in r["results"])


def test_provider_failure_is_not_sent(monkeypatch):
    _twilio(monkeypatch, 400, "failed")
    r = client.post("/api/v1/sos/send", json={"to": ["9876543210"], "message": "SOS"}).json()
    assert r["enabled"] is True and r["sent"] is False


def test_at_most_five_contacts():
    assert client.post("/api/v1/sos/send", json={"to": ["9876543210"] * 6, "message": "x"}).status_code == 422

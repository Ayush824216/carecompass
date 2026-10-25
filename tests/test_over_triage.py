"""Over-triage fixes from the challenge sets: the model alone cannot make an emergency below high confidence, a
pathway that decided below S3 cannot be escalated by the model, and age alone never lifts a pathway to S3.
Real danger signs stay emergencies."""
import pytest

from app.pipeline import final_decision

FORMER_FALSE_EMERGENCIES = [
    "Can a doctor tell me if my child's vaccination schedule is right?",
    "Nani ko kal se bahut ulti ho rahi hai, kuch bhi pet mein nahi tik raha, 80 saal ki hain",
    "Bachche ka sar garam hai aur naak beh rahi hai, 5 saal ka hai, khel raha hai",
    "Didi ko pregnancy ka 3rd mahina hai, ulti bahut ho rahi hai, kuch khaya nahi ja raha",
    "My 70 year old aunt has had loose motions 6 times today and feels faint",
    "Baby 6 mahine ka hai, potty mein thoda khoon dikha, baaki theek hai",
]


@pytest.mark.parametrize("text", FORMER_FALSE_EMERGENCIES)
def test_former_false_emergencies_are_same_day_not_emergency(text):
    d = final_decision(text)
    assert d["care_type"] != "emergency_referral" and d["urgency"] != "routine"


@pytest.mark.parametrize("text", [
    "Dadaji ke seene mein tez dard ho raha hai aur paseena aa raha hai",
    "Nani 80 saal ki hain, ulti ho rahi hai aur ab behosh ho gayi",
    "baby 2 mahine ka hai, tez bukhar hai aur doodh nahi pi raha",
    "pregnant hoon, khoon aa raha hai",
    "My 70 year old aunt has loose motions and is now confused and not responding",
])
def test_real_danger_signs_stay_emergencies(text):
    assert final_decision(text)["care_type"] == "emergency_referral"

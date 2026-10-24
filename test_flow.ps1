# End-to-end API smoke test against a running backend.
#   powershell -ExecutionPolicy Bypass -File test_flow.ps1 [-Base http://localhost:8000]
param([string]$Base = "http://localhost:8000")
$ErrorActionPreference = "Stop"
$official = @("follow_up_question", "care_type", "urgency", "red_flags", "reasoning", "matched_caregivers") | Sort-Object
$fail = 0

function Check($name, $cond) {
  if ($cond) { Write-Host "PASS  $name" -ForegroundColor Green } else { Write-Host "FAIL  $name" -ForegroundColor Red; $script:fail++ }
}
function Post($path, $body) {
  Invoke-RestMethod -Method Post -Uri "$Base$path" -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 10)))
}
function Keys($obj) { ($obj.PSObject.Properties.Name | Sort-Object) }

$h = Invoke-RestMethod "$Base/health"
Check "health ok" ($h.status -eq "ok")

$req = @{ user_input = "papa ko do din se bukhar hai aur khansi bhi"; language = "auto"; location = @{ lat = 28.54; lng = 77.27 }; conversation_history = @() }
$r = Post "/api/v1/triage" $req
Check "default response has exactly the official keys" ((Compare-Object (Keys $r) $official) -eq $null)
Check "example routes to a decision" ($r.care_type -ne $null -and $r.urgency -ne $null)
Check "caregivers matched" ($r.matched_caregivers.Count -ge 1)

$e = Post "/api/v1/triage" @{ user_input = "dadaji ke seene mein tez dard ho raha hai"; language = "auto"; conversation_history = @() }
Check "emergency -> emergency_referral/immediate" ($e.care_type -eq "emergency_referral" -and $e.urgency -eq "immediate")
Check "emergency has no caregivers" ($e.matched_caregivers.Count -eq 0)
Check "emergency reasoning has 112" ($e.reasoning -like "*112*")

$n = Post "/api/v1/triage" @{ user_input = "seene mein dard nahi hai, bas gas hai"; language = "auto"; conversation_history = @() }
Check "negation is not an emergency" ($n.care_type -ne "emergency_referral")

$d = Post "/api/v1/triage?debug=true" $req
Check "debug adds exactly one key" ((Compare-Object (Keys $d) ($official + "debug" | Sort-Object)) -eq $null)
Check "debug has detected_language" ($d.debug.detected_language -eq "hinglish")

$f = Post "/api/v1/triage" @{ user_input = "tabiyat kharab hai"; language = "auto"; conversation_history = @() }
Check "vague input asks a follow-up" ($f.follow_up_question -ne $null -and $f.care_type -eq $null)

if ($r.matched_caregivers.Count -ge 1) {
  $b = Post "/api/v1/book" @{ caregiver_id = $r.matched_caregivers[0].caregiver_id; care_type = $r.care_type; urgency = $r.urgency }
  Check "booking confirmed" ($b.status -eq "confirmed")
}

$saket = Post "/api/v1/triage" @{ user_input = "papa ko do din se bukhar hai aur khansi bhi"; location = @{ lat = 28.5245; lng = 77.2066 }; conversation_history = @() }
$noida = Post "/api/v1/triage" @{ user_input = "papa ko do din se bukhar hai aur khansi bhi"; location = @{ lat = 28.6270; lng = 77.3649 }; conversation_history = @() }
Check "at least 3 caregivers at each location" ($saket.matched_caregivers.Count -ge 3 -and $noida.matched_caregivers.Count -ge 3)
Check "ranking changes with location" ($saket.matched_caregivers[0].caregiver_id -ne $noida.matched_caregivers[0].caregiver_id)

$derm = Post "/api/v1/triage?debug=true" @{ user_input = "skin pe rash hai 2 hafte se"; location = @{ lat = 28.5245; lng = 77.2066 }; conversation_history = @() }
# answer follow-up questions like a user would, until the API decides
$dh = @(@{ role = "user"; content = "skin pe rash hai 2 hafte se" })
for ($i = 0; $i -lt 4 -and $derm.follow_up_question; $i++) {
  $dh += @{ role = "assistant"; content = $derm.follow_up_question }
  $derm = Post "/api/v1/triage?debug=true" @{ user_input = "bas yahi, adult hai, halka hai"; location = @{ lat = 28.5245; lng = 77.2066 }; conversation_history = $dh }
  $dh += @{ role = "user"; content = "bas yahi, adult hai, halka hai" }
}
Check "persistent rash -> specialist" ($derm.care_type -eq "specialist_referral")
Check "dermatologists matched" (($derm.debug.matching | Where-Object { $_.specialty -eq "dermatology" }).Count -ge 3)

# domain guard: non-health turns get a redirect in follow_up_question and no decision; safety still wins
$g = Post "/api/v1/triage?debug=true" @{ user_input = "hello Babu tum kaise ho aajkal etc question kya hai"; conversation_history = @() }
Check "greeting -> redirect, no decision" ($g.care_type -eq $null -and $g.follow_up_question -ne $null -and $g.matched_caregivers.Count -eq 0 -and $g.debug.domain_class -eq "greeting_smalltalk")
$o = Post "/api/v1/triage" @{ user_input = "who won the cricket match yesterday"; conversation_history = @() }
Check "off-topic -> redirect with official keys" ($o.care_type -eq $null -and $o.follow_up_question -ne $null -and (Compare-Object (Keys $o) $official) -eq $null)
$mx = Post "/api/v1/triage" @{ user_input = "hi, mummy ko chakkar aa rahe hain"; conversation_history = @() }
Check "greeting + symptom -> health" ($mx.care_type -ne $null -or ($mx.follow_up_question -ne $null))
$ge = Post "/api/v1/triage" @{ user_input = "hello, papa behosh ho gaye"; conversation_history = @() }
Check "greeting + red flag -> emergency" ($ge.care_type -eq "emergency_referral")

if ($fail -gt 0) { Write-Host "$fail check(s) failed" -ForegroundColor Red; exit 1 } else { Write-Host "All checks passed" -ForegroundColor Green }

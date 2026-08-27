"""Module 2 — document validation (Phase 3).

Rule-based checks on the OCR extraction: MRZ check digits (ICAO 9303 TD3),
expiry/DOB date logic, field formats -> list of {label, status, detail}.
Also validates Indian documents: Aadhaar (Verhoeff checksum) and PAN
(structure, holder type, surname-initial rule).
Statuses: pass | review | fail.
"""
import re
from datetime import date, timedelta

from services import indian_docs
from services.ocr import NATIONALITIES

# fails on these rules are hard fraud signals (risk.py weights them heavily)
CRITICAL_LABELS = {
    "MRZ check digits", "Document expiry", "Date of birth", "Date consistency",
    "Aadhaar checksum", "PAN structure",
}


def _char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - 55
    return 0  # '<' filler


def _check_digit(text: str) -> str:
    weights = (7, 3, 1)
    return str(sum(_char_value(c) * weights[i % 3] for i, c in enumerate(text)) % 10)


def _parse_yymmdd(s: str, assume_2000s: bool) -> date | None:
    if not re.fullmatch(r"\d{6}", s):
        return None
    yy, mm, dd = int(s[:2]), int(s[2:4]), int(s[4:6])
    year = 2000 + yy if (yy < 27 or assume_2000s) else 1900 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


def check(extraction: dict) -> list[dict]:
    """Validate an OCR extraction. Single entry point; returns flag list."""
    doc_type = extraction.get("docType")
    if doc_type == "aadhaar":
        return _check_aadhaar(extraction)
    if doc_type == "pan":
        return _check_pan(extraction)

    mrz = extraction.get("mrz")
    fields = extraction.get("fields") or {}
    if not mrz:
        return [{
            "label": "Document structure", "status": "review",
            "detail": "No recognizable document structure — automated validation unavailable.",
        }]

    l2 = mrz["line2"]
    today = date.today()
    flags: list[dict] = []

    # --- MRZ check digits (TD3: number, dob, expiry, optional, composite)
    digit_checks = (
        ("passport number", l2[0:9], l2[9]),
        ("date of birth", l2[13:19], l2[19]),
        ("expiry date", l2[21:27], l2[27]),
        ("optional data", l2[28:42], l2[42]),
        ("composite", l2[0:10] + l2[13:20] + l2[21:43], l2[43]),
    )
    bad = [name for name, data, cd in digit_checks if _check_digit(data) != cd]
    if bad:
        flags.append({
            "label": "MRZ check digits", "status": "fail",
            "detail": f"Check digit mismatch: {', '.join(bad)}.",
        })
    else:
        flags.append({
            "label": "MRZ check digits", "status": "pass",
            "detail": "All 5 check digits valid.",
        })

    # --- expiry date logic
    expiry = _parse_yymmdd(l2[21:27], assume_2000s=True)
    if expiry is None:
        flags.append({"label": "Document expiry", "status": "review",
                      "detail": "Expiry date could not be parsed from MRZ."})
    elif expiry < today:
        days = (today - expiry).days
        flags.append({
            "label": "Document expiry", "status": "fail",
            "detail": f"Document EXPIRED on {expiry:%d %b %Y} ({days} days ago).",
        })
    elif expiry < today + timedelta(days=180):
        flags.append({
            "label": "Document expiry", "status": "review",
            "detail": f"Document expires soon ({(expiry - today).days} days).",
        })
    else:
        flags.append({
            "label": "Document expiry", "status": "pass",
            "detail": f"Valid until {expiry:%d %b %Y}.",
        })

    # --- date of birth logic
    dob = _parse_yymmdd(l2[13:19], assume_2000s=False)
    if dob is None:
        flags.append({"label": "Date of birth", "status": "review",
                      "detail": "Date of birth could not be parsed from MRZ."})
    elif dob > today:
        flags.append({"label": "Date of birth", "status": "fail",
                      "detail": "Date of birth is in the future."})
    else:
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age > 100:
            flags.append({"label": "Date of birth", "status": "review",
                          "detail": f"Age {age} — implausible."})
        else:
            flags.append({"label": "Date of birth", "status": "pass",
                          "detail": f"Age {age} — plausible."})

    # --- internal date consistency
    if dob and expiry and expiry < dob:
        flags.append({"label": "Date consistency", "status": "fail",
                      "detail": "Expiry date precedes date of birth."})

    # --- field formats
    number = (fields.get("documentNo") or "").strip()
    if re.fullmatch(r"[A-Z0-9]{6,9}", number):
        flags.append({"label": "Document number format", "status": "pass",
                      "detail": f"'{number}' matches expected pattern."})
    else:
        flags.append({"label": "Document number format", "status": "review",
                      "detail": f"'{number}' does not match expected 6-9 char alphanumeric pattern."})

    nationality = l2[10:13]
    if not re.fullmatch(r"[A-Z]{3}", nationality):
        flags.append({"label": "Nationality code", "status": "review",
                      "detail": f"'{nationality}' is not a 3-letter code."})
    elif nationality not in NATIONALITIES:
        flags.append({"label": "Nationality code", "status": "review",
                      "detail": f"'{nationality}' not in reference set — verify manually."})
    else:
        flags.append({"label": "Nationality code", "status": "pass",
                      "detail": f"'{nationality}' recognized."})

    sex = l2[20]
    if sex in ("M", "F"):
        flags.append({"label": "Gender code", "status": "pass",
                      "detail": f"'{sex}' valid."})
    else:
        flags.append({"label": "Gender code", "status": "review",
                      "detail": f"'{sex}' unspecified/other — verify manually."})

    confidence = extraction.get("ocrConfidence")
    if confidence is not None and confidence < 0.35:
        flags.append({"label": "OCR confidence", "status": "review",
                      "detail": f"Low OCR confidence ({confidence:.0%}) — extracted fields may be unreliable."})

    return flags


# ------------------------------------------------------- Indian documents
def _check_aadhaar(extraction: dict) -> list[dict]:
    """Validate an Aadhaar extraction: Verhoeff checksum + structure."""
    fields = extraction.get("fields") or {}
    number = (fields.get("documentNo") or "").replace(" ", "")
    flags: list[dict] = []

    if not re.fullmatch(r"\d{12}", number):
        flags.append({"label": "Aadhaar structure", "status": "review",
                      "detail": f"'{number or '—'}' is not a 12-digit Aadhaar number."})
        return flags

    if number[0] in "01":
        flags.append({"label": "Aadhaar structure", "status": "fail",
                      "detail": "Aadhaar numbers never start with 0 or 1."})
        return flags

    if indian_docs.aadhaar_valid(number):
        flags.append({"label": "Aadhaar checksum", "status": "pass",
                      "detail": "Verhoeff checksum valid (UIDAI standard)."})
    else:
        flags.append({"label": "Aadhaar checksum", "status": "fail",
                      "detail": "Verhoeff checksum FAILED — this number was not issued by UIDAI."})

    flags += _common_field_checks(fields)
    return flags


def _check_pan(extraction: dict) -> list[dict]:
    """Validate a PAN extraction: structure, holder type, surname initial."""
    fields = extraction.get("fields") or {}
    pan = (fields.get("documentNo") or "").strip().upper()
    flags: list[dict] = []

    if not indian_docs.pan_structure_ok(pan):
        flags.append({"label": "PAN structure", "status": "fail",
                      "detail": f"'{pan or '—'}' does not match the PAN format (AAAPL1234K)."})
        return flags

    flags.append({"label": "PAN structure", "status": "pass",
                  "detail": "Structure valid (5 letters + 4 digits + check letter)."})

    holder = indian_docs.pan_holder_type(pan)
    flags.append({"label": "PAN holder type", "status": "pass" if pan[3] == "P" else "review",
                  "detail": (f"4th character '{pan[3]}' = {holder}."
                             if holder else f"4th character '{pan[3]}' — unknown type.")})

    expected_initial = indian_docs.pan_surname_initial(pan)
    surname = (fields.get("name") or "").split()[-1] if fields.get("name") else ""
    if not surname:
        flags.append({"label": "PAN name match", "status": "review",
                      "detail": "Holder name unreadable — cannot verify the PAN's "
                                "5th character against the surname."})
    elif surname[0].upper() != expected_initial:
        flags.append({"label": "PAN name mismatch", "status": "review",
                      "detail": f"5th character '{expected_initial}' should match surname initial "
                                f"'{surname[0].upper()}' ({fields.get('name')})."})
    else:
        flags.append({"label": "PAN name match", "status": "pass",
                      "detail": "Surname initial matches the PAN's 5th character."})

    flags += _common_field_checks(fields)
    return flags


def _common_field_checks(fields: dict) -> list[dict]:
    """Field checks shared by Aadhaar/PAN (DOB logic mainly)."""
    flags: list[dict] = []
    today = date.today()
    dob_text = fields.get("dob") or ""
    dob = None
    if dob_text:
        # parse "DD Mon YYYY"
        for i, month in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")):
            if month.lower() in dob_text.lower():
                parts = dob_text.replace(",", " ").split()
                try:
                    dob = date(int(parts[2]), i + 1, int(parts[0]))
                except (ValueError, IndexError):
                    dob = None
                break
    if dob_text and dob is None:
        flags.append({"label": "Date of birth", "status": "review",
                      "detail": f"DOB '{dob_text}' could not be parsed."})
    elif dob:
        if dob > today:
            flags.append({"label": "Date of birth", "status": "fail",
                          "detail": "Date of birth is in the future."})
        else:
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            flags.append({"label": "Date of birth", "status": "pass",
                          "detail": f"Age {age} — plausible."})
    return flags

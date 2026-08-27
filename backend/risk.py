"""Risk engine (Phase 6): module outputs -> weighted 0-100 score + tier + reasons.

Weights (points added, capped at 100):
  critical validation fail (MRZ/Aadhaar/PAN checksums, dates)               72
  other validation fail                                                     30
  validation review                                                          8
  tampering fail                                             40 x signal (min 20)
  tampering review / module failure                                         10-12
  face verified False (identity mismatch)                                   50
  liveness review                                                           12
  unrecognized document                                                     35
  watchlist match                                                           80

Tiers (architecture.md §7): LOW < 40 · MED 40-69 · HIGH >= 70.
Every non-zero contribution appears in reasons[] — the score is explainable.
"""
from services.validation import CRITICAL_LABELS

_TIER_BANDS = ((70, "HIGH"), (40, "MED"), (0, "LOW"))


def score(extraction: dict, validation_flags: list[dict],
          tamper_flags: list[dict], face_result: dict,
          watchlist_match: dict | None = None) -> dict:
    """Combine all module outputs into {score, tier, reasons}."""
    points = 0
    reasons: list[str] = []

    def add(pts: int, reason: str) -> None:
        nonlocal points
        points += pts
        reasons.append(reason)

    for flag in validation_flags:
        if flag["status"] == "fail":
            if flag["label"] in CRITICAL_LABELS:
                add(72, f"{flag['label']}: {flag['detail']}")
            else:
                add(30, f"{flag['label']}: {flag['detail']}")
        elif flag["status"] == "review":
            add(8, f"{flag['label']}: {flag['detail']}")

    for flag in tamper_flags:
        if flag["status"] == "fail":
            signal = max(flag.get("signal") or 0.6, 0.5)
            add(round(40 * signal), f"{flag['label']}: {flag['detail']}")
        elif flag["status"] == "review":
            add(12, f"{flag['label']}: {flag['detail']}")

    if face_result.get("verified") is False:
        match = face_result.get("match") or 0
        add(50, f"Face match {match:.0%} below threshold — possible identity mismatch")
    elif face_result.get("liveness") == "review":
        add(12, face_result.get("detail") or "Liveness check requires review")

    if extraction.get("mrz") is None and extraction.get("docType") == "unknown":
        add(35, "No recognizable document structure — fields unverified")

    if watchlist_match:
        add(80, f"WATCHLIST MATCH: {watchlist_match.get('doc_number') or watchlist_match.get('person_name')} "
                f"— {watchlist_match.get('reason') or 'flagged document/person'}")

    total = min(100, points)
    tier = next(t for floor, t in _TIER_BANDS if total >= floor)
    if not reasons:
        reasons.append("All validation, tampering and face checks passed")
    return {"score": total, "tier": tier, "reasons": reasons}

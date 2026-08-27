"""Module 1 — OCR extraction (Phase 2).

EasyOCR readtext() on the document image, then map lines to contract fields.
Passport MRZ (bottom two lines) is the reliable source for
name/number/nationality/DOB/expiry/gender. Printed text lines are also
returned so later modules (validation / tampering) can cross-check them.
"""
import re
import threading
from pathlib import Path

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

NATIONALITIES = {
    "IND": "India", "USA": "United States", "GBR": "United Kingdom",
    "CAN": "Canada", "AUS": "Australia", "DEU": "Germany", "FRA": "France",
    "JPN": "Japan", "CHN": "China", "SGP": "Singapore", "ARE": "UAE",
    "RUS": "Russia", "BRA": "Brazil", "ZAF": "South Africa",
}

_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    global _reader
    with _reader_lock:
        if _reader is None:
            import easyocr
            _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return _reader


def prewarm() -> None:
    """Initialize the reader off the request path (downloads model weights
    on the first ever run). Called from a daemon thread at app startup."""
    try:
        _get_reader()
        print("[ocr] reader ready")
    except Exception as exc:
        print(f"[ocr] prewarm failed: {exc}")


def _read(source) -> list:
    if isinstance(source, Path):
        source = str(source)  # easyocr accepts str paths, not Path
    return _get_reader().readtext(source, detail=1, paragraph=False)


def _lines_from_readtext(raw: list) -> list[dict]:
    """Cluster EasyOCR boxes into text lines (by y proximity), joining
    left-to-right within a line. Returns [{'text','conf','y'}] sorted by y."""
    entries = []
    for bbox, text, conf in raw:
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        entries.append({
            "x": sum(xs) / len(xs),
            "y": sum(ys) / len(ys),
            "h": max(ys) - min(ys),
            "text": text,
            "conf": conf,
        })
    entries.sort(key=lambda e: e["y"])
    lines: list[dict] = []
    for entry in entries:
        placed = False
        for line in lines:
            if abs(line["y"] - entry["y"]) < max(line["h"], entry["h"]) * 0.6:
                count = len(line["parts"])
                line["y"] = (line["y"] * count + entry["y"]) / (count + 1)
                line["h"] = max(line["h"], entry["h"])
                line["parts"].append(entry)
                placed = True
                break
        if not placed:
            lines.append({"y": entry["y"], "h": entry["h"], "parts": [entry]})
    out = []
    for line in lines:
        parts = sorted(line["parts"], key=lambda p: p["x"])
        out.append({
            "text": " ".join(p["text"] for p in parts),
            "conf": sum(p["conf"] for p in parts) / len(parts),
            "y": line["y"],
        })
    out.sort(key=lambda l: l["y"])
    return out


def _find_mrz(lines: list[dict]):
    """Locate the TD3 passport MRZ pair: line1 'P<XXXNAME<<', line2 structured.
    Returns (line1, line2) dicts with 'norm' added, or (None, None)."""
    normalized = [{**line, "norm": re.sub(r"\s+", "", line["text"]).upper()}
                  for line in lines]
    for i, line in enumerate(normalized):
        if len(line["norm"]) == 44 and re.match(r"^P<[A-Z]{3}", line["norm"]):
            for candidate in normalized[i + 1:i + 3]:
                if len(candidate["norm"]) == 44 and re.match(r"^[A-Z0-9<]{9}\d", candidate["norm"]):
                    return line, candidate
    return None, None


def _read_bottom_crop(image_path: Path) -> list:
    """Retry pass: OCR only the bottom third of the document, upscaled 2x —
    where the MRZ band lives on a passport data page."""
    import numpy as np
    from PIL import Image

    with Image.open(image_path) as img:
        w, h = img.size
        crop = img.convert("RGB").crop((0, int(h * 0.66), w, h))
        crop = crop.resize((crop.width * 2, crop.height * 2))
        return _read(np.asarray(crop))


def _parse_date(yymmdd: str, assume_2000s: bool) -> str | None:
    if not re.fullmatch(r"\d{6}", yymmdd):
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return None
    if assume_2000s or yy < 27:
        year = 2000 + yy
    else:
        year = 1900 + yy
    return f"{dd:02d} {_MONTHS[mm - 1]} {year}"


def _parse_name(line1_norm: str) -> str:
    body = line1_norm[5:]  # skip P<ISS
    parts = body.split("<<")
    surname = parts[0].replace("<", " ").strip()
    given = " ".join(p.replace("<", " ").strip() for p in parts[1:] if p.strip("<"))
    full = f"{given} {surname}".strip()
    return full.title() if full else full


def extract(image_path: str) -> dict:
    """Single entry point: OCR a document image and extract contract fields.

    Supports passports (TD3 MRZ) plus Indian Aadhaar and PAN cards via
    marker/pattern detection. Returns
    {docType, fields, mrz, textLines, ocrConfidence, warnings}.
    Never raises — failures produce warnings + empty fields (rules.md §5).
    """
    result: dict = {
        "docType": "unknown",
        "fields": {},
        "mrz": None,
        "textLines": [],
        "ocrConfidence": None,
        "warnings": [],
    }
    path = Path(image_path)
    try:
        raw = _read(path)
    except Exception as exc:
        result["warnings"].append(f"OCR engine failed: {exc}")
        return result

    lines = _lines_from_readtext(raw)
    result["textLines"] = [line["text"] for line in lines]

    # --- Indian cards first (no MRZ): Aadhaar / PAN detection
    indian = _detect_indian_card(result["textLines"])
    if indian is not None:
        result["docType"] = indian["docType"]
        result["fields"] = indian["fields"]
        if not indian["fields"]:
            result["warnings"].append(
                f"{indian['docType'].capitalize()} detected but fields could not be read.")
        return result

    # --- passport MRZ path
    line1, line2 = _find_mrz(lines)

    if line1 is None:
        # MRZ often OCRs poorly at full-page scale — retry on the bottom band
        try:
            lines2 = _lines_from_readtext(_read_bottom_crop(path))
            line1, line2 = _find_mrz(lines2)
        except Exception:
            pass

    if line1 is None:
        result["warnings"].append("No recognizable document structure — fields not extracted.")
        return result

    n1, n2 = line1["norm"], line2["norm"]
    dob = _parse_date(n2[13:19], assume_2000s=False)
    expiry = _parse_date(n2[21:27], assume_2000s=True)
    sex = n2[20]
    if sex not in ("M", "F"):
        sex = "X"

    result["docType"] = "passport"
    result["fields"] = {
        "name": _parse_name(n1),
        "documentNo": n2[0:9].rstrip("<"),
        "nationality": NATIONALITIES.get(n2[10:13], n2[10:13]),
        "dob": dob,
        "expiry": expiry,
        "gender": sex,
    }
    result["mrz"] = {"line1": n1, "line2": n2}
    result["ocrConfidence"] = round((line1["conf"] + line2["conf"]) / 2, 3)
    return result


# ------------------------------------------------- Indian card detection
_AADHAAR_MARKERS = ("AADHAAR", "AADHAR", "UNIQUE IDENTIFICATION", "UIDAI")
_PAN_MARKERS = ("PERMANENT ACCOUNT NUMBER", "INCOME TAX DEPARTMENT", "INCOMETAXDEPARTMENT")
_LABEL_MAP = {
    "name": ("NAME", "NAAM"),
    "dob": ("DATE OF BIRTH", "DOB", "JANM"),
    "gender": ("GENDER", "LING"),
    "father": ("FATHER", "PITA"),
    "pan": ("PERMANENT ACCOUNT NUMBER",),
}


def _normalize_for_search(text: str) -> str:
    return re.sub(r"[^A-Z0-9 /]", " ", text.upper())


def _detect_indian_card(text_lines: list[str]) -> dict | None:
    """Detect an Aadhaar or PAN card from OCR text and extract fields.

    Returns {"docType": "aadhaar"|"pan", "fields": {...}} or None.
    """
    if not text_lines:
        return None
    searchable = _normalize_for_search(" ".join(text_lines))

    is_aadhaar = any(marker in searchable for marker in _AADHAAR_MARKERS)
    is_pan = any(marker in searchable for marker in _PAN_MARKERS)
    if not (is_aadhaar or is_pan):
        return None

    fields: dict = {}

    # 12-digit Aadhaar number (possibly printed in XXXX XXXX XXXX groups)
    aadhaar_match = re.search(r"\b(\d{4}\s?\d{4}\s?\d{4})\b", searchable)
    # PAN number: 5 letters + 4 digits + 1 letter
    pan_match = re.search(r"\b([A-Z]{5}\d{4}[A-Z])\b", searchable)

    if is_aadhaar and aadhaar_match:
        fields["documentNo"] = aadhaar_match.group(1).replace(" ", "")
    elif is_pan and pan_match:
        fields["documentNo"] = pan_match.group(1)
    else:
        # markers present but no number found — still classify the doc type
        return {"docType": "aadhaar" if is_aadhaar else "pan", "fields": {}}

    # label→value extraction from OCR lines
    cleaned = [_normalize_for_search(line).strip() for line in text_lines]
    for key, labels in _LABEL_MAP.items():
        if key == "pan":
            continue
        for i, line in enumerate(cleaned):
            if not line:
                continue
            for label in labels:
                # exact-line label ("NAME") or "LABEL: value" — avoids
                # matching NAME inside "FATHER'S NAME" etc.
                if line == label:
                    value = cleaned[i + 1].strip(" :.-") if i + 1 < len(cleaned) else ""
                else:
                    idx = line.find(label + " ") if label + " " in line else -1
                    if idx == -1:
                        continue
                    value = line[idx + len(label):].strip(" :.-")
                if not value and i + 1 < len(cleaned):
                    value = cleaned[i + 1].strip(" :.-")
                value = re.sub(r"\s{2,}", " ", value).strip()
                if not value:
                    continue
                if key in ("name", "father"):
                    if value.replace(" ", "").isalpha() and len(value) > 2:
                        fields[key] = value.title()
                elif key == "dob":
                    dob = _normalize_dob(value)
                    if dob:
                        fields[key] = dob
                elif key == "gender":
                    g = value[:1].upper()
                    if g in ("M", "F"):
                        fields[key] = g
                if key in fields:
                    break
            if key in fields:
                break

    return {"docType": "aadhaar" if is_aadhaar else "pan", "fields": fields}


def _normalize_dob(value: str) -> str | None:
    """Convert DD/MM/YYYY (Indian cards) to the UI's DD Mon YYYY format."""
    match = re.fullmatch(r"(\d{2})\s?[/\-.]\s?(\d{2})\s?[/\-.]\s?(\d{4})", value.strip())
    if not match:
        return None
    dd, mm, yyyy = match.groups()
    try:
        from datetime import date
        d = date(int(yyyy), int(mm), int(dd))
        return d.strftime("%d %b %Y")
    except ValueError:
        return None

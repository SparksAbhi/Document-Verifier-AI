"""Generate synthetic specimen document images for local testing.

Creates three clearly-fake passport specimens (no real PII) in this folder:

  passport_clean.jpg     valid dates, valid MRZ check digits
  passport_expired.jpg   same holder, expiry in the past (validation flag)
  passport_tampered.jpg  clean image with the printed given name edited over
                         ("J0HN" vs MRZ "JOHN") + image-editor EXIF Software
                         tag (tampering signals)

Run:  python backend/samples/generate_samples.py
Regenerate any time — tweak the FIELDS data below for Phase 7 demo variants.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

PAGE_W, PAGE_H = 1100, 780
PAPER = (237, 240, 243)
NAVY = (24, 42, 74)
INK = (30, 34, 40)
MUTED = (110, 118, 128)
MRZ_BAND = (228, 232, 236)
PHOTO_BG = (206, 212, 218)
SILHOUETTE = (158, 166, 175)


def _font(name: str, size: int):
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default(size)


# --------------------------------------------------------------- MRZ helpers
def _char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - 55
    return 0  # '<'


def _check_digit(text: str) -> str:
    weights = (7, 3, 1)
    return str(sum(_char_value(c) * weights[i % 3] for i, c in enumerate(text)) % 10)


def _pad(text: str, width: int) -> str:
    return text.ljust(width, "<")[:width]


def mrz_line1(issuer: str, surname: str, given: str) -> str:
    name = f"{surname}<<{given}".replace(" ", "<").upper()
    return _pad(f"P<{issuer}{name}", 44)


def mrz_line2(number: str, issuer: str, dob: str, sex: str, expiry: str) -> str:
    number = _pad(number.upper(), 9)
    optional = "<" * 14
    upper = number + _check_digit(number)
    dob_block = dob + _check_digit(dob)
    expiry_block = expiry + _check_digit(expiry)
    optional_block = optional + _check_digit(optional)
    line = upper + issuer + dob_block + sex + expiry_block + optional_block
    # composite check digit covers positions 1-10, 14-20, 22-43
    return line + _check_digit(upper + dob_block + expiry_block + optional_block)


# ------------------------------------------------------------------ drawing
FIELDS = (
    ("SURNAME", "DOE"),
    ("GIVEN NAMES", "JOHN"),
    ("NATIONALITY", "INDIAN"),
    ("DATE OF BIRTH", "14 MAR 1989"),
    ("SEX", "M"),
    ("DATE OF EXPIRY", "02 JUN 2031"),
    ("PASSPORT NO", "C40217755"),
)


def draw_passport(expiry_label: str, expiry_mrz: str):
    """Draw one specimen data page; returns (image, {field: value_xy})."""
    img = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, PAGE_W, 96], fill=NAVY)
    d.text((40, 20), "REPUBLIC OF SPECIMEN", font=_font("arialbd.ttf", 30), fill=(240, 243, 246))
    d.text((40, 60), "PASSPORT · SPECIMEN — NOT A REAL DOCUMENT", font=_font("arial.ttf", 15), fill=(168, 178, 192))
    d.text((PAGE_W - 160, 26), "TYPE P", font=_font("arialbd.ttf", 18), fill=(240, 243, 246))
    d.text((PAGE_W - 160, 56), "CODE IND", font=_font("arialbd.ttf", 18), fill=(240, 243, 246))

    # photo placeholder (right side)
    px, py, pw, ph = 760, 150, 260, 320
    d.rectangle([px, py, px + pw, py + ph], fill=PHOTO_BG, outline=MUTED, width=2)
    cx = px + pw // 2
    d.ellipse([cx - 52, py + 58, cx + 52, py + 162], fill=SILHOUETTE)
    d.ellipse([px + 48, py + 178, px + pw - 48, py + 330], fill=SILHOUETTE)

    coords = {}
    for i, (label, value) in enumerate(FIELDS):
        y = 150 + i * 62
        text = expiry_label if label == "DATE OF EXPIRY" else value
        d.text((40, y), label, font=_font("arial.ttf", 13), fill=MUTED)
        d.text((40, y + 18), text, font=_font("arialbd.ttf", 24), fill=INK)
        coords[label] = (40, y + 18)

    # MRZ band
    d.rectangle([0, 600, PAGE_W, PAGE_H], fill=MRZ_BAND)
    d.line([40, 612, PAGE_W - 40, 612], fill=MUTED, width=1)
    mrz_font = _font("consolab.ttf", 26)
    mrz1 = mrz_line1("IND", "DOE", "JOHN")
    mrz2 = mrz_line2("C40217755", "IND", "890314", "M", expiry_mrz)
    x = (PAGE_W - mrz_font.getlength(mrz1)) / 2
    d.text((x, 630), mrz1, font=mrz_font, fill=INK)
    d.text((x, 676), mrz2, font=mrz_font, fill=INK)
    return img, coords


def main() -> None:
    # 1. clean — everything valid
    img, coords = draw_passport("02 JUN 2031", "310602")
    img.save(HERE / "passport_clean.jpg", "JPEG", quality=92)

    # 2. expired — same holder, expiry in the past
    img, _ = draw_passport("02 JUN 2019", "190602")
    img.save(HERE / "passport_expired.jpg", "JPEG", quality=92)

    # 3. tampered — patch the printed given name on the clean image,
    #    then re-save with an editor EXIF tag
    src = Image.open(HERE / "passport_clean.jpg").convert("RGB")
    d = ImageDraw.Draw(src)
    gx, gy = coords["GIVEN NAMES"]
    d.rectangle([gx - 6, gy - 6, gx + 150, gy + 34], fill=PAPER)
    d.text((gx, gy), "J0HN", font=_font("arialbd.ttf", 24), fill=INK)
    exif = Image.Exif()
    exif[305] = "Adobe Photoshop 26.1 (Windows)"  # 305 = EXIF "Software"
    src.save(HERE / "passport_tampered.jpg", "JPEG", quality=90, exif=exif)

    # 4. bad checksum — valid dates, but one passport-number digit altered
    #    without updating its check digit (number + composite both mismatch)
    img, _ = draw_passport("02 JUN 2031", "310602")
    d = ImageDraw.Draw(img)
    l2 = mrz_line2("C40217755", "IND", "890314", "M", "310602")
    corrupted = l2[:8] + ("6" if l2[8] != "6" else "5") + l2[9:]
    mrz_font = _font("consolab.ttf", 26)
    x = (PAGE_W - mrz_font.getlength(l2)) / 2
    d.rectangle([0, 660, PAGE_W, 718], fill=MRZ_BAND)
    d.text((x, 676), corrupted, font=mrz_font, fill=INK)
    img.save(HERE / "passport_badchecksum.jpg", "JPEG", quality=92)

    # 5. visa specimen — no MRZ, so OCR can't parse fields → MED review case
    #    (demonstrates honest degradation instead of fabricated results)
    img = Image.new("RGB", (PAGE_W, 520), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, PAGE_W, 90], fill=(126, 36, 36))
    d.text((40, 16), "REPUBLIC OF SPECIMEN", font=_font("arialbd.ttf", 28), fill=(240, 243, 246))
    d.text((40, 54), "VISA · TYPE L · SPECIMEN — NOT A REAL DOCUMENT", font=_font("arial.ttf", 15), fill=(232, 210, 200))
    visa_fields = (
        ("VISA NO", "V 7735 0091"),
        ("NAME", "JANE ROE"),
        ("NATIONALITY", "INDIAN"),
        ("ENTRY", "SINGLE"),
        ("STAY DURATION", "90 DAYS"),
        ("VALID UNTIL", "12 DEC 2026"),
    )
    for i, (label, value) in enumerate(visa_fields):
        y = 130 + i * 60
        d.text((40, y), label, font=_font("arial.ttf", 13), fill=MUTED)
        d.text((40, y + 18), value, font=_font("arialbd.ttf", 24), fill=INK)
    px, py, pw, ph = 780, 130, 220, 270
    d.rectangle([px, py, px + pw, py + ph], fill=PHOTO_BG, outline=MUTED, width=2)
    cx = px + pw // 2
    d.ellipse([cx - 44, py + 48, cx + 44, py + 138], fill=SILHOUETTE)
    d.ellipse([px + 40, py + 152, px + pw - 40, py + 280], fill=SILHOUETTE)
    img.save(HERE / "visa_specimen.jpg", "JPEG", quality=92)

    # ------- Indian document specimens (all SPECIMEN — no real PII) -------
    _generate_indian_samples()

    print("Generated: passport_clean.jpg, passport_expired.jpg, "
          "passport_tampered.jpg, passport_badchecksum.jpg, visa_specimen.jpg, "
          "aadhaar_clean.jpg, aadhaar_tampered.jpg, pan_clean.jpg, "
          "pan_mismatch.jpg, passport_india.jpg")


def _generate_indian_samples() -> None:
    import sys
    sys.path.insert(0, str(HERE.parent))
    from services import indian_docs

    saffron = (255, 128, 24)
    india_green = (19, 136, 8)
    navy = (16, 34, 74)
    white = (252, 252, 250)

    # ---- Aadhaar card (clean + tampered) ----
    aadhaar_digits = "23456789012"
    aadhaar_no = aadhaar_digits + indian_docs.aadhaar_check_digit(aadhaar_digits)

    def draw_aadhaar(number: str, name: str, dob: str, gender: str):
        img = Image.new("RGB", (900, 580), white)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 900, 26], fill=india_green)
        d.rectangle([0, 554, 900, 580], fill=saffron)
        d.text((30, 4), "GOVERNMENT OF INDICA - SPECIMEN", font=_font("arialbd.ttf", 13), fill=white)
        d.text((30, 42), "UNIQUE IDENTIFICATION AUTHORITY", font=_font("arialbd.ttf", 20), fill=navy)
        d.text((30, 70), "AADHAAR — SPECIMEN CARD, NOT A REAL DOCUMENT", font=_font("arial.ttf", 12), fill=MUTED)
        # photo
        d.rectangle([640, 110, 830, 300], fill=PHOTO_BG, outline=MUTED, width=2)
        d.ellipse([690, 140, 780, 230], fill=SILHOUETTE)
        d.ellipse([670, 240, 800, 330], fill=SILHOUETTE)
        fields = (
            ("NAME", name),
            ("DATE OF BIRTH", dob),
            ("GENDER", gender),
        )
        for i, (label, value) in enumerate(fields):
            y = 120 + i * 58
            d.text((30, y), label, font=_font("arial.ttf", 11), fill=MUTED)
            d.text((30, y + 16), value, font=_font("arialbd.ttf", 20), fill=INK)
        d.text((30, 390), number[:4] + "  " + number[4:8] + "  " + number[8:], font=_font("arialbd.ttf", 30), fill=navy)
        return img

    draw_aadhaar(aadhaar_no, "Arjun Kumar", "12/07/1992", "MALE").save(HERE / "aadhaar_clean.jpg", "JPEG", quality=92)

    # tampered Aadhaar: one checksum digit altered (Verhoeff fails)
    tampered_no = aadhaar_no[:-1] + ("4" if aadhaar_no[-1] != "4" else "7")
    img = draw_aadhaar(tampered_no, "Arjun Kumar", "12/07/1992", "MALE")
    exif = Image.Exif()
    exif[305] = "GIMP 2.10 (Windows)"
    img.save(HERE / "aadhaar_tampered.jpg", "JPEG", quality=90, exif=exif)

    # ---- PAN cards (clean + name mismatch) ----
    # 5th char 'K' matches surname "Kumar"
    pan_no = "AKZPK4821K"

    def draw_pan(number: str, name: str, dob: str):
        img = Image.new("RGB", (860, 540), white)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 860, 70], fill=navy)
        d.text((26, 10), "INCOME TAX DEPARTMENT", font=_font("arialbd.ttf", 20), fill=white)
        d.text((26, 42), "GOVT. OF INDICA — SPECIMEN CARD, NOT A REAL DOCUMENT", font=_font("arial.ttf", 12), fill=(168, 178, 192))
        # photo + signature blocks
        d.rectangle([600, 100, 800, 260], fill=PHOTO_BG, outline=MUTED, width=2)
        d.ellipse([655, 125, 745, 210], fill=SILHOUETTE)
        d.ellipse([640, 215, 760, 290], fill=SILHOUETTE)
        d.rectangle([30, 300, 560, 360], fill=(245, 245, 242), outline=MUTED, width=1)
        d.text((40, 316), "SPECIMEN SIGNATURE", font=_font("arial.ttf", 16), fill=MUTED)
        fields = (
            ("PERMANENT ACCOUNT NUMBER", number),
            ("NAME", name),
            ("FATHER'S NAME", "Specimen Parent Kumar"),
            ("DATE OF BIRTH", dob),
        )
        for i, (label, value) in enumerate(fields):
            y = 100 + i * 52
            d.text((30, y), label, font=_font("arial.ttf", 10), fill=MUTED)
            d.text((30, y + 14), value, font=_font("arialbd.ttf", 19), fill=INK)
        return img

    draw_pan(pan_no, "Arjun Kumar", "12/07/1992").save(HERE / "pan_clean.jpg", "JPEG", quality=92)

    # mismatch PAN: 5th char 'R' but holder surname starts with 'K'
    draw_pan("AKZPR4821R", "Arjun Kumar", "12/07/1992").save(HERE / "pan_mismatch.jpg", "JPEG", quality=92)

    # ---- Indian passport (tricolor header) ----
    img, _ = draw_passport("02 JUN 2031", "310602")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, PAGE_W, 96], fill=navy)
    # tricolor strip
    d.rectangle([0, 96, PAGE_W, 101], fill=saffron)
    d.rectangle([0, 101, PAGE_W, 106], fill=white)
    d.rectangle([0, 106, PAGE_W, 111], fill=india_green)
    d.text((40, 20), "REPUBLIC OF INDICA", font=_font("arialbd.ttf", 30), fill=white)
    d.text((40, 60), "PASSPORT · SPECIMEN — NOT A REAL DOCUMENT", font=_font("arial.ttf", 15), fill=(168, 178, 192))
    img.save(HERE / "passport_india.jpg", "JPEG", quality=92)


if __name__ == "__main__":
    main()

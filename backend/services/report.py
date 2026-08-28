"""PDF report generation for SENTRY screenings (fpdf2).

Generates a professional one-to-two-page report: branding, risk assessment
with score badge, extracted fields, validation/tampering checks with status
colors, face results, officer decision, and the advisory-only disclaimer.
"""

from datetime import datetime

from fpdf import FPDF

NAVY = (16, 34, 74)
CYAN = (0, 128, 122)
GREEN = (19, 136, 8)
AMBER = (200, 145, 0)
RED = (200, 40, 50)
GRAY = (110, 118, 128)
LIGHT = (243, 245, 247)

_STATUS_COLORS = {"pass": GREEN, "review": AMBER, "fail": RED}


def _s(text) -> str:
    """Sanitize text for the built-in latin-1 fonts."""
    replacements = {
        "—": "-", "–": "-", "✓": "OK", "·": "-", "σ": "sigma",
        "≥": ">=", "≤": "<=", "⛔": "[FLAG]", "’": "'", "“": '"', "”": '"',
        "…": "...", "×": "x", "🛂": "",
    }
    text = str(text if text is not None else "")
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class _Report(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        # continuation pages: slim header
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*GRAY)
        self.cell(0, 6, _s(f"SENTRY — Screening Report (continued)"), align="L")
        self.ln(8)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRAY)
        self.cell(0, 5, _s(
            f"SENTRY AI screening report · generated {datetime.now().strftime('%d %b %Y, %H:%M')} · "
            "advisory only — an officer makes the final decision"), align="C")


def generate_report(screening: dict) -> bytes:
    pdf = _Report(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 12, 16)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    risk = screening.get("risk") or {}
    fields = screening.get("fields") or {}
    face = screening.get("face") or {}

    # ---------- header band ----------
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 30, "F")
    pdf.set_xy(16, 7)
    pdf.set_font("Helvetica", "B", 19)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "SENTRY", align="L")
    pdf.set_xy(16, 17)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(160, 210, 220)
    pdf.cell(0, 6, _s("AI Document Screening Report — Border Checkpoint Console"), align="L")
    pdf.set_y(36)

    # ---------- meta row ----------
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    meta = (
        f"Report ID: {_s(screening.get('id'))}    "
        f"Screened: {_s(screening.get('createdAt', ''))}    "
        f"Document type: {_s(screening.get('docType', 'unknown').upper())}"
    )
    pdf.cell(0, 5, meta, align="L")
    pdf.ln(8)

    # ---------- risk badge ----------
    score = risk.get("score", 0)
    tier = risk.get("tier", "—")
    tier_color = {"LOW": GREEN, "MED": AMBER, "HIGH": RED}.get(tier, AMBER)

    pdf.set_fill_color(*LIGHT)
    pdf.rect(16, pdf.get_y(), width, 26, "F")
    pdf.set_xy(22, pdf.get_y() + 4)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*tier_color)
    pdf.cell(26, 12, str(score), align="L")
    pdf.set_xy(22, pdf.get_y() + 16)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GRAY)
    pdf.cell(26, 5, "/ 100", align="L")

    pdf.set_xy(52, pdf.get_y() - 14)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*tier_color)
    pdf.cell(0, 8, f"{_s(tier)} RISK", align="L")
    pdf.set_xy(52, pdf.get_y() + 6)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    tier_desc = {
        "LOW": "All automated checks passed. Cleared for processing.",
        "MED": "Some checks require manual review by the officer.",
        "HIGH": "Strong fraud indicators detected. Immediate attention required.",
    }.get(tier, "")
    pdf.multi_cell(width - 44, 5, _s(tier_desc), align="L")
    pdf.ln(10)

    # ---------- reasons ----------
    reasons = risk.get("reasons") or []
    if reasons:
        _section(pdf, "RISK REASONS (EXPLAINABLE SCORING)")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        for i, reason in enumerate(reasons, 1):
            is_watchlist = "WATCHLIST" in str(reason).upper()
            pdf.set_text_color(*(RED if is_watchlist else (50, 50, 50)))
            pdf.multi_cell(width, 5, _s(f"{i}.  {reason}"), align="L")
            pdf.ln(1.2)
        pdf.ln(3)

    # ---------- extracted fields ----------
    _section(pdf, "EXTRACTED FIELDS (OCR)")
    _field_table(pdf, width, fields)
    pdf.ln(4)

    # ---------- validation checks ----------
    _checks_section(pdf, width, "VALIDATION CHECKS", screening.get("validation") or [])

    # ---------- tampering forensics ----------
    _checks_section(pdf, width, "TAMPERING FORENSICS", screening.get("tampering") or [])

    # ---------- face verification ----------
    _section(pdf, "FACE VERIFICATION & LIVENESS")
    pdf.set_font("Helvetica", "", 9)
    match = face.get("match")
    if match is None:
        face_line = "Not performed (no live face captured)"
    else:
        face_line = f"Match score: {round(match * 100)}%  ·  Verified: {'YES' if face.get('verified') else 'NO'}"
    liveness = face.get("liveness", "na")
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(width, 5, _s(f"{face_line}    Liveness: {_s(liveness)} (simplified check)"), align="L")
    pdf.ln(5)

    # ---------- decision ----------
    _section(pdf, "OFFICER DECISION")
    decision = screening.get("decision")
    pdf.set_font("Helvetica", "B", 11)
    if decision:
        color = {"approve": GREEN, "escalate": AMBER, "deny": RED}.get(decision, AMBER)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, _s(f"{decision.upper()}  —  confirmed by {_s(screening.get('officer') or 'Officer')}"), align="L")
    else:
        pdf.set_text_color(*AMBER)
        pdf.cell(0, 7, "AWAITING OFFICER DECISION", align="L")
    pdf.ln(8)

    # ---------- disclaimer ----------
    pdf.set_fill_color(*LIGHT)
    pdf.rect(16, pdf.get_y(), width, 18, "F")
    pdf.set_xy(20, pdf.get_y() + 3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(width - 8, 4.5, _s(
        "This report is an automated recommendation only — the AI does not decide; a human officer "
        "verified and confirmed the final action. The uploaded document image was securely deleted from "
        "the server after analysis; only this log record persists."), align="L")

    return bytes(pdf.output())


def _section(pdf: _Report, title: str) -> None:
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 7, _s(title), align="L")
    pdf.ln(1)
    pdf.set_draw_color(*CYAN)
    pdf.set_line_width(0.5)
    y = pdf.get_y() + 1
    pdf.line(16, y, 60, y)
    pdf.ln(5)


def _field_table(pdf: _Report, width: float, fields: dict) -> None:
    rows = [
        ("Name", fields.get("name")),
        ("Document No.", fields.get("documentNo")),
        ("Nationality", fields.get("nationality")),
        ("Date of Birth", fields.get("dob")),
        ("Expiry", fields.get("expiry")),
        ("Gender", fields.get("gender")),
    ]
    col = width / 2
    pdf.set_font("Helvetica", "", 9)
    for i in range(0, len(rows), 2):
        for j, (label, value) in enumerate(rows[i:i + 2]):
            x = 16 + j * col
            pdf.set_xy(x, pdf.get_y())
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*GRAY)
            pdf.cell(38, 5.5, _s(label.upper()), align="L")
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(col - 40, 5.5, _s(value or "—"), align="L")
        pdf.ln(6.5)


def _checks_section(pdf: _Report, width: float, title: str, checks: list) -> None:
    _section(pdf, title)
    if not checks:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 5, "Not applicable for this document type.", align="L")
        pdf.ln(5)
        return
    for check in checks:
        status = str(check.get("status", "review")).lower()
        color = _STATUS_COLORS.get(status, AMBER)
        label = str(check.get("label", ""))
        detail = str(check.get("detail", ""))
        # status chip
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*color)
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.3)
        chip = f"  {status.upper()}  "
        chip_w = pdf.get_string_width(chip) + 2
        y = pdf.get_y()
        pdf.rect(16, y - 0.5, chip_w, 5.5, "D")
        pdf.set_xy(16, y)
        pdf.cell(chip_w, 5, chip, align="C")
        # label
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 30, 30)
        pdf.set_xy(16 + chip_w + 3, y)
        pdf.cell(0, 5, _s(label), align="L")
        pdf.ln(5.5)
        # detail
        if detail:
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*GRAY)
            pdf.set_x(16 + chip_w + 3)
            pdf.multi_cell(width - chip_w - 6, 4.5, _s(detail), align="L")
        pdf.ln(1.5)
    pdf.ln(2)

# SENTRY — AI-Based Fake Identity & Document Screening System

**Smart India Hackathon 2026** · Border checkpoint document verification in seconds.

SENTRY reads identity documents (passport, **Aadhaar**, **PAN**, visa), verifies them
against real government checksum algorithms (ICAO 9303 MRZ, **UIDAI Verhoeff**,
ITD PAN structure), runs pixel-level tampering forensics, verifies faces with
liveness checks, cross-references an officer-managed watchlist, and produces an
**explainable risk score** — while the officer stays in command.

## What it does

| Upload | Outcome |
|---|---|
| Genuine Indian passport | **LOW** — all checks pass |
| Aadhaar (clean) | **LOW** — Verhoeff checksum valid |
| Aadhaar (forged digit) | **100 HIGH** — "not issued by UIDAI" + editor EXIF |
| PAN (surname ≠ 5th char) | **88 HIGH** — impersonation flag |
| Passport (Photoshopped) | **74 HIGH** — EXIF + error-level analysis |
| Blacklisted document/person | **+80 → HIGH** — ⛔ watchlist match |
| Wrong person's face | **HIGH** — identity mismatch |

## Architecture

- **Frontend** — vanilla HTML/CSS/JS console (login, dashboard, screening,
  investigation, trash bin, profile, Hindi/English toggle)
- **Backend** — Python FastAPI + 4 AI modules:
  - OCR (EasyOCR + MRZ / Aadhaar / PAN parsing)
  - Validation (ICAO 9303, Verhoeff, PAN rules, date logic)
  - Tampering forensics (EXIF, error-level analysis, noise consistency)
  - Face verification (deepface/Facenet + simplified liveness)
- **Database** — Neon serverless PostgreSQL (accounts, screenings, watchlist)
- **Privacy** — uploaded images are analyzed via temp files and **never stored**;
  only log-type records persist, and owners can delete those (trash bin included)

## Demo accounts

| Role | User ID | Password |
|---|---|---|
| Officer | `kessler` | `sentry-officer-2026` |
| User | `jordan` | `sentry-user-2026` |

Sample documents live in `backend/samples/` — all synthetic specimens, no real PII.

## Setup (Windows)

1. **Prerequisites:** Python 3.11+ and Git.
2. Clone this repo, then copy `backend/dbconfig.example.py` to
   `backend/dbconfig.py` and paste in the Neon connection string
   (**ask the team lead for it privately — it contains the DB password**).
3. Double-click **`setup.bat`** (creates the virtualenv, installs everything,
   generates sample documents). First install downloads ~4GB of AI libraries.
4. Double-click **`start-sentry.bat`** → open http://127.0.0.1:8901
   (Ctrl+F5 on first load). First screening takes ~15-20s while AI models load.

## Project docs

- `prd.md` — product requirements
- `architecture.md` — system design
- `rules.md` — build constraints & AI honesty rules
- `phases.md` — build phases
- `design.md` — visual design
- `memory.md` — full build log & current status
- `demo-script.md` — the hackathon demo walkthrough

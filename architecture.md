# architecture.md — App Flow, Architecture, Stack & Folder Structure

**Project:** SENTRY — AI-Based Fake Identity & Document Screening System
**Last updated:** 2026-08-27

---

## 1. Tech stack
| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | **Existing vanilla HTML/CSS/JS** (`index.html`, `style.css`, `app.js`) | Already built & styled; we just wire mock functions to real API calls. |
| Backend | **Python 3.10/3.11 + FastAPI** (served by Uvicorn) | Best AI/CV ecosystem; auto OpenAPI docs at `/docs`; trivial to run locally. |
| OCR | **EasyOCR** (primary) or **Tesseract** via `pytesseract` | Mature, real extraction. EasyOCR needs no external install; Tesseract needs the Tesseract-OCR binary on Windows. |
| Image / tampering | **Pillow** + **OpenCV** (`opencv-python`) + **piexif/exifread** | Metadata read, Error-Level-Analysis (ELA), noise/edge checks. |
| Face | **`face_recognition`** if a wheel installs fast; else **`deepface`**; else **OpenCV Haar/DNN detection + heuristic** | See §7 — this is the one risky install on Windows; fallback keeps the pipeline alive. |
| Storage | **SQLite** (`screenings.db`) via `sqlite3` / SQLModel | Zero-setup, file-based, perfect for a 1-day local demo. |
| Server run | `uvicorn main:app --reload` | Serves API **and** the static frontend. |

> Python version note: prefer **3.10 or 3.11** — prebuilt wheels for dlib/face
> libraries are most available there, avoiding a slow source build on Windows.

## 2. High-level architecture
```
┌─────────────────────────────────────────────────────────┐
│  Browser (existing vanilla UI)                            │
│  index.html · style.css · app.js                          │
│  - Officer console + User portal                          │
│  - app.js: fetch() → backend, render results into DOM     │
└───────────────┬───────────────────────────────────────────┘
                │  HTTP (JSON + multipart file upload)
                ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI backend (main.py)                                │
│  Routes → services (the 4 modules) → risk engine → DB     │
│                                                           │
│  services/                                                │
│   ├─ ocr.py         (Module 1)                            │
│   ├─ validation.py  (Module 2)                            │
│   ├─ tampering.py   (Module 3)                            │
│   ├─ face.py        (Module 4 + liveness/PAD)             │
│   └─ risk.py        (combine → score + reasons)           │
│                                                           │
│  storage.py (SQLite)   uploads/ (saved images)            │
└─────────────────────────────────────────────────────────┘
```
The frontend does **no AI**. All intelligence lives in the backend services.

## 3. Folder structure (target)
```
website contents all/
├─ index.html            # existing UI (unchanged structure)
├─ style.css             # existing design system
├─ app.js                # existing — swap mock fns for fetch() calls
│
├─ backend/
│  ├─ main.py            # FastAPI app + routes + static file serving
│  ├─ storage.py         # SQLite init + save/load screenings
│  ├─ risk.py            # risk engine: module outputs → score/tier/reasons
│  ├─ services/
│  │  ├─ ocr.py
│  │  ├─ validation.py
│  │  ├─ tampering.py
│  │  └─ face.py
│  ├─ uploads/           # saved document + face images (gitignored)
│  ├─ samples/           # test document images for the demo
│  └─ requirements.txt
│
├─ screenings.db         # SQLite (created at runtime)
│
├─ prd.md  architecture.md  rules.md  phases.md  design.md  memory.md
```

## 4. End-to-end screening flow (officer path)
1. Officer opens **New Screening**, drops a document image (+ optional live face).
2. `app.js` POSTs the file(s) to `POST /api/screen` (multipart).
3. Backend saves the image, then runs, in order:
   - `ocr.extract(image)` → fields
   - `validation.check(fields)` → validation flags
   - `tampering.analyze(image)` → tampering flags + signals
   - `face.verify(doc_photo, live_face)` → match score + liveness (if provided)
   - `risk.score(...)` → `{score, tier, reasons[]}`
4. Backend writes a record to SQLite and returns one JSON payload.
5. `app.js` renders it into the **Processing** log and **Result** view (gauge,
   extracted fields, flags, face-match bar).
6. Officer picks Approve/Escalate/Deny and **confirms** → `POST /api/decision`
   updates the record + audit timeline.

## 5. API surface (minimum for the demo)
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/screen` | multipart: `document` (required), `face` (optional). Runs all modules, returns full result JSON, persists it. |
| `GET`  | `/api/screenings` | list recent screenings (feeds Dashboard live feed + Investigation). |
| `GET`  | `/api/screenings/{id}` | one screening's full result. |
| `POST` | `/api/decision` | `{id, decision, officer, note}` → record final officer decision. |
| `POST` | `/api/liveness` | (user portal) run PAD check on a face frame. |
| `POST` | `/api/query` | (user portal) submit a query package to officers. |
| `GET`  | `/` and static | serve `index.html`, `style.css`, `app.js`. |

### Canonical `/api/screen` response shape
```json
{
  "id": "DOC-88232",
  "docType": "passport",
  "fields": { "name": "...", "documentNo": "...", "nationality": "...",
              "dob": "...", "expiry": "...", "gender": "..." },
  "validation": [ { "label": "MRZ checksum", "status": "pass|review|fail", "detail": "..." } ],
  "tampering":  [ { "label": "Stamp forgery", "status": "review", "detail": "...", "signal": 0.62 } ],
  "face": { "match": 0.88, "liveness": "pass|review|na" },
  "risk": { "score": 75, "tier": "HIGH", "reasons": ["Stamp ink density inconsistent", "..."] },
  "createdAt": "2026-08-27T08:42:11"
}
```
Keep field names aligned with what `app.js` renders so wiring is a rename, not a redesign.

## 6. Data model (SQLite — one table is enough for day 1)
`screenings(id TEXT PK, doc_type, fields_json, validation_json, tampering_json,
face_json, risk_score, risk_tier, reasons_json, decision, officer, note,
created_at, image_path)`

## 7. Module implementation notes (the hybrid approach)
- **OCR (real):** EasyOCR `readtext()` → regex/heuristics to map lines to fields;
  parse the MRZ (bottom 2 lines of passports) for reliable name/number/DOB/expiry.
- **Validation (real, rule-based):** MRZ check-digit algorithm, `datetime`
  comparisons (expired? DOB plausible? expiry after issue?), regex for formats.
- **Tampering (real heuristics):**
  - Metadata: read EXIF; flag missing/edited-software tags (`Photoshop`, `GIMP`).
  - **ELA** (Error-Level Analysis): re-save JPEG at known quality, diff to expose
    edited regions.
  - Noise/edge inconsistency around the photo & stamp regions via OpenCV.
  - Each check emits a 0–1 signal; combined into flags.
- **Face (best-effort real + fallback ladder):**
  1. Try `face_recognition.compare_faces` / distance (needs dlib wheel).
  2. Else `deepface.verify` (downloads a model on first run — pre-warm it).
  3. Else OpenCV face **detection** in both images + a histogram/embedding
     similarity, clearly labeled as a simplified score.
  - Liveness/PAD for day 1 = basic checks (single face present, not a flat
    screenshot via variance/reflection heuristics); label honestly.
- **Risk engine (real, transparent):** weighted sum of normalized signals →
  0–100; thresholds → LOW (<40) / MED (40–69) / HIGH (≥70); always return the
  list of contributing reasons so the UI can explain the score.

## 8. Frontend wiring plan (minimal edits to `app.js`)
- Replace `goTo('processing')`/`goTo('result')` mock hops with a real
  `screenDocument()` that: uploads → shows the pipeline → fetches result →
  fills the Result DOM (gauge, `.extract-val`, `.flag-item`, match bar).
- Replace `confirmDecision()` to also `POST /api/decision`.
- Dashboard live feed + investigation pull from `GET /api/screenings`.
- No framework, no build step — just `fetch` + DOM updates.

## 9. Known risks & mitigations
| Risk | Mitigation |
|------|-----------|
| dlib/face libs won't install on Windows in time | Fallback ladder in §7; time-box to ~20 min then drop to OpenCV heuristic. |
| Tesseract binary not installed | Use EasyOCR (pip-only) as primary. |
| OCR field mapping messy across doc types | Focus the demo on **passport MRZ** (most structured); treat others as best-effort. |
| CORS during local dev | Serve frontend from FastAPI (same origin) — no CORS needed. |

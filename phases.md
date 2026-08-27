# phases.md — Build Phases (1-Day Sprint)

**Project:** SENTRY — AI-Based Fake Identity & Document Screening System
**Last updated:** 2026-08-27
**Total budget:** ~1 working day. Times are guides — protect the **must-haves**.

> Golden rule: **get a full end-to-end slice working first, then deepen each
> module.** A complete rough pipeline beats one polished module. Update
> [memory.md](memory.md) at the end of every phase.

---

## Phase 0 — Setup & skeleton  ·  ~45 min  ·  MUST-HAVE
- [ ] Create `backend/` structure (see [architecture.md](architecture.md) §3).
- [ ] `requirements.txt` + install: fastapi, uvicorn, python-multipart, pillow,
      opencv-python, numpy, easyocr. (Face libs installed in Phase 5.)
- [ ] `main.py`: FastAPI app that serves `index.html`/`style.css`/`app.js`
      (same origin → no CORS) and exposes `GET /api/health`.
- [ ] Confirm `uvicorn main:app --reload` serves the existing UI in the browser.
- [ ] Add 2–3 sample document images to `backend/samples/`.
**Exit:** UI loads from FastAPI; health endpoint returns OK.

## Phase 1 — Vertical slice (fake AI, real plumbing)  ·  ~1 hr  ·  MUST-HAVE
- [ ] `POST /api/screen` accepts an upload, saves it, returns a **hard-coded**
      response in the exact contract shape ([architecture.md](architecture.md) §5).
- [ ] `storage.py`: SQLite init + insert/select; screen endpoint persists a row.
- [ ] Wire `app.js`: New Screening upload → `fetch('/api/screen')` → show
      Processing → render into Result view (gauge, fields, flags, match bar).
**Exit:** Upload a file in the real UI and see it flow to a real (stub) Result
that's saved to the DB. **This is the backbone — everything else swaps stubs for real logic.**

## Phase 2 — Module 1: OCR (real)  ·  ~1 hr  ·  MUST-HAVE
- [ ] `services/ocr.py`: EasyOCR reads the image; parse **passport MRZ** for
      name/number/nationality/DOB/expiry/gender; best-effort for other types.
- [ ] Replace stub `fields` with real extraction; keep a safe fallback on failure.
**Exit:** Real fields from a real passport image appear in the Result view.

## Phase 3 — Module 2: Validation (real, rules)  ·  ~45 min  ·  MUST-HAVE
- [ ] `services/validation.py`: MRZ check-digit verify, expiry/DOB date logic,
      field-format regex → list of `{label,status,detail}`.
- [ ] Render as the Result "Detection flags" / cross-validation rows.
**Exit:** Tampered/expired sample yields visible validation flags.

## Phase 4 — Module 3: Tampering (real heuristics)  ·  ~1 hr  ·  MUST-HAVE
- [ ] `services/tampering.py`: EXIF/metadata check, ELA, noise/edge check → flags + 0–1 signals.
- [ ] Render into the Result detection-flags panel.
**Exit:** An edited image produces a visible tampering flag with a reason.

## Phase 5 — Module 4: Face verification  ·  ~1 hr  ·  SHOULD-HAVE (time-boxed)
- [ ] Install face lib via the fallback ladder ([architecture.md](architecture.md) §7).
      **Hard stop at ~20 min of install pain → drop to OpenCV heuristic.**
- [ ] `services/face.py`: compare doc photo vs uploaded/live face → match 0–1;
      basic liveness/PAD for the user portal.
- [ ] Render the face-match bar; wire the user-portal liveness screen.
**Exit:** A match percentage renders; if fallback used, it's labeled "simplified".

## Phase 6 — Risk engine + integration  ·  ~45 min  ·  MUST-HAVE
- [ ] `risk.py`: normalize + weight all module signals → score, tier, reasons.
- [ ] `/api/screen` returns the fully assembled real payload; gauge shows the
      real score/tier and the reasons list.
- [ ] `/api/decision` records the officer's confirmed decision; dashboard live
      feed + investigation read from `GET /api/screenings`.
**Exit:** One upload runs all real modules → real score → officer confirms →
record shows up in dashboard/investigation.

## Phase 7 — Polish & demo prep  ·  ~1 hr  ·  MUST-HAVE
- [ ] Smooth the Processing animation to reflect real step completion.
- [ ] Error states: failed upload, low-confidence OCR, no face found.
- [ ] Prepare **3 demo docs**: (a) clean pass, (b) expired/invalid, (c) tampered
      → so the demo shows LOW, MED, and HIGH outcomes.
- [ ] Write/rehearse the demo script from [prd.md](prd.md) §9.
- [ ] Final [memory.md](memory.md) update.
**Exit:** Confident, repeatable 3-case demo.

---

## Cut list (drop these first if time runs short)
1. Real face match → use OpenCV heuristic / labeled placeholder.
2. User-portal liveness realism → keep the existing animation, label as demo.
3. Related-identity / watchlist lookups.
4. Persistence polish (dashboard can show a mix of real + seeded rows).

## Stretch (only if ahead of schedule)
- Real password auth; watchlist seed data; multi-doc-type OCR; PDF export of a
  screening report; confidence bars per extracted field.

## Progress tracking
Keep the live checklist and "current phase / current file" pointer in
**[memory.md](memory.md)** — update it after every phase so a fresh session can
resume without re-deriving anything.

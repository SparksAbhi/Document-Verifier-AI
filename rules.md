# rules.md — What to Use, What to Build, Boundaries

**Project:** SENTRY — AI-Based Fake Identity & Document Screening System
**Last updated:** 2026-08-27

These are the guardrails for building SENTRY in one day. When in doubt, choose
the option that keeps a **working end-to-end demo** intact.

---

## 1. Product hard rules (non-negotiable)
1. **AI is advisory only.** The system NEVER auto-approves or auto-denies. It
   produces a score + reasons; a human officer must **explicitly confirm** the
   final decision. This must be visible in the UI (the existing disclaimers stay).
2. **Every risk score is explainable.** No score ships without a `reasons[]` list.
3. **Be honest about fidelity.** If a check is a heuristic or a fallback, label
   it as such in the UI/response (e.g. "simplified face score"). Do not present
   a mock as if it were a trained model — judges will ask.
4. **PII stays local.** Document images and extracted data are sensitive. Store
   only on the local machine, never POST to third-party cloud AI in the demo,
   and provide a way to purge `uploads/` + the DB.

## 2. Approved libraries / tools
Use these; don't introduce heavier alternatives without a reason.
- **Web:** FastAPI, Uvicorn, python-multipart (file uploads), Jinja not needed.
- **OCR:** EasyOCR (primary), pytesseract (only if Tesseract binary present).
- **Imaging:** Pillow, opencv-python, numpy; piexif or exifread for metadata.
- **Face:** face_recognition → deepface → OpenCV (fallback ladder, pick the
  first that installs cleanly; see [architecture.md](architecture.md) §7).
- **Storage:** built-in `sqlite3` (or SQLModel if convenient).
- **Frontend:** none added — plain `fetch` + DOM. No React, no bundler, no npm.

Pin versions in `backend/requirements.txt`. Prefer pip wheels over source builds.

## 3. What to BUILD vs. what to REUSE
- **Reuse:** the entire existing UI (`index.html`, `style.css`), the design
  tokens, the pipeline/gauge/flag components — do not restyle from scratch.
- **Build:** the FastAPI backend, the 4 service modules, the risk engine, the
  SQLite layer, and the `fetch`-based wiring inside `app.js`.
- **Edit `app.js` surgically:** replace mock `goTo(...)` jumps and `confirm*`
  functions with real calls. Keep function names where possible so the HTML
  `onclick=` handlers keep working.

## 4. Coding conventions
- Python: type hints on service function signatures; one module = one concern;
  each service exposes a single clear entry function (`extract`, `check`,
  `analyze`, `verify`, `score`).
- Return **plain dicts** shaped exactly like the API contract in
  [architecture.md](architecture.md) §5 — the frontend depends on those keys.
- No secrets in code. No hard-coded absolute paths — use paths relative to the
  backend folder.
- JS: keep it vanilla and readable; match the existing style in `app.js`
  (function-per-action, `document.getElementById`). No new dependencies.

## 5. Error handling
- Backend never crashes the request on a module failure. Each module wraps its
  work in try/except and returns a **degraded-but-valid** result
  (e.g. `{"status": "review", "detail": "OCR low confidence"}`) so the pipeline
  always completes and the officer still sees something.
- `/api/screen` returns HTTP 200 with partial results + a `warnings[]` array
  rather than a 500, unless the upload itself is invalid (then 400).
- Frontend shows a clear inline message on fetch failure; never leaves the
  pipeline spinner stuck forever (always resolve or timeout).
- Log module errors to console/stdout for debugging during the build.

## 6. Boundaries for the AI assistant (Claude) building this
- **Time-box ruthlessly.** This is a 1-day build. If a real library (esp. face)
  isn't installing within ~20 minutes, switch to the documented fallback and
  keep moving. Note the switch in [memory.md](memory.md).
- **Demo-first ordering.** Get a full ugly end-to-end path working before
  polishing any single module. A complete pipeline beats one perfect module.
- **Don't over-engineer.** No auth frameworks, no ORMs beyond SQLite, no
  microservices, no Docker for day 1. One FastAPI app.
- **Don't restructure the frontend.** Wire it; don't rewrite it.
- **Ask before destructive actions** (deleting files, wiping the DB) unless
  clearly instructed.
- **Update [memory.md](memory.md) after each phase** — this is the continuity
  contract if the session/credits run out mid-build.
- Keep changes reviewable: small, focused edits over sweeping rewrites.

## 7. Definition of done (per module)
A module is "done for the demo" when: it runs on a real sample image, returns
the exact contract shape, fails safe on bad input, and its output visibly
renders in the existing UI.

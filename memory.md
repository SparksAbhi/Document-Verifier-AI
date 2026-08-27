# memory.md — Live Project Memory & Handoff

> **PURPOSE:** context continuity. If the session/credits run out and work moves
> to a fresh chat, this file lets a new assistant resume **without redoing
> anything**. **UPDATE THIS AFTER EVERY MEANINGFUL STEP.**
>
> **Project:** SENTRY — AI-Based Fake Identity & Document Screening System (SIH)
> **Working dir:** `C:\Users\spaul\Desktop\sih\website contents all`

---

## 🔴 CURRENT STATUS  ·  updated 2026-08-28 (INDIA EDITION COMPLETE)
- **Overall:** "Designed for India" upgrade complete: real Aadhaar validation
  (Verhoeff checksum — the actual UIDAI algorithm), real PAN validation
  (structure + holder-type + surname-initial rules), officer watchlist/
  blacklist (checked on every screening, +80 risk on match), 5 new Indian
  specimen samples (incl. tampered/mismatch variants), and an EN/हिंदी
  language toggle. All verified end-to-end.
- **New in this update:**
  - `services/indian_docs.py`: Verhoeff tables (d/p/inv), aadhaar_valid/
    check_digit, PAN structure/holder-type/surname-initial helpers.
  - `ocr.py` `_detect_indian_card`: detects Aadhaar/PAN via markers
    (UIDAI/INCOME TAX DEPARTMENT), extracts number via regex + name/dob/
    gender via label matching (exact-line labels avoid FATHER'S NAME
    matching NAME; `.replace(' ','').isalpha()` for multi-word names).
  - `validation.py`: _check_aadhaar (Verhoeff fail = CRITICAL 72pts),
    _check_pan (structure CRITICAL; holder type; surname-initial match),
    _common_field_checks (DOB logic). MRZ path unchanged.
  - Watchlist: Neon table + GET/POST/DELETE /api/watchlist; screening
    cross-checks doc number + name; match → +80 risk, ⛔ red reason row,
    validation "Watchlist check: fail" flag; Investigation view has the
    manager UI (add/remove entries, loads on view entry).
  - Samples: aadhaar_clean (valid Verhoeff), aadhaar_tampered (bad checksum
    + GIMP EXIF), pan_clean (surname K matches 5th char), pan_mismatch
    (R≠K flagged), passport_india (tricolor header specimen).
  - Hindi toggle: I18N dict + applyLanguage() (data-enText caching); toggle
    buttons in sidebar + login fab (हिं); covers nav, dashboard, upload,
    processing, result, portal labels.
- **Verified via API:** aadhaar_clean → Verhoeff pass + watchlist match →
  80 HIGH; aadhaar_tampered → 100 HIGH (checksum+EXIF+watchlist);
  pan_mismatch → 88 HIGH; watchlist add/remove round-trip.
- **Demo accounts:** Officer `kessler` / `sentry-officer-2026` · User
  `jordan` / `sentry-user-2026`.
- **Server state:** RUNNING on :8901 backed by Neon.

### How to run the backend (verified working)
```
"C:\Users\spaul\Desktop\sih\website contents all\.venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8901 --app-dir "C:\Users\spaul\Desktop\sih\website contents all\backend"
```
Then open http://127.0.0.1:8901/ (UI), http://127.0.0.1:8901/api/health (probe),
http://127.0.0.1:8901/docs (OpenAPI).

## ✅ Done
- [x] Read & understood the existing prototype (`index.html`, `style.css`, `app.js`).
- [x] Collected user decisions (see below).
- [x] Wrote the 6 planning docs: prd, architecture, rules, phases, design, memory.
- [x] **Phase 0:** backend skeleton + deps + samples (details below).
- [x] **Phase 1:** vertical slice (details below).
- [x] **Phase 2:** real OCR (details below).
- [x] **Phase 3:** real validation (details below).
- [x] **Phase 4:** real tampering heuristics (details below).
- [x] **Phase 5:** real face verification (details below).
- [x] **Phase 6:** risk engine + decision + live views (details below).
- [x] **Phase 7:** polish + demo prep (details below).

### Phase 7 details (2026-08-28)
- **Processing view (honest animation):** stage messages match the real
  pipeline (OCR → validation → forensics → [face if attached] → risk
  engine), final stage replaced by a real completion summary line with
  actual score/tier/flag count + face-check line when a face was uploaded.
  `markPipelineComplete()` marks everything done EXCEPT the final "Officer
  final verification" node (honest: that step is the human's). On error a
  "← Back to upload" button appears.
- **Result view shows the uploaded document image**: new endpoint
  `GET /api/screenings/{id}/image` serves the stored upload; `renderResult`
  swaps the placeholder icon for the image (falls back to icon on 404).
- **5th sample — `visa_specimen.jpg`** (Type L visa, no MRZ): demonstrates
  the honest MED path (43 MED: structure-review + no-MRZ reasons).
- **Tampering fix:** `analyze(image_path, mrz_found)` — ELA/noise GRID checks
  are passport-layout-calibrated; on non-MRZ documents (visa bands/blank
  areas → grid false positives, e.g. visa scored 95 HIGH before) they are
  skipped with an explicit "Pixel-grid forensics skipped" pass-flag note;
  EXIF metadata check always runs. Verified: visa 43 MED, tampered still
  74 HIGH, clean 0 LOW.
- **`backend/purge.py`**: interactive PII purge (requires typing PURGE) —
  deletes all DB rows + uploaded images (rules.md §1.4).
- **`demo-script.md`** at project root: full walkthrough (opening line, 4+
  cases with expected scores/timings, close-the-loop section, honesty notes
  for judges, timing table).
- **`backend/requirements.txt`** updated to the real dependency set
  (fastapi/uvicorn/multipart/pillow/numpy/opencv/easyocr/deepface/tf-keras).

### Phase 6 details (2026-08-27)
- **`risk.py` (real weighted engine):** critical validation fail (MRZ
  checksums/expiry/DOB/date-consistency — via `CRITICAL_LABELS` exported from
  validation.py) +72; other validation fail +30; validation review +8;
  tampering fail +40×signal (min .5 floor); tampering review +12; face
  verified=False +50; liveness review +12; no MRZ +35. Cap 100. Tiers:
  HIGH≥70, MED≥40, LOW<40. Reasons list = every contributing point.
- **`storage.py`:** +`get_screening(id)`, +`record_decision(id, decision,
  officer, note)` (UPDATE; returns False if id unknown).
- **`main.py`:** `_build_payload` now calls `risk_score(...)` (interim
  heuristic REMOVED). New endpoints: `GET /api/screenings/{doc_id}` (404 if
  missing), `POST /api/decision` (validates approve|escalate|deny; pydantic
  DecisionRequest; 404 unknown id; officer defaults "R. Kessler").
- **Frontend (app.js + index.html):** `confirmDecision()` → POST
  /api/decision (offline → "recorded locally" message + still shows banner);
  after success calls `refreshDashboard()`. Dashboard: stats (# total,
  LOW/MED/HIGH counts), live feed table (top 8, click → investigation),
  escalation queue (HIGH + undecided, click → investigation), nav badge =
  open HIGH count — all from `GET /api/screenings`; refreshes on every
  `goTo('dashboard')`. Investigation view: `openInvestigation(id)` fetches
  `GET /api/screenings/{id}` → builds timeline (screened → AI recommendation
  w/ tier color → per-flag tampering/validation events → decision or
  awaiting), related identities (doc no), status line shows decision state.
  Old hard-coded mock rows REMOVED from dashboard/investigation HTML
  (empty-state notes added).
- **Verified:** 4 samples via API — clean 0 LOW (1 reason), expired 72 HIGH,
  tampered 74 HIGH (EXIF 34 + ELA 40), badchecksum 72 HIGH. Decision
  round-trip: POST deny → GET shows decision/officer/note persisted.
  Dashboard feed: 26 records. `node --check` passes.

### Phase 5 details (2026-08-27)
- **Install ladder:** `face_recognition` FAILED (dlib needs Visual Studio C++
  build tools, no py3.13 wheel — expected risk). `deepface` installed OK but
  needed `tf-keras` (tensorflow 2.21 compat) AND a server stop first: the
  running uvicorn had `cv2.pyd` locked (WinError 5) because deepface swaps
  opencv-headless→opencv. LESSON: **stop the server before big pip installs.**
- **OpenCV 5 gotchas:** `cv2.CascadeClassifier` NO LONGER EXISTS in cv2 5.0 —
  deepface's "opencv" detector backend is broken. Use `detector_backend=
  'mtcnn'` (works, already installed via deepface deps). face.py uses mtcnn.
- **`services/face.py` (real):** `verify(doc_path, face_path)` → {match,
  verified, liveness, detail, method}. deepface.verify with Facenet +
  mtcnn; match = linear confidence `1 - distance/(2*threshold)` (0 at 2×
  threshold, 0.5 at threshold). Liveness = SIMPLIFIED (honest label):
  exactly 1 face via deepface.extract_faces(mtcnn) → pass, else review.
  No face provided → match None / liveness "na". Never raises.
- **Test faces:** `backend/samples/faces/` — img1/img2/img11 are the SAME
  person in deepface's dataset; img13 is different (careful when demoing!).
  Downloaded from `tests/unit/dataset/` (path moved from `tests/dataset/`).
  Facenet weights cached in `~/.deepface/weights/`.
- **Verified:** img1 vs img2 → 0.714 verified True; img1 vs img11 → same
  person (dataset quirk, NOT a bug — distance 0.205); img1 vs img13 → 0.0
  verified False. Full API: same-face → face.match .714 in payload;
  diff-face → 0.0 + verified false. Note: deepface test images carry their
  own Photoshop 7.0 EXIF — the tampering module correctly flags them.
- **`main.py`:** `/api/screen` now runs face_service.verify(doc_path,
  face_path); face mismatch (verified=False, no other fails) → 75 HIGH
  "possible identity mismatch". Face detail string flows to reasons.
  Precedence: tamper/validation fail > face mismatch > no-MRZ > reviews.

### Phase 4 details (2026-08-27)
- **`services/tampering.py` (real):** `analyze(image_path)` → {"flags":[…],
  "maxSignal"}; never raises (unreadable image → review flag). Three checks:
  1. **EXIF metadata** — editor-software regex (photoshop|gimp|lightroom|…)
     on EXIF Software tag 305 → fail w/ signal .85; benign tag → pass.
  2. **ELA** — |orig − re-save(JPEG q90)| per pixel, 10×7 grid of cell means,
     robust z-score (median+MAD, scale floored at 10% of median to avoid
     exploding z on near-constant grids); FAIL ≥25σ, REVIEW ≥12σ.
  3. **Noise/edge** — Laplacian² energy per grid cell, same z scoring;
     FAIL ≥12σ, REVIEW ≥8σ.
  Non-JPEG uploads get one pre-resave before ELA baseline (still meaningful).
- **Calibration (measured):** clean/expired/badchecksum ELA z ≈ 6.6,
  tampered z ≈ 139.5 → thresholds 12/25 give huge margin. All 3 clean
  samples → all-pass; tampered → EXIF fail + ELA fail (locates the patch at
  grid 1/4 = printed-name row) + noise pass.
- **`main.py`:** `/api/screen` now runs tampering.analyze; `_build_payload`
  takes tamper dict; interim HIGH bumped 72→78 (tamper is stronger evidence).
  Warnings propagate module-failure review flags (signal==0.5).
- **Verified via API:** tampered → 78 HIGH (Photoshop tag + ELA 139.5σ);
  clean → 10 LOW all-pass. ~5.5s/screening.

### Phase 3 details (2026-08-27)
- **`services/validation.py` (real):** `check(extraction)` → list of
  {label,status,detail} flags. Rules: 5 MRZ check digits (ICAO 9303 TD3:
  number/dob/expiry/optional/composite, weights 7-3-1), expiry logic
  (expired→fail with days count, <180 days left→review, else pass), DOB
  logic (future→fail, age>100→review, else pass), expiry<DOB consistency,
  document-number format regex `[A-Z0-9]{6,9}`, nationality 3-letter code +
  recognition vs ocr.NATIONALITIES map, gender M/F/X, low OCR confidence
  (<0.35) → review. All statuses: pass/review/fail.
- **`main.py`:** `_build_payload` now runs `validation.check(extraction)`;
  interim risk: any fail→72 HIGH, reviews→45 MED, all pass→10 LOW,
  no MRZ→55 MED (real engine is Phase 6). Reasons list = failed/reviewed
  flag details.
- **`services/ocr.py`:** renamed `_NATIONALITIES`→`NATIONALITIES` (public,
  used by validation).
- **Samples:** added 4th — `passport_badchecksum.jpg` (one number digit
  altered w/o check-digit update; number + composite mismatch). Regenerator
  updated. All 4 regenerated.
- **Verified via API:** clean→10 LOW all-pass; expired→72 HIGH "EXPIRED on
  02 Jun 2019 (2643 days ago)"; badchecksum→72 HIGH "mismatch: passport
  number, composite" (OCR read altered number C40217756). ~5.4s/screening.

### Phase 2 details (2026-08-27)
- **`services/ocr.py` (real):** lazy singleton EasyOCR Reader (en, CPU) with
  thread lock; `prewarm()` runs in a daemon thread at app startup. `extract(
  image_path)` never raises → returns `{docType, fields, mrz, textLines,
  ocrConfidence, warnings}`. Pipeline: readtext(detail=1) → cluster boxes into
  lines by y-proximity → find TD3 MRZ pair (44 chars, `P<XXX` + structured
  line2) → parse name (line1 `SURNAME<<GIVEN`), docNo, nationality (ISO→name
  map), DOB (1900s/2000s split at yy<27), expiry (2000s), sex. If MRZ not
  found at full scale → retry on 2x-upscaled bottom-third crop. EasyOCR quirk:
  it accepts `str` paths, NOT `Path` (str-convert in `_read`).
- **`main.py` changes:** import services.ocr + prewarm thread; `/api/screen`
  now calls `ocr.extract(doc_path)` and builds payload via `_build_payload`
  (replaces `_stub_payload`). Honest placeholders: MRZ found → structure/
  completeness pass flags + OCR-confidence note; MRZ missing → "review" flag
  + MED 55 risk (no fabricated passes). Version bumped 0.3.0.
- **Static files now served with `Cache-Control: no-cache`** (fixed the user's
  stale-JS problem — browser always revalidates now).
- **Verified:** direct module tests on all 3 samples — clean: John Doe /
  C40217755 / 14 Mar 1989 / expiry 2031; expired: expiry **02 Jun 2019** ✓;
  tampered: MRZ intact (as designed — EXIF/ELA is Phase 4's job). Full API:
  POST clean → DOC-88235 real fields; POST expired → DOC-88236 real expiry.
  EasyOCR weights (~100MB) now cached in `~/.EasyOCR/` (one-time download done).
- **OCR confidence on samples ~46-49%** — fine for MRZ parsing (works), don't
  show raw confidence as a "quality" metric without context; Phase 3 can use
  it as a soft signal.

### Phase 1 details (2026-08-27)
- **Backend:** `storage.py` (SQLite `screenings` table per arch §6; fresh
  conn per call — thread-safe for uvicorn; `next_doc_id()` continues from
  DOC-88233 to blend with the mock dashboard feed). `main.py` now has
  `POST /api/screen` (multipart: document required, face optional; saves to
  `backend/uploads/DOC-XXXXX.jpg`; returns stub payload in exact §5 contract
  shape + `warnings[]`; 400 on empty upload; storage failure degrades to a
  warning, never a 500) and `GET /api/screenings` (newest first).
- **Frontend wiring (surgical):** `index.html` — upload dropzones now open a
  real file picker (hidden `<input type=file>`, ids `doc-file`/`face-file`),
  dropzones show selected filename (`.dropzone.loaded` green state);
  "Begin analysis" calls `startScreening()`; Processing view has ids
  (`proc-title`, `proc-sub`, `proc-log`, `btn-view-result` — hidden until
  done); Result view has ids on all dynamic elements (`result-title/-sub`,
  `fld-{name,documentNo,nationality,dob,expiry,gender}`, `result-flags`,
  `result-flags-empty`, `gauge-arc/-score/-tier`, `risk-reasons`,
  `face-match-pct/-bar`). Added "Risk reasons" card. `style.css` — added
  `.dropzone.loaded`, `.upload-hint`, `.reason-list` (nothing restyled).
  `app.js` — new state vars (`pendingDocFile/FaceFile`, `currentResult`) +
  functions: `handleFileSelect`, `startScreening` (validates doc selected,
  resets decision UI, fetch → render; timeout-free but always resolves or
  errors with an inline log line), `logLine`, `resetPipeline`,
  `markPipelineStep` (drives `.done`/`.active` from step progress),
  `renderResult` (fields, flags w/ pass-vs-review coloring, gauge arc math
  427·(1-score/100) + tier color, reasons list, face-match bar or N/A).
- **Verified:** POST passport_clean → DOC-88233 + DB row + upload file saved;
  POST passport_expired → DOC-88234; GET /api/screenings returns both;
  `node --check app.js` passes; served app.js contains the new functions.

### Phase 0 details (2026-08-27)
- **Env:** Python **3.13.14** (Store install) — NOT the recommended 3.10/3.11.
  All deps installed fine with prebuilt wheels on 3.13, incl. torch. Face libs
  (Phase 5) are the only remaining wheel risk → fallback ladder applies.
- **Venv:** `.venv/` at project root — ALWAYS run via its python
  (`"C:\Users\spaul\Desktop\sih\website contents all\.venv\Scripts\python.exe"`).
- **Created:** `backend/main.py` (FastAPI: serves index.html/style.css/app.js
  from parent dir + `GET /api/health`), `backend/requirements.txt`,
  `backend/storage.py` + `backend/risk.py` + `backend/services/{ocr,validation,
  tampering,face}.py` (docstring stubs for Phases 1–6), `backend/uploads/`,
  `backend/samples/generate_samples.py`, `.gitignore`.
- **Installed & verified imports:** fastapi 0.141.1, uvicorn 0.52.4,
  python-multipart 0.0.32, pillow 12.3.0, opencv-python-headless 5.0.0.93
  (headless: easyocr dep — do NOT also install opencv-python),
  numpy 2.5.2, easyocr 1.7.2, torch 2.13.0, torchvision 0.28.0.
- **Samples:** `backend/samples/` — `passport_clean.jpg` (valid, MRZ checks
  all pass), `passport_expired.jpg` (expiry 2019 → validation flag),
  `passport_tampered.jpg` (printed "J0HN" patched over "JOHN" + EXIF Software
  = "Adobe Photoshop 26.1"). Regenerate via
  `python backend/samples/generate_samples.py`. MRZ check digits verified
  programmatically (number/dob/expiry/composite all correct).
  Note: samples are synthetic "REPUBLIC OF SPECIMEN" passports — no real PII.
- **Smoke test PASSED:** uvicorn on :8901 → `/api/health` = OK, `/`, `/style.css`,
  `/app.js`, `/docs` all 200. Server was stopped after the test.
- **Note:** EasyOCR downloads model weights (~100MB) on FIRST real OCR call —
  expect a slow first request in Phase 2 (pre-warm during that phase).

## ⏳ Not started (see [phases.md](phases.md))
- [x] Phase 0 — backend skeleton + serve UI ✅ (2026-08-27)
- [x] Phase 1 — vertical slice (stub `/api/screen` + SQLite + wire `app.js`) ✅ (2026-08-27)
- [x] Phase 2 — OCR (real, EasyOCR + MRZ) ✅ (2026-08-27)
- [x] Phase 3 — Validation (rules) ✅ (2026-08-27)
- [x] Phase 4 — Tampering (metadata/ELA/noise) ✅ (2026-08-27)
- [x] Phase 5 — Face verification (fallback ladder, time-boxed) ✅ (2026-08-27)
- [x] Phase 6 — Risk engine + integration + `/api/decision` ✅ (2026-08-27)
- [x] Phase 7 — polish + 3-case demo prep ✅ (2026-08-28)

- 2026-08-28 — **Camera + liveness feature:** `POST /api/liveness` (frames
  burst → `face.liveness()`: 64x64 grayscale mean-abs-diff motion analysis
  [static<0.8 fail / <1.8 review / >30 flicker review] + MTCNN face-count on
  first/last frame; temp files, cleaned up). Frontend: camera modal (getUserMedia,
  mirrored preview + scan animation), captures 8 frames @350ms, shows
  per-check verdicts, "Use this capture" sets pendingFaceFile (last frame);
  face dropzone has explicit "Open camera" / "Upload photo" buttons.
  Verified: identical frames → FAIL (motion 0.0, printed photo), distinct
  images → flicker review (correct — real camera motion lands 2-30 → pass).
- 2026-08-28 — **Camera bugfix:** liveness capture hung forever because
  `_captureFrame` used `canvas.convertToBlob` (OffscreenCanvas-only API —
  throws on regular canvas). Fixed to `canvas.toBlob` in a Promise; capture
  loop now try/caught (error shows in status + Start button restored, never
  a stuck spinner). User symptom was "scan animation but nothing after".
- 2026-08-28 — **User portal + logout + login camera:** REAL user flow —
  login liveness now uses the actual camera (`startLoginLiveness`: getUserMedia
  → 8 frames → POST /api/liveness → maps motion/face checks onto the login
  checklist; camera-denied → continue with warning); user portal Submit
  Query page is real (doc upload + optional camera/upload face + query
  textarea + "Run verification checks" runs the FULL /api/screen pipeline,
  checks reflect real validation/tampering/face results + summary with risk
  score; Submit → POST /api/query persists QRY-XXXXX w/ linked screening id;
  "My queries" table live from GET /api/queries, refreshes on portal entry).
  New backend: queries table (storage.py: next_query_id/insert_query/
  list_queries; ids start QRY-51043), POST /api/query + GET /api/queries in
  main.py. `logout()` for both roles: stops camera streams, clears state
  (pendingDocFile/FaceFile/currentResult/userQueryState), returns to role
  select. Camera modal takes target param ('officer'/'user') — useFaceCapture
  routes the captured face to the right portal. Verified: QRY-51043
  round-trip via curl; node --check + backend import OK.
- 2026-08-28 — **Real authentication:** `services/auth.py` (PBKDF2-SHA256
  600k iters, 16B salt, hmac.compare_digest; token_urlsafe sessions).
  Storage: users + sessions tables (split schema — sqlite rejects
  multi-statement execute), create_user/get_user_by_email/get_password_hash/
  create_session/get_session_user/delete_session. Endpoints: POST
  /api/auth/{signup,login,logout} + GET /api/auth/me; httpOnly cookie
  `sentry_session` (GOTCHA: FastAPI Cookie param needs alias= to read a
  non-parameter-name cookie — fixed 401-on-/me bug). Role guard: officer
  login rejects user accounts (403) and vice versa. Seeds at import time:
  officer@checkpoint04.gov/sentry-officer-2026 + jordan@example.com/
  sentry-user-2026. Frontend: real forms (ids ul-/su-/of-), red .auth-error
  boxes, signupUser(), officer/user login hit the API, identity chips show
  the logged-in name+initials, logout() calls /api/auth/logout, session
  restore via /api/auth/me on page load (stays logged in on refresh).
  submitQuery uses the real user's name. Verified: full curl suite — login,
  wrong password 401, role guard 403, signup 201, duplicate 409, logout →
  /me 401. Better Auth was considered and rejected (Node-only; rules.md
  forbids a second server).
- 2026-08-28 — **Neon cloud database + accounts/trash features:** installed
  psycopg[binary]+psycopg-pool; `backend/dbconfig.py` holds the Neon URL
  (GITIGNORED; env.txt too). `storage.py` REWRITTEN for Postgres: connection
  pool, %s placeholders, dict rows; users table gains `username` (unique,
  login by email OR username via get_user_by_login); screenings/queries gain
  `owner_user_id` (per-account history — all list/get/insert calls scoped)
  and `deleted_at` (soft delete). New: soft_delete_screening /
  restore_screening / purge_screening (returns image_path; main.py deletes
  the file). Endpoints: GET /api/screenings/trash (registered BEFORE
  /{doc_id} — order matters), DELETE /api/screenings/{id} (to trash), POST
  /{id}/restore, DELETE /{id}/purge. Signup now: name/email/username/
  password/confirmPassword (backend double-checks match); LoginRequest uses
  `login` field (email or username). QueryRequest dropped userName (uses
  session user); /api/decision records the session user's name as officer.
  Frontend: officer screen has Existing/New tabs (switchOfficerTab +
  signupOfficer); user signup has CREATE USER ID + CONFIRM PASSWORD fields;
  dashboard rows have Delete buttons; new Trash view (nav + view + loadTrash
  with Restore/Delete-forever). GOTCHA: cmd.exe `set /p` doesn't expand
  %VAR% in the same chained line — hardcode IDs when curl-testing.
  Verified end-to-end: signup+confirm-mismatch 400, username login, empty
  new-account dashboard, screen→delete→trash→restore→purge all 200.
- 2026-08-28 — **Images → Neon + profile pictures:** new `images` table
  (BYTEA: id, owner_user_id, kind, data, mime, created_at); additive columns
  profile_image_id (users) + image_id (screenings) via ALTER ... IF NOT
  EXISTS (idempotent). storage: insert_image/get_image/delete_image/
  set_profile_picture/get_profile_picture_id; insert_screening now takes
  image_id; _row_to_payload exposes imageId; purge returns image_id.
  main.py: /api/screen writes doc+face to TEMP files for the AI modules,
  unlinks them in finally, stores bytes via insert_image; image endpoint
  returns Response(bytes, media_type) from Neon; POST+GET /api/profile-picture
  (5MB cap, image/* check, replaces old image). _save_upload/UPLOADS_DIR
  removed. Frontend: avatars clickable (changeProfilePicture → file picker →
  handleProfilePictureSelect → POST → refresh /me → displayProfilePicture;
  img cached with ?v=profileImageId). /me + login responses include
  profileImageId. Old local uploads deleted; backend/uploads now empty
  (legacy). Verified: profile pic upload→fetch round-trip (2.2MB), screening
  image served from Neon (72KB jpeg), no new local files created.
- 2026-08-28 — **Profile page + uniqueness errors:** new view-profile (HTML
  card: big avatar, pf-name/pf-email/pf-username[disabled], save button,
  pf-error/pf-saved notes); loadProfile/saveProfile JS; goTo('profile')
  hook. Identity chips clickable (chip → profile page; avatar inside still
  swaps picture via stopPropagation). displayProfilePicture now renders
  initials fallback + syncs the profile-page avatar. Backend: PUT /api/profile
  + storage.update_user_profile (returns True/'email'/False); signup
  pre-checks get_user_by_username → specific "user ID already taken" 409,
  email → specific 409. Verified: update round-trip, login with new email
  works, duplicate-username specific error, demo account restored.
- 2026-08-28 — **Secure image deletion + password toggles:** /api/screen
  now analyzes via temp files (deleted in finally) and stores NOTHING —
  imageDeleted:true flag added to payload; insert_image call removed.
  Processing view: secure-delete-banner (shred-doc w/ 5 staggered falling
  lines → checkPop ✓ → typewriter sd-cheers 'Cheers! Your data is safely
  deleted' → fadeUp sub-note); showSecureDeleteBanner() re-clones the node
  so CSS animations replay every screening; resetPipeline hides it. Result
  view: doc-deleted-note placeholder (🗑️ 'Image securely deleted after
  analysis') when imageDeleted. Log line 'uploaded image securely deleted'
  added. Password toggles: togglePassword(btn,input) 🐈→🙈/👁 + .pw-field/
  .pw-toggle CSS on ul-password, su-password, su-confirm, of-password,
  ofsu-password, ofsu-confirm. Cleaned: DELETE FROM images WHERE
  kind='document' (2 rows) + screenings.image_id=NULL. Verified: screen →
  imageDeleted true, image endpoint 404, 0 document images in Neon.
- 2026-08-28 — **Processing view redesign + Neon pool fix:** rewrote
  view-processing (split layout: stepper left / log top-right / shred
  bottom-right; progress bar w/ % + label + error state; wait-title with
  spinner → "Analysis complete"). Replaced .pnode/.connector/.triobranch
  CSS with .pstep stepper (marker ✓/active-pulse/skipped-dashed); JS
  markPipelineStep(activeIndex), markPipelineComplete (face step skipped
  when no face), setProgress, setProcTitle. NEON FIX: pool
  check=check_connection + max_lifetime=240 (stale SSL after compute
  suspend caused 500s — verified fixed, login+screen 200 after restart).
- 2026-08-28 — **India Edition:** indian_docs.py (Verhoeff verified vs
  canonical test vector 2363; PAN rules from ITD structure); OCR Indian
  detection (markers + regex + label extraction — gotchas: isalpha() fails
  on spaces; label must be exact-line or 'LABEL value' to avoid substring
  collisions); validation branches + CRITICAL_LABELS extended (Aadhaar
  checksum, PAN structure); watchlist table/endpoints/UI/match (+80 pts,
  ⛔ reason, fail flag); 5 Indian specimen samples; Hindi toggle (I18N +
  applyLanguage + sidebar/login buttons). All verified via API: clean
  Aadhaar+watchlist → 80 HIGH; tampered → 100 HIGH; PAN mismatch → 88 HIGH.

## 🏁 PROJECT COMPLETE — demo cheat sheet
| Upload (backend\samples\) | Expected outcome |
|---|---|
| `passport_clean.jpg` | **0 LOW** — genuine document |
| `passport_india.jpg` | **0 LOW** — Indian passport, tricolor header |
| `aadhaar_clean.jpg` | **0 LOW** — Verhoeff checksum passes |
| `pan_clean.jpg` | **8 LOW/MED review** — PAN structure + surname match |
| `visa_specimen.jpg` | **43 MED** — no MRZ, honest review |
| `passport_expired.jpg` | **72 HIGH** — expiry rule |
| `passport_badchecksum.jpg` | **72 HIGH** — MRZ checksum fraud |
| `passport_tampered.jpg` | **74 HIGH** — EXIF + ELA forensics |
| `aadhaar_tampered.jpg` | **100 HIGH** — Verhoeff FAIL + GIMP tag |
| `pan_mismatch.jpg` | **88 HIGH** — surname initial ≠ 5th char |
| any doc + watchlist entry | **+80 → HIGH** — ⛔ WATCHLIST MATCH |
| faces: doc `img1.jpg` + face `img2.jpg` | face ~71% verified |
| faces: doc `img1.jpg` + face `img13.jpg` | **50 pts** → identity mismatch |

## 🔒 Locked decisions (from user, 2026-08-27)
1. **Backend/AI language:** Python + FastAPI.
2. **AI depth:** Hybrid — real OCR, rule validation, tampering heuristics; face
   match best-effort real with documented fallback.
3. **Frontend:** keep existing vanilla HTML/CSS/JS; wire mock functions to the API.
4. **Timeline:** **1 day.** Time-box everything; protect the end-to-end demo.
5. Serve frontend from FastAPI (same origin) to avoid CORS.
6. Storage: SQLite (`screenings.db`), local only. PII stays on the machine.

## 🧠 Key facts a fresh session needs
- The existing UI already has ALL the screens (officer dashboard/upload/
  processing/result/investigation + user portal + login/liveness). We are
  **wiring**, not designing. Function names in `app.js` map to `onclick=` in
  `index.html` — keep them or update both.
- API contract + folder layout are defined in [architecture.md](architecture.md)
  §5 and §3. Return dict keys must match what `app.js` renders.
- Design tokens are in [design.md](design.md) / `style.css` `:root` — reuse them.
- Riskiest task: installing face libs on Windows. Fallback ladder in
  [architecture.md](architecture.md) §7. Hard-stop at ~20 min → OpenCV heuristic.
- Recommended Python: 3.10 / 3.11 for best wheel availability.

## 📁 Files
- `index.html` / `style.css` / `app.js` — frontend, **WIRED to the real API as
  of Phase 1** (upload → `/api/screen` → Result view renders real payload).
  Dashboard/Investigation still show mock data (Phase 6 wires them).
- `prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, `memory.md` — docs.
- `backend/main.py` — FastAPI: static serving (no-cache) + `/api/health` +
  `/api/screen` (**real OCR wired**, Phase 2) + `/api/screenings`. Active
  work file for Phases 3-6 (add validation/tampering/face/risk to
  `_build_payload`).
- `backend/storage.py` — SQLite layer, working (Phase 1).
- `backend/services/ocr.py` + `validation.py` + `tampering.py` + `face.py`
  — **ALL real, working** (Phases 2-5). `backend/risk.py` — **real weighted
  engine** (Phase 6), used by main.py `_build_payload`.
- `backend/samples/faces/` — deepface test faces (img1/img2/img11 same
  person; img13 different). Used as doc+face upload pair for face tests.
- `backend/samples/` — generator + 3 specimen images (clean/expired/tampered).
- `backend/uploads/` — received document images (DOC-88233.jpg, DOC-88234.jpg from tests).
- `screenings.db` — SQLite DB at project root (has 2 real test rows).
- `.venv/` — Python 3.13 virtualenv with all Phase 0 deps installed.
- `.gitignore` — venv, uploads, db, pycache.
- `files needed to create before making a website.txt` — original brief.

## ⚠️ Open questions / assumptions to confirm with user
- Auth: assumed **mocked** for the demo (no real password hashing/JWT) unless asked.
- Sample document images: **resolved** — 3 synthetic specimen passports generated
  in `backend/samples/` (clean / expired / tampered). Swap in real specimen
  scans later only if user prefers (synthetics have no PII → privacy-safe).
- Whether other doc types (visa, licence, permit) need real OCR or passport-only
  is enough for the demo (currently: passport-first, others best-effort).

## 📝 Change log
- 2026-08-27 — Created the 6 planning docs; recorded locked decisions from Q&A.
- 2026-08-27 — **Phase 0 done:** venv (Py 3.13) + all deps incl. EasyOCR/torch;
  `backend/` skeleton with FastAPI serving the existing UI; `/api/health` OK
  (smoke-tested on :8901, server stopped after); 3 synthetic passport samples
  generated with valid MRZ + one EXIF-tampered variant. Frontend untouched.
- 2026-08-27 — **Phase 1 done:** vertical slice live — `POST /api/screen`
  (stub analysis, contract shape, persists to SQLite) + `GET /api/screenings`;
  frontend wired (file pickers, real fetch, Result view renders payload:
  fields/flags/gauge/reasons/face bar). Verified via curl twice (DOC-88233/34)
  + `node --check`. Server left running on :8901 for user testing.
- 2026-08-27 — **Phase 2 done:** real OCR — `services/ocr.py` (EasyOCR
  singleton + line clustering + TD3 MRZ parser + bottom-crop retry), wired
  into `/api/screen`; honest placeholders for later phases; no-cache headers
  on static files (fixed stale-JS bug user hit). Verified on all 3 samples
  via module tests + API POSTs (DOC-88235/36). Weights cached in ~/.EasyOCR.
  User browser-tested the upload flow OK before Phase 2 started.
- 2026-08-27 — **Phase 3 done:** real validation — `services/validation.py`
  (5 ICAO check digits, expiry/DOB logic, format rules) wired into
  `/api/screen` with interim risk scoring (fail→72 HIGH / review→45 MED /
  pass→10 LOW). Added 4th sample (badchecksum). Verified: clean→LOW 10,
  expired→HIGH 72 "EXPIRED 2019", badchecksum→HIGH 72 checksum mismatch.
- 2026-08-27 — **Phase 4 done:** real tampering detection —
  `services/tampering.py` (EXIF editor tags + ELA q90 re-save grid z-score +
  Laplacian noise consistency), empirically calibrated (clean 6.6σ vs
  tampered 139.5σ → thresholds 12/25). Wired into `/api/screen`; interim
  HIGH→78. Verified: tampered→78 HIGH (Photoshop EXIF + ELA localized),
  clean→10 LOW.
- 2026-08-27 — **Phase 5 done:** real face verification — deepface/Facenet +
  mtcnn detector (after face_recognition/dlib failed on py3.13 and OpenCV 5
  killed the 'opencv' backend). Installed tf-keras; deepface test faces in
  samples/faces. Verified: same person → match .714 verified True;
  different → 0.0 verified False → 75 HIGH impersonation path. Face-enabled
  screenings ~20-35s (vs ~5.5s without face).
- 2026-08-27 — **Phase 6 done:** real risk engine (weighted: critical fail
  72 / tamper 40×signal / face mismatch 50 / no-MRZ 35 etc.), `POST
  /api/decision` + `GET /api/screenings/{id}`, Dashboard + Investigation
  views live from DB (mock rows removed). Verified: clean 0 LOW, expired 72,
  tampered 74, badchecksum 72; decision deny round-trips; feed 26 records.
- 2026-08-28 — **Phase 7 done (PROJECT COMPLETE):** honest processing
  animation + completion summary + error back-button; document image shown
  in Result view (`GET /api/screenings/{id}/image`); 5th sample visa→43 MED
  (fixed non-MRZ grid false positives: ELA/noise grids skip on non-passport
  layouts, honest skip note); `backend/purge.py` PII wipe; `demo-script.md`;
  requirements.txt finalized. All tiers verified via API.

---
### How to update this file
After each step, edit: **CURRENT STATUS** (phase + current file + next action),
tick **Done**, and add a dated **Change log** line. Keep it short and current —
this is the first thing a fresh session should read.

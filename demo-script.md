# SENTRY — Demo Script

**Project:** AI-Based Fake Identity & Document Screening System (SIH)
**Setup:** start the server (see below), open http://127.0.0.1:8901, hard-refresh
(Ctrl+F5). Pre-warm: upload `passport_clean.jpg` once **before** the demo so the
OCR/face models are loaded in memory (first screening after a server start takes
~15-20s; later ones ~5s).

```
"C:\Users\spaul\Desktop\sih\website contents all\.venv\Scripts\python.exe" -m uvicorn main:app --port 8901 --app-dir "C:\Users\spaul\Desktop\sih\website contents all\backend"
```

Sample files live in `backend\samples\`. All are synthetic specimens — no real PII.

**Demo accounts:** Officer `kessler` / `sentry-officer-2026` · User `jordan` / `sentry-user-2026`

---

## Opening line (10 s)
> "SENTRY cuts document verification from minutes to seconds — built for Indian
> checkpoints. It reads passports, Aadhaar and PAN cards, verifies them against
> real government checksum algorithms, runs pixel-level forensics, checks faces,
> and cross-references a watchlist — producing an explainable risk score. The
> officer stays in command: the AI only recommends."

Log in as **Officer** (`kessler` / `sentry-officer-2026`).

## Case 1 — Genuine Indian passport → LOW (~15 s)
1. **New Screening** → upload `passport_india.jpg` → **Begin analysis**.
2. Watch the redesigned Processing view: progress bar, 7-step pipeline,
   engine log — then the **shred animation: "Cheers! Your data is safely deleted"**.
3. **Result**: score **0 LOW**, real extracted fields. Point out the
   "Image securely deleted" placeholder — the upload never touches storage.

## Case 2 — Aadhaar: real Indian validation (~15 s)
1. Upload `aadhaar_clean.jpg` → **Result**: **LOW** — "Verhoeff checksum valid
   (UIDAI standard)". Explain: the SAME math UIDAI uses — a forged number
   fails instantly.
2. Upload `aadhaar_tampered.jpg` → **100 HIGH**: "Verhoeff checksum FAILED —
   this number was not issued by UIDAI" + GIMP editing tag in EXIF.
   One digit changed → caught twice.

## Case 3 — PAN: the surname rule (~15 s)
1. Upload `pan_clean.jpg` → structure valid, holder type P = Individual,
   surname initial matches the PAN's 5th character → LOW.
2. Upload `pan_mismatch.jpg` → **88 HIGH** — the 5th character says 'R' but
   the holder's surname starts with 'K' → impersonation flag.

## Case 4 — Passport forensics (~15 s)
1. `passport_tampered.jpg` → **74 HIGH**: Photoshop EXIF tag + Error-Level
   Analysis located the edited region (139.5σ deviation).
2. Optional: `passport_expired.jpg` → 72 HIGH (expiry rule);
   `passport_badchecksum.jpg` → ICAO 9303 checksum fraud.

## Case 5 — Watchlist: the database cross-check (~20 s)
1. **Investigation** view → Watchlist panel → add `234567890124` /
   "Arjun Kumar" / reason "Duplicate identity".
2. Upload `aadhaar_clean.jpg` again — now **80 HIGH** with a red ⛔
   WATCHLIST MATCH reason. A perfectly valid document, still flagged —
   because the *person* is on the list.
3. Remove the entry from the watchlist to reset.

## Case 6 — Face verification (~30 s, slower)
1. Document: `samples\faces\img1.jpg` + face: `img2.jpg` → verified ~71%.
2. Repeat with `img13.jpg` → **identity mismatch** → HIGH.
3. Or use the **📷 camera** — live capture with liveness (hold a printed
   photo perfectly still → "printed photograph suspected").

## Close the loop (~30 s)
1. **Dashboard** — per-account live stats/feed/escalation queue.
2. Click a HIGH row → **Investigation** timeline (real case evidence).
3. **Delete** a record → **Trash** → restore it (accidental-delete safety).
4. Click your name → **Profile** (edit name/email, picture).
5. **हिं / EN toggle** — the console speaks Hindi.
6. **User portal** (log out → User login): travelers submit documents with
   the same AI; every output carries the "advisory only" disclaimer.
7. Data + accounts live in a **Neon cloud database**; uploaded images are
   **never stored** — shredded after analysis (the animation you saw).

---

## Honesty notes (if judges ask)
- Face match = deepface/Facenet embeddings; liveness = simplified single-face +
  motion check (labeled "simplified") — real PAD is future work.
- Tampering = heuristics (EXIF + ELA + noise), calibrated on samples, not a
  trained forgery model.
- Aadhaar Verhoeff + PAN structure + ICAO MRZ checksums are the REAL government
  algorithms — judges can verify the math independently.
- Risk score is a transparent weighted sum — every point maps to a listed reason.
- All sample documents are synthetic specimens ("Republic of Indica") — no real PII.
- Auth is real (PBKDF2-hashed passwords, session cookies) but single-tenant demo.

## Timings to expect
- Screening without face: ~5 s (after warm-up).
- Screening with face: ~20-35 s (first one slower).
- First screening after server start: ~15-20 s extra (model load).
- Neon idles asleep? First request self-heals (pool check) — just retry once.

# prd.md — Project Requirements Document

**Project:** SENTRY — AI-Based Fake Identity & Document Screening System
**Event:** Smart India Hackathon
**Last updated:** 2026-08-27
**Build window:** 1 day (see [phases.md](phases.md))

---

## 1. One-line summary
An AI-assisted platform that screens identity & travel documents at border
checkpoints — extracting data, validating it, detecting tampering, and matching
faces — then produces a **risk score that assists (never replaces) a human
officer's decision**.

## 2. Problem context
Border checkpoints process thousands of documents daily (passports, visas,
national IDs, licences, permits). Manual verification is slow, error-prone, and
misses sophisticated forgery. Common threats:
- Fake passports & visas, altered photographs, modified dates of birth
- Tampered visa stamps, identity impersonation, multiple identities per person
- Expired / blacklisted travel documents
- High passenger volume causing delays

## 3. Goals
1. Cut per-document verification from minutes to seconds.
2. Surface tampering/forgery signals a human might miss.
3. Standardize screening decisions across checkpoints via a consistent risk score.
4. Keep a digital audit trail for investigations.
5. **Keep the human officer in control** — AI output is advisory only.

## 4. Target users
| Role | Who | What they do |
|------|-----|--------------|
| **Officer** (primary) | Border security personnel | Screen documents, review AI risk output, make & record the final decision, run investigations |
| **User** (secondary) | Travelers / passengers | Self-service portal: upload a document, pass a liveness face check, submit a query to an officer |

## 5. Core features (the 4 required modules + glue)
- **Module 1 — OCR Extraction:** pull structured fields from a document image.
  - Passport: Name, Passport No., Nationality, DOB, Date of expiry, Gender.
  - Visa: Visa No., Visa Type, Entry validation, Stay duration.
  - Also: National ID, Driving licence, Permit.
- **Module 2 — Document Validation:** check extracted data against official
  rules — MRZ checksum, date logic (DOB < expiry, not expired), field formats,
  age sanity, issuing-authority format.
- **Module 3 — Tampering Detection (core innovation):** photo replacement,
  text manipulation, stamp forgery, image-metadata analysis (see
  [architecture.md](architecture.md) for the hybrid approach).
- **Module 4 — Face Verification:** confirm the document photo matches the live
  face; includes a liveness / presentation-attack (PAD) check.
- **Risk Engine:** combine module outputs into a 0–100 score + LOW/MED/HIGH tier
  with human-readable reasons.
- **Officer decision & audit:** Approve / Escalate / Deny, explicitly confirmed
  by the officer, written to a timeline/audit log.
- **Investigation view:** case timeline, related identities, officer notes.
- **User portal:** upload + verification checks + submit-to-officer flow.

## 6. Functional requirements (for the 1-day build)
Must-have (demo-critical):
- FR1 Upload a document image via the existing UI and receive real results.
- FR2 Real OCR returns extracted fields shown in the Result view.
- FR3 Rule-based validation produces pass/fail flags.
- FR4 Tampering heuristics (metadata + Error-Level-Analysis + noise) produce flags.
- FR5 Risk engine returns score + tier + reasons, rendered in the gauge.
- FR6 Officer can select and **confirm** a final decision; it is recorded.

Should-have:
- FR7 Real face match between an uploaded selfie/live capture and the doc photo.
- FR8 User liveness/PAD screen backed by a real (even if basic) check.
- FR9 Results persisted so the dashboard/investigation show real records.

Nice-to-have (only if time remains):
- FR10 Multi-identity / related-identity lookup.
- FR11 Watchlist/blacklist check against a seeded list.

## 7. Non-functional requirements
- **Advisory-only AI:** the system never auto-denies; it recommends. A human
  must confirm. This is a hard product principle (see [rules.md](rules.md)).
- **Speed:** a single screening should feel near-instant in the demo (< ~5 s).
- **Privacy:** documents are sensitive PII — store locally, do not send to
  third-party cloud services in the demo build; allow easy purge.
- **Explainability:** every risk score must list the reasons that produced it.
- **Runs locally on Windows** for the demo, single machine, no internet reliance
  for core screening.

## 8. Explicitly out of scope (1-day build)
- Training custom deep-learning forgery models from scratch.
- Real government database integration.
- Production auth (real password hashing/JWT is a stretch goal, not required).
- Mobile apps, multi-checkpoint sync, horizontal scaling.

## 9. Success criteria / demo script
A judge can: log in as an officer → start a new screening → upload a sample
passport image → watch the pipeline run → see **real extracted fields, real
validation flags, real tampering signals, a computed risk score with reasons**
→ officer confirms a decision → it appears in the dashboard/investigation trail.
Then: log in as a user → upload a doc → pass verification checks → submit to officer.

## 10. Key decisions (locked)
- Backend/AI language: **Python + FastAPI**.
- AI depth: **hybrid** — real OCR, rule validation, tampering heuristics; face
  match best-effort real with a documented fallback.
- Frontend: **keep existing vanilla HTML/CSS/JS**, wire mock functions to the API.
- Timeline: **1 day** — every module is time-boxed with a fallback.

See [architecture.md](architecture.md) for how, [phases.md](phases.md) for when,
[rules.md](rules.md) for constraints, and [memory.md](memory.md) for live status.

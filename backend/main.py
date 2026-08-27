"""SENTRY backend — FastAPI app.

Serves the existing frontend (index.html / style.css / app.js) from the parent
folder — same origin, so no CORS — and exposes the screening API. The AI
modules live in services/ and are wired in progressively (see phases.md).
"""
import os
import re
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Cookie, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import storage
from risk import score as risk_score
from services import auth as auth_service
from services import face as face_service
from services import ocr, tampering, validation

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent

storage.init_db()
_seed_users = {
    # demo accounts created on first boot (passwords are hashed at runtime)
    "officer@checkpoint04.gov": ("kessler", "R. Kessler", "officer", None, "sentry-officer-2026"),
    "jordan@example.com": ("jordan", "Jordan Lee", "user", "C40217755", "sentry-user-2026"),
}


def _seed_demo_users() -> None:
    for email, (username, name, role, passport, password) in _seed_users.items():
        if storage.get_user_by_login(email) is None:
            storage.create_user(
                email, username, name, auth_service.hash_password(password), role,
                passport_no=passport, created_at=datetime.now().isoformat(timespec="seconds"),
            )


_seed_demo_users()

app = FastAPI(title="SENTRY — Document Screening API", version="0.3.0")

# Download/init EasyOCR weights off the request path (first run downloads
# ~100MB; afterwards it is a quick local load).
threading.Thread(target=ocr.prewarm, daemon=True).start()


@app.get("/api/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "service": "sentry-backend"}


# ------------------------------------------------------------------- auth
SESSION_COOKIE = "sentry_session"
SESSION_DAYS = 7


def _current_user(session: str | None) -> dict | None:
    if not session:
        return None
    return storage.get_session_user(session)


def _session_response(user: dict, status_code: int = 200) -> JSONResponse:
    token = auth_service.new_session_token()
    expires = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    storage.create_session(token, user["id"], expires)
    response = JSONResponse({
        "user": {k: user[k] for k in ("id", "email", "username", "name", "role", "passportNo", "profileImageId")},
        "role": user["role"],
    }, status_code=status_code)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400,
        httponly=True, samesite="lax",
    )
    return response


def _require_user(session: str | None) -> dict:
    user = _current_user(session)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user


class SignupRequest(BaseModel):
    name: str
    email: str
    username: str
    password: str
    confirmPassword: str = ""  # frontend also checks; backend double-guards
    passportNo: str | None = None
    role: str = "user"


class LoginRequest(BaseModel):
    login: str  # email OR username
    password: str
    role: str | None = None  # optional guard: reject if it doesn't match


@app.post("/api/auth/signup")
def signup(request: SignupRequest) -> JSONResponse:
    email = request.email.strip().lower()
    username = request.username.strip().lower()
    if "@" not in email or not username or not username.replace("_", "").replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Enter a valid email and a user ID (letters, numbers, . _ -).")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if request.confirmPassword != request.password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
    if request.role not in ("user", "officer"):
        raise HTTPException(status_code=400, detail="Invalid role.")
    if storage.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail=f"The user ID '{username}' is already taken.")
    if storage.get_user_by_login(email) is not None:
        raise HTTPException(status_code=409, detail="That email is already registered.")
    user_id = storage.create_user(
        email, username, request.name.strip() or "Unnamed", auth_service.hash_password(request.password),
        request.role, passport_no=(request.passportNo or None) or None,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    if user_id is None:
        raise HTTPException(status_code=409, detail="That email or user ID is already registered.")
    user = storage.get_user_by_login(email)
    return _session_response(user, status_code=201)


@app.post("/api/auth/login")
def login(request: LoginRequest) -> JSONResponse:
    login_value = request.login.strip()
    user = storage.get_user_by_login(login_value)
    stored = storage.get_password_hash(login_value) if user is not None else None
    if user is None or stored is None or not auth_service.verify_password(request.password, stored):
        raise HTTPException(status_code=401, detail="Invalid user ID/email or password.")
    if request.role and request.role != user["role"]:
        raise HTTPException(status_code=403, detail=f"This account is not registered as {request.role}.")
    return _session_response(user)


@app.post("/api/auth/logout")
def logout(session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> JSONResponse:
    if session:
        storage.delete_session(session)
    response = JSONResponse({"loggedOut": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/auth/me")
def me(session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    user = _current_user(session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return {"user": {k: user[k] for k in ("id", "email", "username", "name", "role", "passportNo", "profileImageId")}}


@app.get("/api/screenings")
def list_screenings(limit: int = 50, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> list[dict]:
    """The logged-in account's screenings, newest first (per-account history)."""
    user = _require_user(session)
    return storage.list_screenings(user["id"], limit=limit)


@app.get("/api/screenings/trash")
def list_trash(session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> list[dict]:
    """Soft-deleted screenings — recoverable from the trash bin."""
    user = _require_user(session)
    return storage.list_screenings(user["id"], limit=100, trashed=True)


@app.delete("/api/screenings/{doc_id}")
def delete_screening(doc_id: str, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """Move a screening to the trash bin (recoverable)."""
    user = _require_user(session)
    if not storage.soft_delete_screening(doc_id, user["id"]):
        raise HTTPException(status_code=404, detail=f"Screening {doc_id} not found (or already deleted).")
    return {"id": doc_id, "deleted": True}


@app.post("/api/screenings/{doc_id}/restore")
def restore_screening(doc_id: str, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """Recover a screening from the trash bin."""
    user = _require_user(session)
    if not storage.restore_screening(doc_id, user["id"]):
        raise HTTPException(status_code=404, detail=f"Screening {doc_id} not found.")
    return {"id": doc_id, "restored": True}


@app.delete("/api/screenings/{doc_id}/purge")
def purge_screening(doc_id: str, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """Permanently delete a trashed screening (also removes its image from Neon)."""
    user = _require_user(session)
    image_id = storage.purge_screening(doc_id, user["id"])
    if image_id is None:
        raise HTTPException(status_code=404, detail=f"Screening {doc_id} not found.")
    if image_id:
        storage.delete_image(image_id)
    return {"id": doc_id, "purged": True}


class QueryRequest(BaseModel):
    queryText: str | None = None
    screeningId: str | None = None


@app.post("/api/query")
def submit_query(request: QueryRequest, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """User portal: submit a query package (with an optional screening id)
    to the officer queue."""
    user = _require_user(session)
    query_id = storage.next_query_id()
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        storage.insert_query(query_id, user["id"], user["name"], request.queryText,
                             request.screeningId, created_at)
    except Exception as exc:
        print(f"[storage] query persist failed: {exc}")
        raise HTTPException(status_code=500, detail="Query could not be saved.")
    return {"id": query_id, "status": "pending", "recorded": True,
            "createdAt": created_at}


@app.get("/api/queries")
def list_queries(limit: int = 20, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> list[dict]:
    """User portal: the logged-in account's submitted queries."""
    user = _require_user(session)
    return storage.list_queries(user["id"], limit=limit)


@app.get("/api/screenings/{doc_id}")
def get_screening(doc_id: str, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    user = _require_user(session)
    screening = storage.get_screening(doc_id, owner_user_id=user["id"])
    if screening is None:
        raise HTTPException(status_code=404, detail=f"Screening {doc_id} not found.")
    return screening


@app.get("/api/screenings/{doc_id}/image")
def get_screening_image(doc_id: str, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> Response:
    """Serve the stored document image (from the Neon images table)."""
    user = _require_user(session)
    screening = storage.get_screening(doc_id, owner_user_id=user["id"])
    if screening is None or not screening.get("imageId"):
        raise HTTPException(status_code=404, detail=f"No image for {doc_id}.")
    image = storage.get_image(screening["imageId"])
    if image is None:
        raise HTTPException(status_code=404, detail="Stored image missing.")
    return Response(content=image["data"], media_type=image["mime"] or "image/jpeg")


# ------------------------------------------------------- profile pictures
@app.post("/api/profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict:
    """Store (or replace) the logged-in account's profile picture in Neon."""
    user = _require_user(session)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5 MB).")
    mime = file.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")
    old_id = storage.get_profile_picture_id(user["id"])
    image_id = storage.insert_image(user["id"], "profile", data, mime)
    storage.set_profile_picture(user["id"], image_id)
    if old_id and old_id != image_id:
        storage.delete_image(old_id)
    return {"profileImageId": image_id, "updated": True}


@app.get("/api/profile-picture")
def get_profile_picture(session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> Response:
    """Serve the logged-in account's profile picture."""
    user = _require_user(session)
    image_id = user.get("profileImageId")
    if not image_id:
        raise HTTPException(status_code=404, detail="No profile picture set.")
    image = storage.get_image(image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Stored image missing.")
    return Response(content=image["data"], media_type=image["mime"] or "image/jpeg")


class ProfileUpdateRequest(BaseModel):
    name: str
    email: str


@app.put("/api/profile")
def update_profile(request: ProfileUpdateRequest, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """Edit the logged-in account's name and email (user ID is permanent)."""
    user = _require_user(session)
    name = request.name.strip()
    email = request.email.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty.")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    result = storage.update_user_profile(user["id"], name, email)
    if result == "email":
        raise HTTPException(status_code=409, detail="That email is already registered to another account.")
    if result is False:
        raise HTTPException(status_code=404, detail="Account not found.")
    updated = storage.get_user_by_login(email)
    return {
        "user": {k: updated[k] for k in ("id", "email", "username", "name", "role", "passportNo", "profileImageId")},
        "updated": True,
    }


class WatchlistRequest(BaseModel):
    docNumber: str
    personName: str | None = None
    reason: str | None = None
    severity: str = "high"


@app.get("/api/watchlist")
def get_watchlist(session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> list[dict]:
    """List watchlist entries (officer-managed blacklist)."""
    _require_user(session)
    return storage.list_watchlist()


@app.post("/api/watchlist")
def add_to_watchlist(request: WatchlistRequest, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """Add a document number / person to the watchlist."""
    user = _require_user(session)
    doc_number = request.docNumber.strip()
    if not doc_number:
        raise HTTPException(status_code=400, detail="Document number is required.")
    entry_id = storage.add_watchlist_entry(
        doc_number, request.personName, request.reason, request.severity,
        added_by=user["name"], created_at=datetime.now().isoformat(timespec="seconds"),
    )
    return {"id": entry_id, "added": True}


@app.delete("/api/watchlist/{entry_id}")
def remove_from_watchlist(entry_id: int, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """Remove a watchlist entry."""
    _require_user(session)
    if not storage.remove_watchlist_entry(entry_id):
        raise HTTPException(status_code=404, detail="Entry not found.")
    return {"id": entry_id, "removed": True}


class DecisionRequest(BaseModel):
    id: str
    decision: str  # approve | escalate | deny
    officer: str = "R. Kessler"
    note: str | None = None


@app.post("/api/decision")
def record_decision(request: DecisionRequest, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    """Record the officer's explicitly confirmed final decision (audit trail)."""
    user = _require_user(session)
    if request.decision not in ("approve", "escalate", "deny"):
        raise HTTPException(
            status_code=400,
            detail="decision must be one of: approve, escalate, deny",
        )
    officer_name = user["name"] if user["role"] == "officer" else request.officer
    if not storage.record_decision(request.id, request.decision, officer_name, request.note):
        raise HTTPException(status_code=404, detail=f"Screening {request.id} not found.")
    return {
        "id": request.id,
        "decision": request.decision,
        "officer": officer_name,
        "recorded": True,
    }


@app.post("/api/liveness")
async def liveness(frames: list[UploadFile] = File(...)) -> dict:
    """Presentation-attack check on a burst of camera frames (live capture)."""
    if len(frames) < 3:
        raise HTTPException(
            status_code=400, detail="Need at least 3 frames for the liveness check."
        )
    tmp_paths: list[str] = []
    try:
        for frame in frames:
            data = await frame.read()
            if not data:
                continue
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=_safe_suffix(frame.filename)
            ) as tmp:
                tmp.write(data)
                tmp_paths.append(tmp.name)
        if len(tmp_paths) < 3:
            raise HTTPException(status_code=400, detail="Empty frames received.")
        return face_service.liveness(tmp_paths)
    finally:
        for path in tmp_paths:
            try:
                os.unlink(path)
            except OSError:
                pass


@app.post("/api/screen")
async def screen(
    document: UploadFile = File(...), face: UploadFile | None = File(None),
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict:
    """Receive a document image (multipart), run all four AI modules, persist
    the result + image under the logged-in account, return the §5 payload."""
    user = _require_user(session)
    doc_bytes = await document.read()
    if not doc_bytes:
        raise HTTPException(status_code=400, detail="Uploaded document is empty.")

    doc_id = storage.next_doc_id()

    # AI modules need a real file path — use a temp file, deleted right
    # after analysis. The image itself is NEVER stored anywhere.
    tmp_doc_path: str | None = None
    tmp_face_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=_safe_suffix(document.filename)
        ) as tmp:
            tmp.write(doc_bytes)
            tmp_doc_path = tmp.name

        face_bytes = b""
        if face is not None:
            face_bytes = await face.read()
            if face_bytes:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=_safe_suffix(face.filename)
                ) as tmp:
                    tmp.write(face_bytes)
                    tmp_face_path = tmp.name

        extraction = ocr.extract(tmp_doc_path)
        tamper = tampering.analyze(
            tmp_doc_path, mrz_found=extraction["mrz"] is not None
        )
        face_result = face_service.verify(tmp_doc_path, tmp_face_path)
    finally:
        for path in (tmp_doc_path, tmp_face_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    # watchlist cross-check (problem statement: "validate against databases")
    watchlist_match = storage.match_watchlist(
        (extraction.get("fields") or {}).get("documentNo"),
        (extraction.get("fields") or {}).get("name"),
    )
    payload = _build_payload(doc_id, extraction, tamper, face_result, watchlist_match)

    # Security policy (hackathon promise): the uploaded document image is
    # used for analysis and then PERMANENTLY deleted — nothing binary is
    # stored. Only the log-type screening record (fields, flags, risk,
    # decision) persists, and the owner can delete that too (trash bin).
    payload["imageDeleted"] = True

    warnings: list[str] = list(extraction.get("warnings", []))
    warnings += [
        f"Tampering check '{f['label']}' could not run: {f['detail']}"
        for f in tamper.get("flags", []) if f["status"] == "review" and f.get("signal") == 0.5
    ]
    try:
        storage.insert_screening(payload, image_id=None, owner_user_id=user["id"])
    except Exception as exc:  # degraded-but-valid per rules.md §5
        print(f"[storage] persist failed: {exc}")
        warnings.append("Result could not be persisted to the database.")

    payload["warnings"] = warnings
    return payload


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{2,5}", suffix) else ".jpg"


def _build_payload(doc_id: str, extraction: dict, tamper: dict, face_result: dict,
                   watchlist_match: dict | None = None) -> dict:
    """Assemble the §5 contract payload from all four real module outputs,
    with the weighted risk engine (risk.py)."""
    fields = extraction["fields"]

    validation_flags = validation.check(extraction)
    tamper_flags = tamper.get("flags", [])
    risk = risk_score(extraction, validation_flags, tamper_flags, face_result,
                      watchlist_match=watchlist_match)

    if watchlist_match:
        validation_flags.insert(0, {
            "label": "Watchlist check",
            "status": "fail",
            "detail": f"Document/person matches a watchlist entry "
                      f"({watchlist_match.get('reason') or 'flagged'}).",
        })

    return {
        "id": doc_id,
        "docType": extraction["docType"],
        "fields": fields,
        "validation": validation_flags,
        "tampering": tamper_flags,
        "face": face_result,
        "risk": risk,
        "watchlistMatch": bool(watchlist_match),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }


_NO_CACHE = {"Cache-Control": "no-cache"}  # dev: browser always revalidates


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html", headers=_NO_CACHE)


@app.get("/style.css")
def serve_style() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "style.css", headers=_NO_CACHE)


@app.get("/app.js")
def serve_app_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js", headers=_NO_CACHE)

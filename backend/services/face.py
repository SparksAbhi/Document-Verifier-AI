"""Module 4 — face verification + liveness/PAD (Phase 5).

deepface (Facenet embeddings) compares the document photo against the
uploaded live face and returns a 0-1 match score. Liveness is an honest,
simplified check for day 1: exactly one detectable face in the live image —
labeled as "simplified" in the response (rules.md §1.3: never present a
heuristic as a trained model).
"""

_MODEL = "Facenet"        # ~90MB weights; good accuracy/speed tradeoff
_DETECTOR = "mtcnn"       # works with OpenCV 5 (the 'opencv' backend does not)


def _deepface():
    from deepface import DeepFace  # heavy import — keep off module import
    return DeepFace


def count_faces(image_path: str) -> int:
    """Count detectable faces via deepface's detector backend."""
    try:
        faces = _deepface().extract_faces(
            str(image_path), detector_backend=_DETECTOR, enforce_detection=False
        )
        return len([f for f in faces if f.get("confidence", 0) > 0.5])
    except Exception:
        return 0


def verify(doc_image_path: str, face_image_path: str | None) -> dict:
    """Compare the document image's face with the live-face image.

    Returns {match, verified, liveness, detail, method}. Never raises —
    detection failures return match=None with an honest detail.
    """
    if not face_image_path:
        return {
            "match": None,
            "verified": None,
            "liveness": "na",
            "detail": "No live face provided — face check skipped.",
            "method": None,
        }

    # --- liveness (simplified): exactly one face must be present
    face_count = count_faces(face_image_path)
    if face_count == 1:
        liveness, liveness_note = "pass", "single face detected"
    elif face_count == 0:
        liveness, liveness_note = "review", "no face detected in live capture"
    else:
        liveness, liveness_note = "review", f"{face_count} faces detected in live capture"

    # --- face match via embeddings
    try:
        result = _deepface().verify(
            img1_path=str(doc_image_path),
            img2_path=str(face_image_path),
            model_name=_MODEL,
            detector_backend=_DETECTOR,
            enforce_detection=True,
        )
        distance = float(result["distance"])
        threshold = float(result["threshold"]) or 1.0
        # linear confidence: distance 0 -> 1.0, distance == threshold -> 0.5,
        # distance >= 2*threshold -> 0
        score = max(0.0, min(1.0, 1.0 - distance / (2.0 * threshold)))
        return {
            "match": round(score, 3),
            "verified": bool(result["verified"]),
            "liveness": liveness,
            "detail": (f"Facenet distance {distance:.3f} (threshold {threshold:.3f}); "
                       f"liveness: {liveness_note} (simplified check)"),
            "method": f"deepface/{_MODEL}",
        }
    except ValueError as exc:
        # deepface raises ValueError when no face can be detected
        return {
            "match": None,
            "verified": None,
            "liveness": liveness,
            "detail": f"Face match unavailable: {exc}; liveness: {liveness_note} (simplified check)",
            "method": f"deepface/{_MODEL}",
        }
    except Exception as exc:  # model/driver failure — degrade honestly
        return {
            "match": None,
            "verified": None,
            "liveness": liveness,
            "detail": f"Face engine failed: {exc}",
            "method": f"deepface/{_MODEL}",
        }


# ------------------------------------------------------------------ liveness
# thresholds on mean abs pixel diff (0-255 scale) between consecutive frames,
# measured on 64x64 grayscale — tune per camera if needed
_MOTION_FAIL = 0.8     # below: perfectly static scene -> printed-photo suspicion
_MOTION_REVIEW = 1.8   # below: unusually low motion
_MOTION_FLICKER = 30.0 # above: abnormal flicker (screen replay can trigger)


def liveness(frame_paths: list[str]) -> dict:
    """Presentation-attack check on a burst of camera frames.

    Honest, simplified PAD (labeled as such): (1) natural micro-motion
    between frames — a printed photo or idle screen is perfectly static;
    (2) exactly one face present in sampled frames; (3) no abnormal flicker.

    Returns {liveness, motionScore, checks[], method}. Never raises.
    """
    import numpy as np
    from PIL import Image

    if len(frame_paths) < 3:
        return {
            "liveness": "review", "motionScore": None,
            "checks": [{"label": "Frame burst", "status": "review",
                        "detail": f"Only {len(frame_paths)} frames received — need at least 3."}],
            "method": "motion + face-count (simplified)",
        }

    checks: list[dict] = []

    # --- motion analysis (fast, all frames)
    try:
        smalls = []
        for path in frame_paths:
            with Image.open(path) as img:
                smalls.append(np.asarray(img.convert("L").resize((64, 64)), dtype=np.float32))
        diffs = [float(np.abs(smalls[i] - smalls[i + 1]).mean())
                 for i in range(len(smalls) - 1)]
        motion = sum(diffs) / len(diffs)
    except Exception as exc:
        return {
            "liveness": "review", "motionScore": None,
            "checks": [{"label": "Motion analysis", "status": "review",
                        "detail": f"Frames could not be analyzed: {exc}"}],
            "method": "motion + face-count (simplified)",
        }

    if motion < _MOTION_FAIL:
        checks.append({"label": "Motion analysis", "status": "fail",
                       "detail": f"Scene is perfectly static (motion {motion:.2f}) — printed photograph suspected."})
    elif motion < _MOTION_REVIEW:
        checks.append({"label": "Motion analysis", "status": "review",
                       "detail": f"Very low motion ({motion:.2f}) — verify the subject is live."})
    elif motion > _MOTION_FLICKER:
        checks.append({"label": "Motion analysis", "status": "review",
                       "detail": f"Abnormal flicker ({motion:.2f}) — possible screen replay."})
    else:
        checks.append({"label": "Motion analysis", "status": "pass",
                       "detail": f"Natural micro-movement detected (motion {motion:.2f})."})

    # --- face presence (slower MTCNN — sample first & last frame only)
    for name, path in (("first", frame_paths[0]), ("last", frame_paths[-1])):
        count = count_faces(path)
        if count == 1:
            checks.append({"label": f"Face presence ({name} frame)", "status": "pass",
                           "detail": "Exactly one face detected."})
        else:
            checks.append({"label": f"Face presence ({name} frame)", "status": "review",
                           "detail": f"{count} faces detected — expected exactly one."})

    statuses = [c["status"] for c in checks]
    overall = "fail" if "fail" in statuses else ("review" if "review" in statuses else "pass")
    return {
        "liveness": overall,
        "motionScore": round(motion, 2),
        "checks": checks,
        "method": "motion + face-count (simplified)",
    }

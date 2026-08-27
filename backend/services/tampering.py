"""Module 3 — tampering detection (Phase 4).

Real heuristics, each honestly labeled:
1. EXIF/metadata — editor-software tags (Photoshop, GIMP, ...) are strong
   forgery indicators on document scans.
2. ELA (Error-Level Analysis) — re-save the JPEG at a known quality and diff;
   regions edited after the original save show different error levels. Grid
   cells are scored with robust z-scores (median + MAD).
3. Noise/edge consistency — Laplacian variance per grid cell; pasted/patched
   regions often differ in local sharpness.

Each check emits {label, status, detail, signal} with signal in 0-1.
"""
import io
import re
from pathlib import Path

import numpy as np
from PIL import Image

_EDITOR_PATTERN = re.compile(
    r"photoshop|gimp|lightroom|paint\.net|affinity|canva|pixlr|snapseed"
    r"|paintbrush|fotor|befunky|picmonkey|photoscape", re.IGNORECASE)

_ELA_QUALITY = 90
_GRID = (10, 7)  # cols x rows

# thresholds (tuned empirically on the sample set — see memory.md)
# clean sample max ELA z ≈ 6.6, tampered ≈ 139 → wide margin at 12/25
_ELA_REVIEW_Z = 12.0
_ELA_FAIL_Z = 25.0
_NOISE_REVIEW_Z = 8.0
_NOISE_FAIL_Z = 12.0


def analyze(image_path: str, mrz_found: bool = True) -> dict:
    """Single entry point: run all tampering heuristics on an image file.

    `mrz_found`: whether OCR located a passport MRZ. The ELA/noise grid
    checks are calibrated for passport data-page layouts; on other layouts
    (e.g. visa header bands, blank regions) they produce false positives,
    so they are skipped with an honest note. EXIF metadata always runs.

    Returns {"flags": [{label, status, detail, signal}], "maxSignal": float}.
    Never raises — unreadable images degrade to a review flag (rules.md §5).
    """
    result: dict = {"flags": [], "maxSignal": 0.0}
    try:
        path = Path(image_path)
        with Image.open(path) as img:
            img.load()
            fmt = img.format
            exif = img.getexif()
            software = exif.get(305)  # EXIF Software tag
            rgb = img.convert("RGB")
    except Exception as exc:
        result["flags"].append({
            "label": "Image analysis", "status": "review",
            "detail": f"Image could not be opened: {exc}", "signal": 0.5,
        })
        result["maxSignal"] = 0.5
        return result

    result["flags"].append(_metadata_flag(software))
    if mrz_found:
        result["flags"].append(_ela_flag(rgb, is_jpeg=(fmt == "JPEG")))
        result["flags"].append(_noise_flag(rgb))
    else:
        result["flags"].append({
            "label": "Pixel-grid forensics",
            "status": "pass",
            "detail": ("Skipped — ELA/noise grid calibration is specific to "
                       "passport data-page layouts; other document types are "
                       "referred to manual review (metadata check still ran)."),
            "signal": 0.0,
        })
    result["maxSignal"] = max(f.get("signal") or 0.0 for f in result["flags"])
    return result


def _metadata_flag(software) -> dict:
    if software and _EDITOR_PATTERN.search(str(software)):
        return {
            "label": "Image metadata (EXIF)",
            "status": "fail",
            "detail": (f"Editing-software tag present: '{software}'. "
                       "A document scan should not carry image-editor metadata."),
            "signal": 0.85,
        }
    if software:
        return {
            "label": "Image metadata (EXIF)",
            "status": "pass",
            "detail": f"Software tag '{software}' is not a known image editor.",
            "signal": 0.1,
        }
    return {
        "label": "Image metadata (EXIF)",
        "status": "pass",
        "detail": "No editor-software tags in metadata.",
        "signal": 0.05,
    }


# --------------------------------------------------------------------- ELA
def _ela_diff(rgb: Image, is_jpeg: bool) -> np.ndarray:
    """Error-level map: |original - re-save(q90)| per pixel (grayscale)."""
    base_img = rgb if is_jpeg else _resave(rgb)
    base = np.asarray(base_img, dtype=np.float32)
    resaved = np.asarray(_resave(base_img), dtype=np.float32)
    return np.abs(base - resaved).mean(axis=2)


def _resave(img: Image) -> Image:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=_ELA_QUALITY)
    buf.seek(0)
    with Image.open(buf) as reopened:
        return reopened.copy()


def _ela_flag(rgb: Image, is_jpeg: bool) -> dict:
    diff = _ela_diff(rgb, is_jpeg)
    max_z, (row, col) = _grid_max_z(diff)
    if max_z >= _ELA_FAIL_Z:
        return {
            "label": "Error-level analysis",
            "status": "fail",
            "detail": (f"Localized re-save artifacts (deviation {max_z:.1f}σ at "
                       f"grid {row + 1}/{col + 1}) — a region was likely edited "
                       "after the original capture."),
            "signal": min(1.0, max_z / 40),
        }
    if max_z >= _ELA_REVIEW_Z:
        return {
            "label": "Error-level analysis",
            "status": "review",
            "detail": (f"Some error-level inconsistency (deviation {max_z:.1f}σ "
                       f"at grid {row + 1}/{col + 1}) — heuristic, verify visually."),
            "signal": min(0.6, max_z / 40),
        }
    return {
        "label": "Error-level analysis",
        "status": "pass",
        "detail": f"Error levels uniform across the page (max deviation {max_z:.1f}σ).",
        "signal": min(0.3, max_z / 30),
    }


# ------------------------------------------------------------------- noise
def _noise_flag(rgb: Image) -> dict:
    import cv2
    gray = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY).astype(np.float32)
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    variance = lap * lap  # local energy proxy
    max_z, (row, col) = _grid_max_z(variance)
    if max_z >= _NOISE_FAIL_Z:
        return {
            "label": "Noise/edge consistency",
            "status": "fail",
            "detail": (f"Sharpness/noise pattern inconsistent (deviation "
                       f"{max_z:.1f}σ at grid {row + 1}/{col + 1}) — possible "
                       "pasted or re-rendered region."),
            "signal": min(1.0, max_z / 20),
        }
    if max_z >= _NOISE_REVIEW_Z:
        return {
            "label": "Noise/edge consistency",
            "status": "review",
            "detail": (f"Local texture variation (deviation {max_z:.1f}σ at "
                       f"grid {row + 1}/{col + 1}) — heuristic, verify visually."),
            "signal": min(0.6, max_z / 20),
        }
    return {
        "label": "Noise/edge consistency",
        "status": "pass",
        "detail": f"Texture/sharpness consistent across regions (max deviation {max_z:.1f}σ).",
        "signal": min(0.2, max_z / 40),
    }


# ------------------------------------------------------------------- utils
def _grid_max_z(map2d: np.ndarray) -> tuple[float, tuple[int, int]]:
    """Max robust z-score over a grid of per-cell means; unusually HIGH cells
    are the suspicious direction (more error / more texture than the rest).

    Returns (max_z, (row, col)).
    """
    h, w = map2d.shape
    rows, cols = _GRID[1], _GRID[0]
    ch, cw = max(1, h // rows), max(1, w // cols)
    means = np.empty((rows, cols), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            cell = map2d[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
            means[r, c] = float(cell.mean()) if cell.size else 0.0

    median = float(np.median(means))
    mad = float(np.median(np.abs(means - median)))
    # floor the scale so near-constant grids don't explode z
    scale = max(1.4826 * mad, median * 0.10, 1e-3)
    z = (means - median) / scale

    z_pos = np.where(z > 0, z, 0.0)
    idx = int(np.argmax(z_pos))
    r, c = divmod(idx, cols)
    return float(z_pos[r, c]), (r, c)

"""SENTRY Assist — the in-app help chatbot (GLM via AgentRouter).

Low-effort prototype settings to conserve credits: only the last 6
conversation messages are sent, replies capped at ~250 tokens.
"""

import json
import urllib.error
import urllib.request

_SYSTEM_PROMPT = """You are SENTRY Assist, the AI helper inside SENTRY — an AI-based fake identity & document screening system used at Indian border checkpoints (Smart India Hackathon 2026 project).

About SENTRY: it screens identity documents (passports, Aadhaar, PAN cards, visas) using 4 AI modules — OCR extraction, document validation (ICAO 9303 MRZ checksums, UIDAI Verhoeff checksum for Aadhaar, Income Tax Dept PAN structure rules), tampering forensics (EXIF metadata, error-level analysis, noise consistency), and face verification with liveness checks. A weighted risk engine produces an explainable 0-100 score: LOW under 40, MED 40-69, HIGH 70+. Watchlist matches add 80 points. Officers always make the final decision — the AI only recommends. Uploaded images are securely deleted after analysis.

Answer concisely (2-4 sentences), plainly, and helpfully. You are chatting with border security officers and travelers."""


def ask_assistant(messages: list[dict], screening_context: str | None = None) -> str:
    """Send the conversation to GLM and return the reply text.

    `messages`: [{role: "user"|"assistant", content: "..."}, ...]
    `screening_context`: optional summary of the screening currently open.
    """
    from llmconfig import API_KEY, BASE_URL, MODEL

    system = _SYSTEM_PROMPT
    if screening_context:
        system += "\n\n" + screening_context

    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}] + messages[-6:],
        "max_tokens": 250,
        "temperature": 0.5,
    }
    request = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"GLM API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach AgentRouter: {exc.reason}") from exc

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"unexpected GLM response: {json.dumps(data)[:300]}") from exc


def is_configured() -> bool:
    try:
        from llmconfig import API_KEY
        return bool(API_KEY and not API_KEY.startswith("sk-YOUR"))
    except ImportError:
        return False

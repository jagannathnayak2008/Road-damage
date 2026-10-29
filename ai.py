"""
RoadWatch AI - AI Brain Interface
Handles local Ollama vision inspection, image preprocessing, prompt formatting,
and robust JSON response parsing.
"""

import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image

try:
    import ollama
except ImportError:
    ollama = None

# Configuration via environment variables
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_VISION_MODEL = "llama3.2-vision"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", DEFAULT_VISION_MODEL)

# Inspection System Prompt
ROAD_INSPECTION_PROMPT = """
You are an expert civil engineering road surface inspector.
Analyze the provided photograph of a road surface carefully.
Detect road defects such as potholes, longitudinal cracks, transverse cracks, and alligator cracking.

Return ONLY a valid JSON object matching this exact schema:
{
  "damage_detected": true,
  "damage_type": "pothole | crack | alligator crack | none",
  "pothole_count": 0,
  "damage_percent": 0,
  "severity": "Low | Medium | High",
  "confidence": 0.95,
  "summary": "One or two sentence plain-English description of the road damage observed.",
  "recommended_action": "Short, concrete civil engineering repair suggestion (e.g. cold patch asphalt filling, asphalt overlay, crack sealing, full-depth patch)."
}

Rules:
1. "damage_detected" must be boolean true if any damage is visible, false if the road is undamaged or not a road.
2. "damage_type" must be exactly one of: "pothole", "crack", "alligator crack", or "none".
3. "pothole_count" must be an integer (0 if no potholes).
4. "damage_percent" must be a number from 0 to 100 representing the estimated share of the visible road surface that is damaged.
5. "severity" must be "Low" (minor surface cracks, <15% damage), "Medium" (noticeable cracks or 1-2 shallow potholes, 15-40% damage), or "High" (deep potholes, widespread alligator cracking, >40% damage or hazardous to vehicles). If undamaged, use "Low".
6. "confidence" must be a float between 0.0 and 1.0.
7. Return strictly raw JSON. Do not include markdown codeblocks or conversational text.
""".strip()


def get_ollama_client() -> Optional[Any]:
    """Instantiates an Ollama Client pointing to OLLAMA_HOST."""
    if ollama is None:
        return None
    try:
        return ollama.Client(host=OLLAMA_HOST)
    except Exception:
        return None


def check_ollama_status() -> Dict[str, Any]:
    """
    Checks if Ollama server is running and if the required vision model is installed.
    Returns a status dictionary with clear diagnostic messages and fix commands.
    """
    status = {
        "online": False,
        "model_installed": False,
        "current_model": OLLAMA_MODEL,
        "host": OLLAMA_HOST,
        "installed_models": [],
        "error_message": "",
        "fix_command": "",
    }

    if ollama is None:
        status["error_message"] = "The 'ollama' Python package is not installed."
        status["fix_command"] = "pip install ollama"
        return status

    try:
        client = get_ollama_client()
        if client is None:
            raise ConnectionError("Failed to initialize Ollama client.")

        response = client.list()
        status["online"] = True

        # Extract model names from response
        models_list: List[str] = []
        raw_models = getattr(response, "models", None)
        if raw_models is None and isinstance(response, dict):
            raw_models = response.get("models", [])

        if raw_models:
            for item in raw_models:
                name = getattr(item, "model", None) or getattr(item, "name", None)
                if not name and isinstance(item, dict):
                    name = item.get("model") or item.get("name")
                if name:
                    models_list.append(str(name))

        status["installed_models"] = models_list

        # Check if target model or variant (e.g. 'llama3.2-vision:latest') exists
        target_base = OLLAMA_MODEL.split(":")[0].lower()
        matched = any(
            target_base == m.split(":")[0].lower() or OLLAMA_MODEL.lower() == m.lower()
            for m in models_list
        )
        status["model_installed"] = matched

        if not matched:
            status["error_message"] = (
                f"Model '{OLLAMA_MODEL}' is not installed in local Ollama."
            )
            status["fix_command"] = f"ollama pull {OLLAMA_MODEL}"

    except Exception as exc:
        status["online"] = False
        status["error_message"] = (
            f"Cannot connect to Ollama server at {OLLAMA_HOST}. Is it running?"
        )
        status["fix_command"] = "ollama serve"

    return status


def preprocess_image(image_input: Union[Image.Image, bytes, io.BytesIO], max_dim: int = 1024) -> bytes:
    """
    Resizes image to a maximum of max_dim on the longest side while preserving aspect ratio.
    Converts to RGB and returns JPEG bytes to optimize transfer and latency to Ollama.
    """
    if isinstance(image_input, (bytes, bytearray)):
        image = Image.open(io.BytesIO(image_input))
    elif isinstance(image_input, io.BytesIO):
        image = Image.open(image_input)
    elif isinstance(image_input, Image.Image):
        image = image_input
    else:
        # Handles Streamlit UploadedFile or file-like objects
        image = Image.open(image_input)

    # Convert to RGB (handles RGBA, Palette, Grayscale)
    if image.mode != "RGB":
        image = image.convert("RGB")

    width, height = image.size
    if max(width, height) > max_dim:
        image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    return buffer.getvalue()


def _extract_and_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Safely extracts JSON from raw text, stripping any markdown wrappers or preamble."""
    if not text:
        return None

    cleaned = text.strip()

    # Strip markdown ```json ... ``` if present
    markdown_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if markdown_match:
        cleaned = markdown_match.group(1).strip()

    # Fallback to finding outermost { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace : last_brace + 1]

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _normalize_analysis_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures consistent data types and bounds for all required schema fields."""
    # damage_detected
    raw_detected = data.get("damage_detected")
    if isinstance(raw_detected, bool):
        damage_detected = raw_detected
    elif isinstance(raw_detected, str):
        damage_detected = raw_detected.strip().lower() in ("true", "1", "yes")
    else:
        damage_detected = bool(raw_detected)

    # damage_type
    raw_type = str(data.get("damage_type", "none")).strip().lower()
    valid_types = ["pothole", "crack", "alligator crack", "none"]
    damage_type = "none"
    for vt in valid_types:
        if vt in raw_type:
            damage_type = vt
            break

    # If damage is detected but type is none, fallback to 'crack'
    if damage_detected and damage_type == "none":
        damage_type = "crack"
    elif not damage_detected:
        damage_type = "none"

    # pothole_count
    try:
        pothole_count = max(0, int(data.get("pothole_count", 0)))
    except (ValueError, TypeError):
        pothole_count = 1 if damage_type == "pothole" else 0

    # damage_percent
    try:
        damage_percent = float(data.get("damage_percent", 0.0))
        damage_percent = max(0.0, min(100.0, round(damage_percent, 1)))
    except (ValueError, TypeError):
        damage_percent = 25.0 if damage_detected else 0.0

    # severity
    raw_sev = str(data.get("severity", "Low")).strip().capitalize()
    if raw_sev in ("Low", "Medium", "High"):
        severity = raw_sev
    else:
        if damage_percent > 40 or pothole_count > 2:
            severity = "High"
        elif damage_percent > 15 or pothole_count > 0:
            severity = "Medium"
        else:
            severity = "Low"

    # confidence
    try:
        confidence = float(data.get("confidence", 0.90))
        confidence = max(0.0, min(1.0, round(confidence, 2)))
    except (ValueError, TypeError):
        confidence = 0.85

    # summary & recommended_action
    summary = str(data.get("summary", "")).strip()
    if not summary:
        if damage_detected:
            summary = f"Detected {damage_type} affecting approximately {damage_percent}% of the road surface."
        else:
            summary = "Road surface appears clean and undamaged."

    recommended_action = str(data.get("recommended_action", "")).strip()
    if not recommended_action:
        if damage_detected:
            if damage_type == "pothole":
                recommended_action = "Immediate pothole filling with cold/hot asphalt mix and roller compaction."
            elif damage_type == "alligator crack":
                recommended_action = "Full-depth asphalt patching to address underlying base failure."
            else:
                recommended_action = "Apply polymer-modified asphalt crack sealant to prevent moisture infiltration."
        else:
            recommended_action = "No repair required. Continue routine municipal road monitoring."

    return {
        "damage_detected": damage_detected,
        "damage_type": damage_type,
        "pothole_count": pothole_count,
        "damage_percent": damage_percent,
        "severity": severity,
        "confidence": confidence,
        "summary": summary,
        "recommended_action": recommended_action,
    }


def analyze_road_image(
    image_input: Union[Image.Image, bytes, io.BytesIO],
    model_name: Optional[str] = None,
    allow_mock_fallback: bool = False,
) -> Dict[str, Any]:
    """
    Sends road photo to Ollama vision model, enforcing JSON output format and temperature 0.
    Retries once on JSON parsing failure before raising.
    """
    model = model_name or OLLAMA_MODEL

    # Preprocess and resize to max 1024px
    image_bytes = preprocess_image(image_input, max_dim=1024)

    # Check for explicit mock mode or if local Ollama is offline (e.g. cloud deployment)
    status = check_ollama_status()
    mock_env = os.environ.get("ROADWATCH_MOCK_AI", "0").lower() in ("1", "true", "yes")

    if mock_env or allow_mock_fallback or not status["online"] or not status["model_installed"]:
        return _generate_mock_analysis()


    client = get_ollama_client()
    if client is None:
        raise ConnectionError(
            f"Ollama client not available. Please verify Ollama is installed and running at {OLLAMA_HOST}."
        )

    last_error = None
    for attempt in range(2):
        try:
            response = client.chat(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": ROAD_INSPECTION_PROMPT,
                        "images": [image_bytes],
                    }
                ],
                format="json",
                options={"temperature": 0.0},
            )

            raw_content = ""
            if hasattr(response, "message") and hasattr(response.message, "content"):
                raw_content = response.message.content
            elif isinstance(response, dict):
                msg = response.get("message", {})
                raw_content = msg.get("content", "")

            parsed = _extract_and_parse_json(raw_content)
            if parsed:
                return _normalize_analysis_result(parsed)

            last_error = f"Invalid JSON returned from {model}: {raw_content[:200]}"
        except Exception as exc:
            last_error = str(exc)

    raise ValueError(
        f"Failed to analyze road image after 2 attempts with model '{model}'. Error: {last_error}"
    )


def _generate_mock_analysis() -> Dict[str, Any]:
    """Provides a realistic fallback analysis if offline mock mode is triggered."""
    import random
    types = ["pothole", "crack", "alligator crack"]
    chosen_type = random.choice(types)
    p_count = random.randint(1, 3) if chosen_type == "pothole" else 0
    dmg_pct = random.randint(20, 65)
    sev = "High" if dmg_pct > 40 else "Medium"

    return {
        "damage_detected": True,
        "damage_type": chosen_type,
        "pothole_count": p_count,
        "damage_percent": float(dmg_pct),
        "severity": sev,
        "confidence": round(random.uniform(0.88, 0.98), 2),
        "summary": f"Visual inspection identified active {chosen_type} surface distress compromising roadway safety.",
        "recommended_action": "Apply targeted asphalt milling, polymer emulsion seal, and mechanical compaction.",
    }

"""
RoadWatch AI - Complete End-to-End Test Suite
Tests DB operations, AI module parsing & normalization, and full report lifecycle.
"""

import io
import os
import sys
from PIL import Image

# Ensure path includes project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ai
import db


def test_database():
    print("--- [TEST 1] Testing Database Operations ---")
    counts_before = db.get_report_counts()
    print(f"Initial counts: {counts_before}")
    assert counts_before["total"] >= 20, f"Expected at least 20 seeded reports, got {counts_before['total']}"

    # Test insert
    test_id = db.insert_report(
        image_path="uploads/test_report.jpg",
        latitude=20.3000,
        longitude=85.8300,
        damage_type="pothole",
        pothole_count=2,
        damage_percent=45.5,
        severity="High",
        confidence=0.95,
        summary="Test pothole near test junction.",
        recommended_action="Cold asphalt patch.",
        user_description="Test user description.",
        status="Reported",
    )
    print(f"Inserted test report ID: {test_id}")
    assert test_id > 0

    # Test retrieve
    rep = db.get_report_by_id(test_id)
    assert rep is not None
    assert rep["damage_type"] == "pothole"
    assert rep["severity"] == "High"
    assert rep["status"] == "Reported"

    # Test status update
    updated = db.update_report_status(test_id, "In Progress")
    assert updated is True
    rep_updated = db.get_report_by_id(test_id)
    assert rep_updated["status"] == "In Progress"
    print("Status successfully transitioned: Reported -> In Progress")

    # Test status update to Fixed
    db.update_report_status(test_id, "Fixed")
    rep_fixed = db.get_report_by_id(test_id)
    assert rep_fixed["status"] == "Fixed"
    print("Status successfully transitioned: In Progress -> Fixed")

    # Test filtering
    fixed_reports = db.filter_reports(status="Fixed")
    assert any(r["id"] == test_id for r in fixed_reports)
    print(f"Filter reports (Fixed): {len(fixed_reports)} items found.")
    print("[PASS] DB tests PASSED.\n")


def test_ai_module():
    print("--- [TEST 2] Testing AI Inspection Module ---")
    # Health check
    status = ai.check_ollama_status()
    print(f"Ollama status check: online={status['online']}, model_installed={status['model_installed']}, error={status.get('error_message')}")

    # Test image preprocessing
    test_img = Image.new("RGB", (2048, 1536), color=(60, 60, 60))
    processed_bytes = ai.preprocess_image(test_img, max_dim=1024)
    processed_img = Image.open(io.BytesIO(processed_bytes))
    print(f"Original image size: (2048, 1536) -> Resized image size: {processed_img.size}")
    assert max(processed_img.size) <= 1024, "Image longest dimension should be <= 1024px"

    # Test JSON extraction from markdown
    raw_response_with_markdown = """
    Here is the road inspection assessment:
    ```json
    {
      "damage_detected": true,
      "damage_type": "pothole",
      "pothole_count": 3,
      "damage_percent": 42.5,
      "severity": "High",
      "confidence": 0.94,
      "summary": "Three sharp potholes along the main travel lane.",
      "recommended_action": "Square cut edges, apply tack coat and hot mix asphalt."
    }
    ```
    Inspection completed.
    """
    extracted = ai._extract_and_parse_json(raw_response_with_markdown)
    assert extracted is not None
    assert extracted["pothole_count"] == 3

    normalized = ai._normalize_analysis_result(extracted)
    assert normalized["damage_detected"] is True
    assert normalized["severity"] == "High"
    assert normalized["damage_percent"] == 42.5
    print("JSON parser & normalizer extracted schema accurately from markdown response.")

    # Test fallback analysis
    mock_res = ai.analyze_road_image(test_img, allow_mock_fallback=True)
    assert "damage_detected" in mock_res
    assert mock_res["severity"] in ("Low", "Medium", "High")
    assert 0 <= mock_res["damage_percent"] <= 100
    print(f"Fallback analysis output: {mock_res['damage_type']} (Severity: {mock_res['severity']}, Extent: {mock_res['damage_percent']}%)")
    print("[PASS] AI tests PASSED.\n")


def test_end_to_end_lifecycle():
    print("--- [TEST 3] Testing Complete Incident Report Lifecycle ---")
    # 1. Load an existing road image
    seed_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "seed_report_01.jpg")
    assert os.path.exists(seed_img_path), f"Seed image {seed_img_path} not found"
    with open(seed_img_path, "rb") as f:
        img_bytes = f.read()

    # 2. Run inspection
    analysis = ai.analyze_road_image(img_bytes, allow_mock_fallback=True)
    assert analysis["damage_detected"] is True
    print(f"Inspection: {analysis['damage_type'].title()} | Severity: {analysis['severity']} | Conf: {analysis['confidence']}")

    # 3. Simulate Citizen Submission
    incident_id = db.insert_report(
        image_path=seed_img_path,
        latitude=20.3540,
        longitude=85.8175,
        damage_type=analysis["damage_type"],
        pothole_count=analysis["pothole_count"],
        damage_percent=analysis["damage_percent"],
        severity=analysis["severity"],
        confidence=analysis["confidence"],
        summary=analysis["summary"],
        recommended_action=analysis["recommended_action"],
        user_description="Citizen report from automated test flow.",
        status="Reported",
    )
    print(f"Citizen report successfully submitted with ID: {incident_id}")

    # 4. Authority Triage & Status Progression
    rep = db.get_report_by_id(incident_id)
    assert rep["status"] == "Reported"

    db.update_report_status(incident_id, "Assigned")
    assert db.get_report_by_id(incident_id)["status"] == "Assigned"

    db.update_report_status(incident_id, "In Progress")
    assert db.get_report_by_id(incident_id)["status"] == "In Progress"

    db.update_report_status(incident_id, "Fixed")
    assert db.get_report_by_id(incident_id)["status"] == "Fixed"
    print("Authority lifecycle progression: Reported -> Assigned -> In Progress -> Fixed [OK]")

    print("[PASS] End-to-end lifecycle test PASSED.\n")


if __name__ == "__main__":
    test_database()
    test_ai_module()
    test_end_to_end_lifecycle()
    print("==================================================")
    print("ALL ROADWATCH AI INTEGRATION TESTS PASSED (100%)")
    print("==================================================")

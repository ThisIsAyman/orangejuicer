"""Tests for orangejuicer.tcx — Strava-ready TCX generation."""

from xml.etree import ElementTree as ET

from orangejuicer.tcx import build_description, build_tcx

TCX_NS = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"

WORKOUT = {
    "performance_summary_id": "ps-123",
    "workout_date": "2026-04-18",
    "starts_at": "2026-04-18T09:15:00+00:00",
    "class_name": "Orange 60",
    "class_type": "Orange 60",
    "coach_name": "Jamie",
    "studio_name": "Bethesda, MD",
    "calories_burned": 612,
    "splat_points": 17,
    "active_time_seconds": 3600,
    "avg_hr": 148,
    "max_hr": 179,
}

TELEMETRY = [
    {"relative_timestamp": 0, "hr": 110, "tread_distance": 0.0, "tread_speed": 4.0},
    {"relative_timestamp": 60, "hr": 150, "tread_distance": 0.1, "tread_speed": 6.0},
    {"relative_timestamp": 120, "hr": 165, "tread_distance": 0.25, "tread_speed": 7.0},
    {"relative_timestamp": 180, "hr": 170, "row_distance": 200.0, "row_spm": 28, "row_pace": 130},
]


def _parse(tcx_text):
    return ET.fromstring(tcx_text)


def test_tcx_is_valid_xml_with_other_sport():
    root = _parse(build_tcx(WORKOUT, TELEMETRY))
    activity = root.find(f"{TCX_NS}Activities/{TCX_NS}Activity")
    assert activity is not None
    assert activity.get("Sport") == "Other"


def test_trackpoints_have_heart_rate():
    root = _parse(build_tcx(WORKOUT, TELEMETRY))
    hrs = root.findall(f".//{TCX_NS}Trackpoint/{TCX_NS}HeartRateBpm/{TCX_NS}Value")
    assert [h.text for h in hrs] == ["110", "150", "165", "170"]


def test_distance_is_monotonic_non_decreasing():
    root = _parse(build_tcx(WORKOUT, TELEMETRY))
    dists = [float(d.text) for d in root.findall(f".//{TCX_NS}Trackpoint/{TCX_NS}DistanceMeters")]
    assert dists == sorted(dists)
    # Final distance should combine treadmill miles->metres and rower metres.
    assert dists[-1] > 0


def test_lap_totals_from_summary():
    root = _parse(build_tcx(WORKOUT, TELEMETRY))
    lap = root.find(f".//{TCX_NS}Lap")
    assert lap.find(f"{TCX_NS}Calories").text == "612"
    assert lap.find(f"{TCX_NS}TotalTimeSeconds").text == "3600.0"
    assert lap.find(f"{TCX_NS}AverageHeartRateBpm/{TCX_NS}Value").text == "148"
    assert lap.find(f"{TCX_NS}MaximumHeartRateBpm/{TCX_NS}Value").text == "179"


def test_notes_contains_coach_and_studio():
    root = _parse(build_tcx(WORKOUT, TELEMETRY))
    notes = root.find(f".//{TCX_NS}Notes").text
    assert "Jamie" in notes
    assert "Bethesda, MD" in notes
    assert "Orange 60" in notes


def test_no_telemetry_fallback_emits_trackpoints():
    root = _parse(build_tcx(WORKOUT, []))
    tps = root.findall(f".//{TCX_NS}Trackpoint")
    assert len(tps) == 2  # synthetic start + end
    assert tps[0].find(f"{TCX_NS}HeartRateBpm/{TCX_NS}Value").text == "148"


def test_description_format():
    desc = build_description(WORKOUT)
    lines = desc.split("\n")
    assert lines[0] == "OrangeTheory — Orange 60"
    assert "Coach: Jamie" in lines[1]
    assert "Studio: Bethesda, MD" in lines[1]
    assert "Splats: 17" in lines[2]
    assert "Calories: 612" in lines[2]
    assert "HR avg/max: 148/179" in lines[2]


def test_studio_name_override():
    desc = build_description(WORKOUT, studio_name="Override Studio")
    assert "Override Studio" in desc

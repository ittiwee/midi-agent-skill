#!/usr/bin/env python3
"""
Normalize and validate composition input.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_types.music import Composition, Track, Note
from midi_types.notation import is_rest, parse_duration, parse_pitch, split_pitches


def _num(value, default=None):
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int7(value, low=0):
    v = _num(value)
    return None if v is None else max(low, min(127, int(v)))


def _normalize_note(n: Dict[str, Any], where: str) -> Note:
    """
    Normalize one note. Invalid pitches become rests (instead of being dropped)
    so the timing of the following notes is preserved.
    """
    pitch = n.get("pitch")
    if pitch is None or is_rest(pitch):
        pitch = "R"
    else:
        valid = []
        for p in split_pitches(pitch):
            try:
                parse_pitch(p)
                valid.append(p)
            except ValueError as e:
                print(f"Warning: {where}: {e}", file=sys.stderr)
        pitch = "R" if not valid else (valid[0] if len(valid) == 1 else valid)

    beats = _num(n.get("beats"))
    if beats is not None and beats <= 0:
        beats = None
    duration = n.get("duration")
    if duration is not None:
        duration = str(duration)
        try:
            parse_duration(duration)
        except ValueError as e:
            print(f"Warning: {where}: {e}; using quarter note", file=sys.stderr)
            duration = "4"
    elif beats is None:
        duration = "4"

    start = _num(n.get("start"))
    return Note(
        pitch=pitch,
        duration=duration,
        velocity=_int7(n.get("velocity"), low=1),
        start=max(0.0, start) if start is not None else None,
        beats=beats,
    )


def normalize_composition(data: Any) -> Composition:
    """
    Normalize and validate composition input.

    Handles various input formats and ensures a valid Composition object.

    Args:
        data: Raw input data (dict-like)

    Returns:
        A valid Composition object
    """
    if not isinstance(data, dict):
        data = {}

    title = data.get("title", "untitled")
    if not isinstance(title, str):
        title = str(title) if title else "untitled"

    bpm = _num(data.get("bpm"), 90)
    bpm = max(20, min(300, int(bpm)))

    ts = data.get("time_signature")
    time_signature = None
    if isinstance(ts, (list, tuple)) and len(ts) == 2:
        num, den = int(_num(ts[0], 4)), int(_num(ts[1], 4))
        if num > 0 and den > 0 and den & (den - 1) == 0:
            time_signature = [num, den]

    tempo_changes: List[Dict[str, float]] = []
    for c in data.get("tempo_changes", []) or []:
        if isinstance(c, dict) and _num(c.get("time")) is not None and _num(c.get("bpm")):
            tempo_changes.append({"time": max(0.0, _num(c["time"])),
                                  "bpm": max(20.0, min(300.0, _num(c["bpm"])))})

    tracks = []
    raw_tracks = data.get("tracks", [])
    if not isinstance(raw_tracks, list):
        raw_tracks = []

    for ti, t in enumerate(raw_tracks):
        if not isinstance(t, dict):
            continue

        instrument = t.get("instrument")
        if instrument is not None and not isinstance(instrument, str):
            instrument = str(instrument)

        raw_notes = t.get("notes", [])
        if not isinstance(raw_notes, list):
            raw_notes = []
        notes = [_normalize_note(n, f"track {ti} note {ni}")
                 for ni, n in enumerate(raw_notes) if isinstance(n, dict)]

        if not any(not n.is_rest for n in notes):
            continue  # Only keep tracks that actually play something

        channel = _num(t.get("channel"))
        controls = [dict(c) for c in t.get("controls", []) or []
                    if isinstance(c, dict) and ("cc" in c or "pitchwheel" in c)]
        tracks.append(Track(
            notes=notes,
            instrument=instrument,
            drums=bool(t.get("drums", False)),
            channel=int(channel) if channel is not None and 0 <= channel <= 15 else None,
            name=str(t["name"]) if t.get("name") else None,
            velocity=_int7(t.get("velocity"), low=1),
            volume=_int7(t.get("volume")),
            pan=_int7(t.get("pan")),
            reverb=_int7(t.get("reverb")),
            chorus=_int7(t.get("chorus")),
            controls=controls,
        ))

    return Composition(title=title, bpm=bpm, tracks=tracks,
                       time_signature=time_signature, tempo_changes=tempo_changes)


def normalize_to_dict(data: Any) -> Dict[str, Any]:
    """
    Normalize input and return as dictionary.

    Args:
        data: Raw input data

    Returns:
        Normalized composition as dictionary
    """
    composition = normalize_composition(data)
    return composition.to_dict()


if __name__ == "__main__":
    import json

    messy_input = {
        "title": 123,  # Should become "123"
        "bpm": "120",  # Should become 120
        "tracks": [
            {
                "instrument": "piano",
                "notes": [
                    {"pitch": "C4", "duration": "4"},
                    {"pitch": "E4"},                     # Missing duration -> quarter
                    {"pitch": "H9", "duration": "4"},    # Invalid pitch -> rest (keeps timing)
                    {"pitch": ["G4", "B4"], "duration": "4", "velocity": 300}  # Velocity clamped
                ]
            },
            "invalid_track",  # Should be skipped
            {
                "notes": []  # Empty notes - should be skipped
            }
        ]
    }

    result = normalize_composition(messy_input)
    print(json.dumps(result.to_dict(), indent=2))

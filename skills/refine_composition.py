#!/usr/bin/env python3
"""
Refine composition by adjusting length and other properties.
"""

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_types.music import Composition, Note, Track
from midi_types.notation import parse_duration


def _uses_absolute_time(track: Track) -> bool:
    return any(n.start is not None for n in track.notes)


def _copy(note: Note, offset: float) -> Note:
    """Copy a note; shift it by `offset` beats if it has an absolute start."""
    if note.start is None:
        return replace(note)
    return replace(note, start=note.start + offset)


def _loop_until(track: Track, done) -> None:
    """Append repeats of the track's original notes until done(count, end_beat) is true."""
    base = list(track.notes)
    period = track.end_beat() if _uses_absolute_time(track) else 0.0
    if not base or (_uses_absolute_time(track) and period <= 0):
        return
    repeat = 1
    while not done(len(track.notes), track.end_beat()):
        for note in base:
            if done(len(track.notes), track.end_beat()):
                return
            track.notes.append(_copy(note, period * repeat))
        repeat += 1


def refine_composition(composition: Composition, min_notes: int = 16) -> Composition:
    """
    Ensure each track has at least `min_notes` notes by repeating its material.

    Args:
        composition: The composition to refine
        min_notes: Minimum number of notes per track (default: 16)

    Returns:
        Refined composition
    """
    for track in composition.tracks:
        if 0 < len(track.notes) < min_notes:
            _loop_until(track, lambda count, end: count >= min_notes)
    return composition


def refine_from_dict(data: Dict[str, Any], min_notes: int = 16) -> Dict[str, Any]:
    """
    Refine a composition from dictionary input.

    Args:
        data: Composition as dictionary
        min_notes: Minimum number of notes per track

    Returns:
        Refined composition as dictionary
    """
    composition = Composition.from_dict(data)
    refined = refine_composition(composition, min_notes)
    return refined.to_dict()


def extend_composition(composition: Composition, target_bars: int = 8,
                       beats_per_bar: int = None) -> Composition:
    """
    Extend composition to reach a target number of bars by repeating material.

    Args:
        composition: The composition to extend
        target_bars: Target number of bars
        beats_per_bar: Beats per bar (default: from time_signature, else 4)

    Returns:
        Extended composition
    """
    if beats_per_bar is None:
        if composition.time_signature:
            num, den = composition.time_signature
            beats_per_bar = num * 4 / den
        else:
            beats_per_bar = 4
    target_beats = target_bars * beats_per_bar

    for track in composition.tracks:
        if track.notes and track.end_beat() < target_beats:
            _loop_until(track, lambda count, end: end >= target_beats - 1e-9)

    return composition


def _duration_to_beats(duration_str: str) -> float:
    """Convert duration string to beats (kept for backward compatibility)."""
    try:
        return parse_duration(duration_str)
    except ValueError:
        return 1.0


if __name__ == "__main__":
    import json

    # Example with short tracks
    short_composition = {
        "title": "Short Song",
        "bpm": 100,
        "tracks": [
            {
                "instrument": "piano",
                "notes": [
                    {"pitch": "C4", "duration": "4"},
                    {"pitch": "E4", "duration": "4"},
                    {"pitch": "G4", "duration": "4"}
                ]
            },
            {
                "instrument": "bass",
                "notes": [
                    {"pitch": "C2", "duration": "2"}
                ]
            }
        ]
    }

    result = refine_from_dict(short_composition, min_notes=8)
    print(json.dumps(result, indent=2))

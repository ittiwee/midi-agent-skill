"""
Shared note/duration notation helpers.

Used by generation, import, refinement and enhancement so that every module
interprets pitches and durations the same way.
"""

import re
from typing import List, Optional, Union

# Duration notation -> beats (quarter note = 1 beat)
DURATION_MAP = {
    "1": 4.0,      # whole note
    "d1": 6.0,     # dotted whole
    "2": 2.0,      # half note
    "d2": 3.0,     # dotted half
    "4": 1.0,      # quarter note
    "d4": 1.5,     # dotted quarter
    "8": 0.5,      # eighth note
    "d8": 0.75,    # dotted eighth
    "16": 0.25,    # sixteenth note
    "d16": 0.375,  # dotted sixteenth
    "32": 0.125,   # thirty-second note
    "T2": 4 / 3,   # triplet half
    "T4": 2 / 3,   # triplet quarter (3 in the space of a half note)
    "T8": 1 / 3,   # triplet eighth (3 in the space of a quarter note)
    "T16": 1 / 6,  # triplet sixteenth
}

REST_TOKENS = {"r", "rest", "-", ""}

# General MIDI percussion key map (channel 10)
DRUM_MAP = {
    "kick": 36, "bass-drum": 36, "acoustic-bass-drum": 35,
    "side-stick": 37, "rimshot": 37,
    "snare": 38, "acoustic-snare": 38, "clap": 39, "hand-clap": 39,
    "electric-snare": 40,
    "low-floor-tom": 41, "closed-hihat": 42, "hihat": 42, "hh": 42,
    "high-floor-tom": 43, "pedal-hihat": 44, "low-tom": 45,
    "open-hihat": 46, "ohh": 46, "low-mid-tom": 47, "hi-mid-tom": 48,
    "crash": 49, "crash-cymbal-1": 49, "high-tom": 50,
    "ride": 51, "ride-cymbal-1": 51, "chinese-cymbal": 52, "ride-bell": 53,
    "tambourine": 54, "splash": 55, "cowbell": 56, "crash-cymbal-2": 57,
    "vibraslap": 58, "ride-cymbal-2": 59, "hi-bongo": 60, "low-bongo": 61,
    "mute-hi-conga": 62, "open-hi-conga": 63, "low-conga": 64,
    "high-timbale": 65, "low-timbale": 66, "high-agogo": 67, "low-agogo": 68,
    "cabasa": 69, "maracas": 70, "short-whistle": 71, "long-whistle": 72,
    "short-guiro": 73, "long-guiro": 74, "claves": 75,
    "hi-wood-block": 76, "low-wood-block": 77, "mute-cuica": 78,
    "open-cuica": 79, "mute-triangle": 80, "open-triangle": 81,
}

# Canonical name for each drum key (used when importing)
DRUM_NAMES = {}
for _name, _key in DRUM_MAP.items():
    DRUM_NAMES.setdefault(_key, _name)

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_PITCH_RE = re.compile(r"^([A-Ga-g])(#|b|##|bb)?(-?\d+)$")


def is_rest(pitch: Union[str, int, List, None]) -> bool:
    """True if the pitch value denotes a rest."""
    if pitch is None:
        return True
    if isinstance(pitch, list):
        return all(is_rest(p) for p in pitch)
    return isinstance(pitch, str) and pitch.strip().lower() in REST_TOKENS


def split_pitches(pitch: Union[str, int, List]) -> List[Union[str, int]]:
    """Split a pitch value into individual pitches (chords: list or "C4,E4,G4")."""
    if isinstance(pitch, list):
        out: List[Union[str, int]] = []
        for p in pitch:
            out.extend(split_pitches(p))
        return out
    if isinstance(pitch, str):
        return [p.strip() for p in re.split(r"[,+ ]+", pitch) if p.strip()]
    return [pitch]


def parse_pitch(pitch: Union[str, int]) -> int:
    """
    Convert a single pitch to a MIDI note number.

    Accepts "C4" (=60), "F#5", "Bb3", raw MIDI numbers (60 or "60"),
    and GM drum names ("kick", "snare", "hihat", ...).
    """
    if isinstance(pitch, bool):
        raise ValueError(f"Invalid pitch: {pitch!r}")
    if isinstance(pitch, (int, float)):
        n = int(pitch)
    else:
        s = str(pitch).strip()
        if re.fullmatch(r"\d+", s):
            n = int(s)
        elif s.lower().replace("_", "-") in DRUM_MAP:
            n = DRUM_MAP[s.lower().replace("_", "-")]
        else:
            m = _PITCH_RE.match(s)
            if not m:
                raise ValueError(f"Invalid pitch format: {pitch!r}")
            letter, acc, octave = m.groups()
            n = (int(octave) + 1) * 12 + _NOTE_OFFSETS[letter.upper()]
            n += {"#": 1, "##": 2, "b": -1, "bb": -2}.get(acc or "", 0)
    if not 0 <= n <= 127:
        raise ValueError(f"Pitch out of MIDI range (0-127): {pitch!r}")
    return n


def pitch_name(note_number: int) -> str:
    """Convert MIDI note number to a name, e.g. 60 -> "C4"."""
    return f"{NOTE_NAMES[note_number % 12]}{note_number // 12 - 1}"


def parse_duration(duration: Union[str, int, float, None]) -> float:
    """
    Convert duration notation to beats.

    Raises ValueError for unparseable values so callers can decide what to do.
    """
    if duration is None:
        raise ValueError("Missing duration")
    s = str(duration).strip()
    if s in DURATION_MAP:
        return DURATION_MAP[s]
    try:
        division = float(s)
    except ValueError:
        raise ValueError(f"Invalid duration: {duration!r}")
    if division <= 0:
        raise ValueError(f"Invalid duration: {duration!r}")
    return 4.0 / division


def beats_to_duration(beats: float, tolerance: float = 1e-4) -> Optional[str]:
    """Return the notation string matching `beats`, or None if there is none."""
    for key, value in DURATION_MAP.items():
        if abs(value - beats) <= tolerance:
            return key
    return None

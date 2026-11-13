"""
Type definitions for music composition.

Timing model
------------
Each track keeps a cursor (in beats) starting at 0. A note is placed at
`start` if given, otherwise at the cursor. Its length is `beats` if given,
otherwise `duration` notation ("4" = quarter). After each note (or rest) the
cursor moves to `start + length`. Older compositions that only use
pitch + duration therefore behave exactly as before.
"""

import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Union

from .notation import is_rest, parse_duration

PitchValue = Union[str, int, List[Union[str, int]]]


@dataclass
class Note:
    """A note, chord, or rest."""
    pitch: PitchValue                # "C4", ["C4","E4","G4"], "C4,E4,G4", "R" (rest), "kick"
    duration: Optional[str] = "4"    # notation: "4" quarter, "8" eighth, "d4", "T8", ...
    velocity: Optional[int] = None   # 1-127; falls back to track velocity, then 100
    start: Optional[float] = None    # absolute position in beats (optional)
    beats: Optional[float] = None    # exact length in beats; overrides `duration`

    @property
    def is_rest(self) -> bool:
        return is_rest(self.pitch)

    def length(self) -> float:
        """Length in beats (falls back to 1 beat with a warning if unparseable)."""
        if self.beats is not None:
            return float(self.beats)
        try:
            return parse_duration(self.duration)
        except ValueError as e:
            print(f"Warning: {e}; using 1 beat", file=sys.stderr)
            return 1.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"pitch": self.pitch}
        if self.start is not None:
            d["start"] = self.start
        if self.beats is not None:
            d["beats"] = self.beats
        elif self.duration is not None:
            d["duration"] = self.duration
        if self.velocity is not None:
            d["velocity"] = self.velocity
        return d

    @classmethod
    def from_dict(cls, n: Dict[str, Any]) -> "Note":
        beats = n.get("beats")
        start = n.get("start")
        velocity = n.get("velocity")
        duration = n.get("duration")
        return cls(
            pitch=n.get("pitch", "R"),
            duration=str(duration) if duration is not None else (None if beats is not None else "4"),
            velocity=int(velocity) if velocity is not None else None,
            start=float(start) if start is not None else None,
            beats=float(beats) if beats is not None else None,
        )


class TimedNote(NamedTuple):
    start: float
    beats: float
    note: Note


@dataclass
class Track:
    """A track containing notes for a single instrument."""
    notes: List[Note] = field(default_factory=list)
    instrument: Optional[str] = None   # GM instrument name / alias
    drums: bool = False                # True -> GM percussion channel (10)
    channel: Optional[int] = None      # explicit MIDI channel 0-15 (auto if None)
    name: Optional[str] = None         # track name shown in DAWs
    velocity: Optional[int] = None     # default velocity for notes without one
    volume: Optional[int] = None       # CC7  (0-127) at time 0
    pan: Optional[int] = None          # CC10 (0=left, 64=center, 127=right)
    reverb: Optional[int] = None       # CC91 (0-127)
    chorus: Optional[int] = None       # CC93 (0-127)
    controls: List[Dict[str, Any]] = field(default_factory=list)
    # controls: [{"time": beats, "cc": 64, "value": 127}, {"time": beats, "pitchwheel": -8192..8191}]

    def timeline(self) -> Iterator[TimedNote]:
        """Yield every note/rest with its resolved absolute start and length."""
        cursor = 0.0
        for note in self.notes:
            start = note.start if note.start is not None else cursor
            beats = note.length()
            yield TimedNote(start, beats, note)
            cursor = start + beats

    def end_beat(self) -> float:
        """Beat at which the last note of the track ends."""
        return max((t.start + t.beats for t in self.timeline()), default=0.0)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for key in ("name", "instrument"):
            if getattr(self, key) is not None:
                d[key] = getattr(self, key)
        if self.drums:
            d["drums"] = True
        for key in ("channel", "velocity", "volume", "pan", "reverb", "chorus"):
            if getattr(self, key) is not None:
                d[key] = getattr(self, key)
        if self.controls:
            d["controls"] = [dict(c) for c in self.controls]
        d["notes"] = [n.to_dict() for n in self.notes]
        return d

    @classmethod
    def from_dict(cls, t: Dict[str, Any]) -> "Track":
        def opt_int(key):
            v = t.get(key)
            return int(v) if v is not None else None
        return cls(
            notes=[Note.from_dict(n) for n in t.get("notes", []) if isinstance(n, dict)],
            instrument=t.get("instrument"),
            drums=bool(t.get("drums", False)),
            channel=opt_int("channel"),
            name=t.get("name"),
            velocity=opt_int("velocity"),
            volume=opt_int("volume"),
            pan=opt_int("pan"),
            reverb=opt_int("reverb"),
            chorus=opt_int("chorus"),
            controls=[dict(c) for c in t.get("controls", []) if isinstance(c, dict)],
        )


@dataclass
class Composition:
    """A complete musical composition."""
    title: str
    bpm: float
    tracks: List[Track] = field(default_factory=list)
    time_signature: Optional[List[int]] = None             # e.g. [3, 4]
    tempo_changes: List[Dict[str, float]] = field(default_factory=list)
    # tempo_changes: [{"time": beats, "bpm": 140}]

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"title": self.title, "bpm": self.bpm}
        if self.time_signature:
            d["time_signature"] = list(self.time_signature)
        if self.tempo_changes:
            d["tempo_changes"] = [dict(c) for c in self.tempo_changes]
        d["tracks"] = [t.to_dict() for t in self.tracks]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Composition":
        ts = data.get("time_signature")
        return cls(
            title=data.get("title", "untitled"),
            bpm=data.get("bpm", 90),
            tracks=[Track.from_dict(t) for t in data.get("tracks", []) if isinstance(t, dict)],
            time_signature=[int(ts[0]), int(ts[1])] if ts else None,
            tempo_changes=[dict(c) for c in data.get("tempo_changes", []) if isinstance(c, dict)],
        )

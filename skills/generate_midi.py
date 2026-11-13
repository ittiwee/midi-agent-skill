#!/usr/bin/env python3
"""
Generate MIDI file from a Composition object using midiutil.
Uses General MIDI program changes compatible with A320U.sf2 SoundFont.

Supports chords, rests, per-note velocity, absolute note starts, drum tracks
(GM channel 10), mix controls (volume/pan/reverb/chorus), arbitrary CC and
pitch-wheel events, time signature and tempo changes.
"""

import math
import re
import sys
from pathlib import Path
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from midiutil import MIDIFile
from midi_types.music import Composition, Track
from midi_types.gm_instruments import resolve_instrument
from midi_types.notation import (  # noqa: F401  (re-exported for backward compatibility)
    DURATION_MAP,
    parse_duration,
    parse_pitch,
    split_pitches,
)

DRUM_CHANNEL = 9
MELODIC_CHANNELS = [c for c in range(16) if c != DRUM_CHANNEL]  # 15 channels
DRUM_INSTRUMENT_NAMES = {"drums", "drum", "drum-kit", "drumkit", "percussion", "standard-kit", "kit"}
TICKS_PER_QUARTER = 960


def is_drum_track(track: Track) -> bool:
    if track.drums or track.channel == DRUM_CHANNEL:
        return True
    if track.instrument:
        return re.sub(r"[\s_]+", "-", track.instrument.lower()) in DRUM_INSTRUMENT_NAMES
    return False


def track_program(track: Track) -> int:
    return resolve_instrument(track.instrument) if track.instrument else 0


def assign_channels(tracks: List[Track]) -> List[int]:
    """
    Assign a MIDI channel to every track.

    - Drum tracks go to channel 10 (index 9).
    - Tracks with an explicit `channel` keep it.
    - Other tracks get a free melodic channel. When all 15 are taken, a track
      shares the channel of an earlier track using the same instrument.
      If no such track exists, a ValueError is raised instead of silently
      overlapping two different instruments on one channel.
    """
    channels: List[Optional[int]] = [None] * len(tracks)
    used = set()

    for i, track in enumerate(tracks):
        if is_drum_track(track):
            channels[i] = DRUM_CHANNEL
        elif track.channel is not None:
            if not 0 <= track.channel <= 15:
                raise ValueError(f"Track {i}: channel must be 0-15, got {track.channel}")
            channels[i] = track.channel
            used.add(track.channel)

    free = [c for c in MELODIC_CHANNELS if c not in used]
    program_channel = {}
    for i, track in enumerate(tracks):
        if channels[i] is not None:
            program_channel.setdefault(track_program(track), channels[i])
            continue
        program = track_program(track)
        if free:
            channels[i] = free.pop(0)
            program_channel.setdefault(program, channels[i])
        elif program in program_channel and program_channel[program] != DRUM_CHANNEL:
            channels[i] = program_channel[program]
        else:
            raise ValueError(
                f"Too many melodic instruments: track {i} ({track.instrument}) needs a channel "
                f"but all 15 melodic channels are in use. Merge tracks that use the same "
                f"instrument, or reuse an instrument already in the piece."
            )
    return channels  # type: ignore[return-value]


def _ticks(beats: float) -> int:
    """Beats -> integer ticks, rounded (midiutil itself truncates, which drops a tick)."""
    return max(0, int(round(float(beats) * TICKS_PER_QUARTER)))


def _clamp7(value) -> int:
    return max(0, min(127, int(value)))


def generate_midi(composition: Composition, output_path: Optional[str] = None) -> str:
    """
    Generate a MIDI file from a Composition object.

    Args:
        composition: The composition to convert to MIDI
        output_path: Where to write the file (default: output/<title>.mid)

    Returns:
        The path to the generated MIDI file
    """
    tracks = composition.tracks
    channels = assign_channels(tracks)
    midi = MIDIFile(max(1, len(tracks)), file_format=1, ticks_per_quarternote=TICKS_PER_QUARTER,
                    eventtime_is_ticks=True)

    # Global meta events on track 0
    midi.addTempo(0, 0, composition.bpm)
    for change in composition.tempo_changes:
        midi.addTempo(0, _ticks(change["time"]), float(change["bpm"]))
    if composition.time_signature:
        num, den = composition.time_signature
        if den <= 0 or den & (den - 1):
            raise ValueError(f"Time signature denominator must be a power of 2, got {den}")
        midi.addTimeSignature(0, 0, int(num), int(math.log2(den)), 24)

    for track_idx, track in enumerate(tracks):
        channel = channels[track_idx]
        drums = channel == DRUM_CHANNEL

        midi.addTrackName(track_idx, 0, track.name or track.instrument or f"Track {track_idx + 1}")
        # On channel 10 the program selects the drum kit (0 = standard kit)
        midi.addProgramChange(track_idx, channel, 0, 0 if drums else track_program(track))

        for cc, value in ((7, track.volume), (10, track.pan), (91, track.reverb), (93, track.chorus)):
            if value is not None:
                midi.addControllerEvent(track_idx, channel, 0, cc, _clamp7(value))

        for ctrl in track.controls:
            time = _ticks(ctrl.get("time", 0))
            if "pitchwheel" in ctrl:
                value = max(-8192, min(8191, int(ctrl["pitchwheel"])))
                midi.addPitchWheelEvent(track_idx, channel, time, value)
            elif "cc" in ctrl:
                midi.addControllerEvent(track_idx, channel, time, int(ctrl["cc"]) & 0x7F,
                                        _clamp7(ctrl.get("value", 0)))

        default_velocity = track.velocity if track.velocity is not None else 100

        # The timeline always advances, even when a note is invalid, so one bad
        # note can no longer shift the rest of the track out of sync.
        for start, beats, note in track.timeline():
            if note.is_rest or beats <= 0:
                continue
            velocity = max(1, min(127, int(note.velocity if note.velocity is not None
                                           else default_velocity)))
            for p in split_pitches(note.pitch):
                try:
                    pitch = parse_pitch(p)
                except ValueError as e:
                    print(f"Warning: track {track_idx}: skipping pitch at beat {start:g}: {e}",
                          file=sys.stderr)
                    continue
                midi.addNote(track=track_idx, channel=channel, pitch=pitch,
                             time=_ticks(start), duration=max(1, _ticks(beats)),
                             volume=velocity)

    if output_path:
        file_path = Path(output_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(__file__).parent.parent / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", composition.title)
        file_path = out_dir / f"{safe_title}.mid"

    with open(file_path, "wb") as f:
        midi.writeFile(f)

    return str(file_path)


def generate_midi_from_dict(data: dict, output_path: Optional[str] = None) -> str:
    """
    Generate MIDI from a dictionary representation.

    Args:
        data: Dictionary with title, bpm, and tracks
        output_path: Optional output file path

    Returns:
        Path to the generated MIDI file
    """
    composition = Composition.from_dict(data)
    return generate_midi(composition, output_path)


if __name__ == "__main__":
    example = {
        "title": "Test Multi-Instrument",
        "bpm": 120,
        "time_signature": [4, 4],
        "tracks": [
            {
                "instrument": "acoustic-grand-piano",
                "notes": [
                    {"pitch": ["C4", "E4", "G4"], "duration": "2", "velocity": 80},
                    {"pitch": "R", "duration": "4"},
                    {"pitch": "C5", "duration": "4", "velocity": 110}
                ]
            },
            {
                "instrument": "acoustic-bass",
                "pan": 40,
                "notes": [
                    {"pitch": "C2", "duration": "2"},
                    {"pitch": "G2", "duration": "2"}
                ]
            },
            {
                "instrument": "drums",
                "notes": [
                    {"pitch": "kick,hihat", "duration": "8"},
                    {"pitch": "hihat", "duration": "8"},
                    {"pitch": "snare,hihat", "duration": "8"},
                    {"pitch": "hihat", "duration": "8"}
                ]
            }
        ]
    }

    result = generate_midi_from_dict(example)
    print(f"Generated: {result}")

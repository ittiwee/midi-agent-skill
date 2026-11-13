#!/usr/bin/env python3
"""
Import an existing MIDI file into the composition JSON format.

The result can be edited (by hand, by Claude, or with enhance_midi.py) and
written back with generate_midi.py. Every note gets an absolute `start`, so
timing, overlaps and chords are preserved exactly.

Preserved: notes, velocities, chords, drums (channel 10), program per channel,
track names, tempo + tempo changes, time signature, CC and pitch-wheel events.
Not preserved: SysEx, lyrics/markers, mid-track program changes (the first
program on each channel is used; a warning lists the others).

Usage:
    python skills/import_midi.py song.mid [out.json]
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from midi_types.gm_instruments import get_instrument_name
from midi_types.notation import DRUM_NAMES, beats_to_duration, pitch_name

DRUM_CHANNEL = 9


def _r(x: float) -> float:
    """Round beat values for readable JSON while staying finer than one tick."""
    v = round(x, 6)
    return int(v) if v == int(v) else v


def _note_to_dict(start: float, beats: float, pitches: List[int], velocity: int,
                  drums: bool) -> Dict[str, Any]:
    names = [DRUM_NAMES.get(p, str(p)) if drums else pitch_name(p) for p in pitches]
    d: Dict[str, Any] = {"pitch": names[0] if len(names) == 1 else names, "start": _r(start)}
    notation = beats_to_duration(beats, tolerance=1e-3)
    if notation is not None:
        d["duration"] = notation
    else:
        d["beats"] = _r(beats)
    d["velocity"] = velocity
    return d


def import_midi(midi_path: str, merge_chords: bool = True) -> Dict[str, Any]:
    """
    Read a MIDI file and return a composition dictionary.

    Args:
        midi_path: Path to a .mid file
        merge_chords: Combine notes with identical start, length and velocity
                      into one chord entry (more compact, same sound)

    Returns:
        Composition dictionary compatible with generate_midi_from_dict()
    """
    try:
        import mido
    except ImportError:
        raise RuntimeError("mido is required for MIDI import: pip install mido")

    mid = mido.MidiFile(midi_path)
    if mid.type == 2:
        raise ValueError("MIDI type 2 (multiple independent songs) is not supported")
    tpb = mid.ticks_per_beat

    tempos: List[tuple] = []         # (tick, bpm)
    time_signature: Optional[List[int]] = None
    out_tracks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # First program seen per channel anywhere in the file (some type-1 files put
    # all program changes in a separate track from the notes)
    global_programs: Dict[int, int] = {}
    for mtrack in mid.tracks:
        for msg in mtrack:
            if msg.type == "program_change":
                global_programs.setdefault(msg.channel, msg.program)

    for ti, mtrack in enumerate(mid.tracks):
        tick = 0
        track_name: Optional[str] = None
        active: Dict[tuple, List[tuple]] = defaultdict(list)    # (ch, pitch) -> [(tick, vel)]
        notes: Dict[int, List[tuple]] = defaultdict(list)        # ch -> [(start, end, pitch, vel)]
        programs: Dict[int, int] = {}
        controls: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

        for msg in mtrack:
            tick += msg.time
            t = msg.type
            if t == "track_name" and track_name is None:
                track_name = msg.name.strip() or None
            elif t == "set_tempo":
                bpm_value = round(mido.tempo2bpm(msg.tempo), 2)
                tempos.append((tick, int(bpm_value) if bpm_value == int(bpm_value) else bpm_value))
            elif t == "time_signature" and time_signature is None:
                time_signature = [msg.numerator, msg.denominator]
            elif t == "note_on" and msg.velocity > 0:
                active[(msg.channel, msg.note)].append((tick, msg.velocity))
            elif t == "note_off" or (t == "note_on" and msg.velocity == 0):
                stack = active.get((msg.channel, msg.note))
                if stack:
                    start, vel = stack.pop(0)
                    notes[msg.channel].append((start, tick, msg.note, vel))
            elif t == "program_change":
                if msg.channel not in programs:
                    programs[msg.channel] = msg.program
                elif programs[msg.channel] != msg.program:
                    warnings.append(f"track {ti} ch {msg.channel + 1}: program change to "
                                    f"{msg.program} at beat {tick / tpb:g} ignored")
            elif t == "control_change":
                controls[msg.channel].append({"time": _r(tick / tpb), "cc": msg.control,
                                              "value": msg.value})
            elif t == "pitchwheel":
                controls[msg.channel].append({"time": _r(tick / tpb), "pitchwheel": msg.pitch})

        # Close notes that never received a note-off
        for (ch, pitch), stack in active.items():
            for start, vel in stack:
                notes[ch].append((start, max(tick, start + tpb), pitch, vel))  # at least 1 beat
                warnings.append(f"track {ti} ch {ch + 1}: unterminated note {pitch} closed at end")

        for ch in sorted(set(notes) | set(controls)):
            if not notes.get(ch):
                continue  # controller-only channel data without notes is dropped
            drums = ch == DRUM_CHANNEL
            entries = sorted(notes[ch], key=lambda n: (n[0], n[2]))

            # Group into chords
            groups: List[List[tuple]] = []
            for n in entries:
                last = groups[-1][0] if groups else None
                if (merge_chords and last and last[0] == n[0] and last[1] == n[1]
                        and last[3] == n[3]):
                    groups[-1].append(n)
                else:
                    groups.append([n])

            note_dicts = []
            for g in groups:
                start, end, _, vel = g[0]
                beats = max(end - start, 1) / tpb
                note_dicts.append(_note_to_dict(start / tpb, beats, [n[2] for n in g], vel, drums))

            track: Dict[str, Any] = {}
            if drums:
                track["instrument"] = "drums"
                track["drums"] = True
            else:
                track["instrument"] = get_instrument_name(programs.get(ch, global_programs.get(ch, 0)))
            if track_name:
                track["name"] = track_name
            track["channel"] = ch
            # Hoist time-0 mix controllers into readable track fields
            rest_controls = []
            for c in controls.get(ch, []):
                field = {7: "volume", 10: "pan", 91: "reverb", 93: "chorus"}.get(c.get("cc"))
                if field and c["time"] == 0 and field not in track:
                    track[field] = c["value"]
                else:
                    rest_controls.append(c)
            if rest_controls:
                track["controls"] = rest_controls
            track["notes"] = note_dicts
            out_tracks.append(track)

    tempos.sort()
    bpm = tempos[0][1] if tempos and tempos[0][0] == 0 else 120
    tempo_changes = [{"time": _r(tk / tpb), "bpm": b} for tk, b in tempos if tk > 0]

    title = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(midi_path).stem)
    result: Dict[str, Any] = {"title": title, "bpm": bpm}
    if time_signature:
        result["time_signature"] = time_signature
    if tempo_changes:
        result["tempo_changes"] = tempo_changes
    result["tracks"] = out_tracks

    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)
    return result


def import_midi_to_json(midi_path: str, json_path: Optional[str] = None) -> str:
    """Import a MIDI file and write the composition JSON. Returns the JSON path."""
    data = import_midi(midi_path)
    if json_path is None:
        out_dir = Path(__file__).parent.parent / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = str(out_dir / f"{data['title']}.json")
    Path(json_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return json_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = import_midi_to_json(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"Imported: {path}")

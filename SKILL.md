---
name: midi-generation
description: Generate, import and enhance MIDI files with GM instruments and music theory. Use when creating music, composing melodies, generating MIDI files, or improving/editing an existing MIDI file.
license: MIT
---

# MIDI Generation Skill

Generate MIDI files with proper music theory. **Use the provided Python scripts in `skills/`. Do NOT write custom code.**

## Important Rules

1. **Use provided scripts** in `skills/` directory (Python)
2. **Never write custom Python/JS** for MIDI generation
3. **Install dependencies first**: `pip install midiutil mido`
4. **Consult music theory resources** when needed (see below)

## Quick Dissonance Rules

**Always follow these to avoid harsh sounds:**

1. **Never play notes 1 semitone apart** (C+C#, E+F, B+C)
2. **Bass plays root or fifth** of the chord
3. **Spread voices across octaves** (don't cluster)
4. **Each track uses different MIDI channel** (automatic)

---

## Music Theory Resources (Read When Needed)

**Only read the resource that matches your current task:**

| When you need... | Read this file |
|------------------|----------------|
| Scales, chords, intervals, cadences | [resources/music-theory.md](resources/music-theory.md) |
| Chord progressions by genre | [resources/chord-progressions.md](resources/chord-progressions.md) |
| Avoiding dissonance, voice spacing | [resources/voice-leading.md](resources/voice-leading.md) |
| **Classical/Baroque counterpoint** | [resources/counterpoint.md](resources/counterpoint.md) |
| Modes (Dorian, Phrygian, etc.) | [resources/modes-scales.md](resources/modes-scales.md) |
| Rhythm, time signatures, syncopation | [resources/rhythm-patterns.md](resources/rhythm-patterns.md) |
| Instrument ranges, combinations | [resources/orchestration.md](resources/orchestration.md) |

### When to Read Each Resource

- **Pop/Rock song** → chord-progressions.md + voice-leading.md
- **Classical piece** → counterpoint.md + orchestration.md
- **Jazz composition** → modes-scales.md + chord-progressions.md
- **Film score** → orchestration.md + modes-scales.md
- **Any composition** → Always check voice-leading.md for dissonance

---

## Workflow

1. **Install dependencies**: `pip install midiutil mido`
2. **Identify genre/style** → Select appropriate resources
3. **Read relevant theory** → Only the files you need
4. **Choose instruments** → See [midi_types/gm_instruments.py](midi_types/gm_instruments.py)
5. **Create composition JSON**
6. **Use scripts** to generate MIDI

### Improving an existing MIDI file

1. `import_midi("song.mid")` → composition dict (every note has an absolute `start`)
2. Either apply ready-made operations with `enhance_midi_file()` / `enhance_dict()`,
   or edit the dict directly using the theory resources (reharmonize, add parts, fix clashes)
3. `generate_midi_from_dict(data, "output/song_improved.mid")` → optionally `convert_to_wav()`

Never overwrite the user's original file unless they ask.

```python
from skills import import_midi, enhance_midi_file, enhance_dict, generate_midi_from_dict

# Quick polish: less robotic timing/velocity, wider dynamics, some reverb
enhance_midi_file("song.mid", [
    {"op": "quantize", "grid": "16", "strength": 0.7},
    {"op": "humanize", "timing": 0.015, "velocity": 8},
    {"op": "dynamics", "low": 55, "high": 115},
    {"op": "set_mix", "track": 0, "reverb": 50, "pan": 50},
], "output/song_enhanced.mid")
```

| Operation | Arguments |
|-----------|-----------|
| `humanize` | `timing` (beats, default 0.02), `velocity` (±, default 8), `tracks`, `seed` |
| `quantize` | `grid` ("16", "8", "T8"…), `strength` 0–1, `lengths` (bool), `tracks` |
| `transpose` | `semitones`, `tracks` (drum tracks are skipped) |
| `set_instrument` | `track` (index), `instrument` |
| `set_mix` | `track`, `volume`, `pan`, `reverb`, `chorus` (0–127) |
| `dynamics` | `low`, `high` (rescale velocities), `tracks` |

`tracks` is a track index or list of indices; omit for all tracks.

## Python Scripts

| Script | Purpose |
|--------|---------|
| `skills/generate_midi.py` | Generate MIDI (auto-assigns channels per track) |
| `skills/normalize_composition.py` | Validate and normalize input |
| `skills/refine_composition.py` | Adjust length, extend tracks |
| `skills/convert_to_wav.py` | MIDI → WAV (requires FluidSynth) |
| `skills/import_midi.py` | Existing MIDI → composition dict/JSON (requires mido) |
| `skills/enhance_midi.py` | Humanize, quantize, transpose, re-orchestrate, mix |

## Usage Example

```python
import sys
sys.path.insert(0, '/path/to/midi-skill')

from skills.generate_midi import generate_midi_from_dict

composition = {
    "title": "My Song",
    "bpm": 120,
    "tracks": [
        {
            "instrument": "acoustic-grand-piano",
            "notes": [
                {"pitch": "C4", "duration": "4"},
                {"pitch": "E4", "duration": "4"},
                {"pitch": "G4", "duration": "4"},
                {"pitch": "C5", "duration": "2"}
            ]
        },
        {
            "instrument": "acoustic-bass",
            "notes": [
                {"pitch": "C2", "duration": "2"},
                {"pitch": "G2", "duration": "2"}
            ]
        }
    ]
}

midi_path = generate_midi_from_dict(composition)
print(f"Generated: {midi_path}")
```

## Composition Format

```json
{
  "title": "My Song",
  "bpm": 120,
  "tracks": [
    {
      "instrument": "acoustic-grand-piano",
      "notes": [
        { "pitch": "C4", "duration": "4" },
        { "pitch": "E4", "duration": "4" }
      ]
    },
    {
      "instrument": "acoustic-bass",
      "notes": [
        { "pitch": "C2", "duration": "2" }
      ]
    }
  ]
}
```

## Note & Track Options

**Note fields**

| Field | Meaning |
|-------|---------|
| `pitch` | `"C4"`, `"F#5"`, `"Bb3"`, MIDI number `60`; chord: `["C4","E4","G4"]` or `"C4,E4,G4"`; rest: `"R"` |
| `duration` | Notation (table below) |
| `beats` | Exact length in beats (overrides `duration`), e.g. `0.4` |
| `velocity` | 1–127 loudness (default: track `velocity`, else 100). **Vary it** — accents, phrasing, crescendos |
| `start` | Absolute position in beats (optional). Without it, notes follow each other |

**Track fields:** `instrument`, `name`, `drums` (true → GM drum channel), `velocity` (default),
`volume`, `pan` (0 L – 64 C – 127 R), `reverb`, `chorus` (0–127),
`controls` (`[{"time": 0, "cc": 64, "value": 127}, {"time": 2, "pitchwheel": 4096}]`), `channel` (normally automatic)

**Composition fields:** `title`, `bpm`, `time_signature` (`[3, 4]`), `tempo_changes` (`[{"time": 32, "bpm": 100}]`)

**Drums:** use `"instrument": "drums"`; pitches are names like `kick`, `snare`, `hihat`, `open-hihat`,
`crash`, `ride`, `low-tom`, `high-tom`, `clap` (full list: `DRUM_MAP` in [midi_types/notation.py](midi_types/notation.py)).

```json
{"instrument": "drums", "notes": [
  {"pitch": ["kick", "hihat"], "duration": "8", "velocity": 110},
  {"pitch": "hihat", "duration": "8", "velocity": 70},
  {"pitch": ["snare", "hihat"], "duration": "8", "velocity": 105},
  {"pitch": "hihat", "duration": "8", "velocity": 70}
]}
```

## Duration Notation

| Value | Note |
|-------|------|
| `1` | Whole note (4 beats) |
| `2` | Half note (2 beats) |
| `d2` | Dotted half (3 beats) |
| `4` | Quarter note (1 beat) |
| `d4` | Dotted quarter (1.5 beats) |
| `8` | Eighth note (0.5 beats) |
| `16` | Sixteenth note (0.25 beats) |
| `32` | Thirty-second note |
| `T4` / `T8` / `T16` | Triplets (3 in the space of 2) |

## Instrument Aliases

| Alias | GM Instrument |
|-------|---------------|
| `piano` | acoustic-grand-piano |
| `guitar` | acoustic-guitar-nylon |
| `bass` | acoustic-bass |
| `strings` | string-ensemble-1 |
| `brass` | brass-section |
| `sax` | alto-sax |

Full list: [midi_types/gm_instruments.py](midi_types/gm_instruments.py)

## Notes

- 15 melodic channels (0-8, 10-15) + drums on ch.9. More tracks are allowed only if they reuse an instrument already in the piece (they share its channel); otherwise an error is raised
- Output: `output/` directory
- WAV requires: FluidSynth + A320U.sf2 in `soundfonts/`

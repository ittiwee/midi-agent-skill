"""Types module for MIDI generation."""

from .music import Note, Track, Composition
from .notation import DURATION_MAP, DRUM_MAP, parse_pitch, parse_duration, pitch_name
from .gm_instruments import (
    GM_INSTRUMENTS,
    INSTRUMENT_ALIASES,
    resolve_instrument,
    get_instrument_name,
    get_instruments_by_category
)

__all__ = [
    "Note",
    "Track",
    "Composition",
    "DURATION_MAP",
    "DRUM_MAP",
    "parse_pitch",
    "parse_duration",
    "pitch_name",
    "GM_INSTRUMENTS",
    "INSTRUMENT_ALIASES",
    "resolve_instrument",
    "get_instrument_name",
    "get_instruments_by_category"
]

"""Skills module for MIDI generation, import and enhancement."""

from .generate_midi import generate_midi, generate_midi_from_dict
from .normalize_composition import normalize_composition, normalize_to_dict
from .refine_composition import refine_composition, refine_from_dict, extend_composition
from .convert_to_wav import convert_to_wav, get_conversion_status, ConvertOptions
from .import_midi import import_midi, import_midi_to_json
from .enhance_midi import (
    apply_operations,
    enhance_dict,
    enhance_midi_file,
    humanize,
    quantize,
    transpose,
    set_instrument,
    set_mix,
    dynamics,
)

__all__ = [
    "generate_midi",
    "generate_midi_from_dict",
    "normalize_composition",
    "normalize_to_dict",
    "refine_composition",
    "refine_from_dict",
    "extend_composition",
    "convert_to_wav",
    "get_conversion_status",
    "ConvertOptions",
    "import_midi",
    "import_midi_to_json",
    "apply_operations",
    "enhance_dict",
    "enhance_midi_file",
    "humanize",
    "quantize",
    "transpose",
    "set_instrument",
    "set_mix",
    "dynamics",
]

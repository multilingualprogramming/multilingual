#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Sonic projection of a polymodal program.

The sonic projection is a peer of the spatial projection. It takes the
modality-free semantic core and synthesizes a sonic seed manifest that a
WebAudio runtime can render. Frequency, amplitude, and routing are
derived from semantic fields (opcode, intensity, phase, channel) and
the per-opcode hints in the ontology.

Mapping summary:

- opcode      -> sonic role (source / modulator / bus / effect / trigger)
                and waveform / envelope hints from the ontology
- intensity   -> amplitude in [0, 1] and modulator depth
- phase       -> start offset (0..1 of one bar)
- channel     -> voice / output channel index
- entity index + channel -> pentatonic frequency
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.semantic_core import build_semantic_core

MANIFEST_KIND = "sonic-seed-v0"

# A pentatonic scale (A minor pentatonic) chosen because any subset of
# entities lands on a consonant chord. Frequencies in Hz.
PENTATONIC_HZ: tuple[float, ...] = (
    220.000,  # A3
    261.626,  # C4
    293.665,  # D4
    329.628,  # E4
    391.995,  # G4
    440.000,  # A4
    523.251,  # C5
    587.330,  # D5
    659.255,  # E5
    783.991,  # G5
)


def build_sonic_manifest(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return a validated sonic manifest."""
    core = build_semantic_core(source, language=language, source_path=source_path)
    voices = [_voice_from_semantic_entity(entity) for entity in core["entities"]]
    return {
        "kind": MANIFEST_KIND,
        "version": 0,
        "source_language": language,
        "source": source_path,
        "tempo_bpm": 96,
        "bar_seconds": 4.0,
        "voices": voices,
    }


def build_sonic_manifest_file(
    source_path: str | Path,
    output_path: str | Path,
    language: str = "en",
) -> dict[str, Any]:
    """Build and write a sonic manifest from a Multilingual source file."""
    src = Path(source_path)
    out = Path(output_path)
    manifest = build_sonic_manifest(
        src.read_text(encoding="utf-8"),
        language=language,
        source_path=str(src),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _voice_from_semantic_entity(entity: dict[str, Any]) -> dict[str, Any]:
    op = opcode_ontology.get(entity["opcode"])
    index = int(entity["index"])
    channel = int(entity["channel"])
    intensity = float(entity["intensity"])
    phase = float(entity["phase"])
    signal = float(entity["signal"])

    pitch_index = (index + channel * 3) % len(PENTATONIC_HZ)
    frequency = PENTATONIC_HZ[pitch_index]

    amplitude = max(0.0, min(1.0, intensity * 0.4 + signal * 0.1))
    if op.sonic.role == "bus":
        amplitude = 0.0  # buses are silent themselves
    elif op.sonic.role == "modulator":
        amplitude = max(0.0, min(1.0, intensity * 0.6))

    return {
        "index": index,
        "opcode": op.code,
        "name": op.name,
        "role": op.sonic.role,
        "waveform": op.sonic.waveform,
        "envelope": op.sonic.envelope,
        "frequency_hz": round(frequency, 3),
        "amplitude": round(amplitude, 4),
        "start_offset": round(phase % 1.0, 4),
        "channel": channel,
    }

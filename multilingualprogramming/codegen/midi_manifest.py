#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""MIDI projection of a polymodal program.

Peer of the linear / spatial / volumetric / sonic projections. Where
those projections describe continuous shapes (along 1/2/3 spatial axes
or in audio), MIDI describes the program as a sequence of discrete
events: note on/off, control change, program change, percussion hits.

This is the modality that stress-tests whether the ontology is
genuinely modality-free. If our opcode primitives only mapped cleanly
to continuous-shape projections, MIDI would be where that cracked --
because MIDI's contract is fundamentally event-flavored rather than
field-flavored. Each opcode commits to a MIDI role
(``note``, ``drum``, ``cc``, ``program``, ``bus``) via its
:class:`MidiHint`, and the projection here turns the semantic core
into a flat list of MIDI events ready for a piano-roll renderer or
Web MIDI output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.semantic_core import build_semantic_core

MANIFEST_KIND = "midi-seed-v0"


def build_midi_manifest(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return a validated MIDI manifest."""
    core = build_semantic_core(source, language=language, source_path=source_path)
    events = [_event_from_semantic_entity(entity) for entity in core["entities"]]
    return {
        "kind": MANIFEST_KIND,
        "version": 0,
        "source_language": language,
        "source": source_path,
        "tempo_bpm": 96,
        "bar_seconds": 4.0,
        "events": events,
        "relations": core["relations"],
    }


def build_midi_manifest_file(
    source_path: str | Path,
    output_path: str | Path,
    language: str = "en",
) -> dict[str, Any]:
    """Build and write a MIDI manifest from a Multilingual source file."""
    src = Path(source_path)
    out = Path(output_path)
    manifest = build_midi_manifest(
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


def _event_from_semantic_entity(entity: dict[str, Any]) -> dict[str, Any]:
    op = opcode_ontology.get(entity["opcode"])
    intensity = float(entity["intensity"])

    # Bus voices are silent under the forward MIDI projection just as
    # they are silent under sonic. The event is still emitted so peer
    # projections agree on entity count and ordering -- runtimes simply
    # do not transmit it.
    if op.midi.role == "bus":
        velocity = 0
    else:
        velocity = max(0, min(127, round(op.midi.velocity * intensity)))

    return {
        "index": int(entity["index"]),
        "opcode": op.code,
        "name": op.name,
        "role": op.midi.role,
        "pitch": op.midi.pitch,
        "velocity": velocity,
        "channel": int(entity["channel"]),
        "start_offset": round(float(entity["phase"]) % 1.0, 4),
    }

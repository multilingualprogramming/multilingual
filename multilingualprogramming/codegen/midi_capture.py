#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Inverse MIDI projection: observed MIDI events -> semantic core.

The forward MIDI projection emits identity labels for manifests, but a
real MIDI input stream does not carry ``opcode`` or ``name``. This
module recovers semantic identity from the observable MIDI fields the
ontology owns: role and pitch.

MIDI capture is deliberately partial:

- ``bus`` events are silent routing markers, not recoverable input.
- ``program`` events in the current ontology have base velocity 0, so
  intensity cannot be recovered.
- events whose velocity has clipped to 127 cannot recover the original
  intensity exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.semantic_core import CORE_KIND


@dataclass(frozen=True)
class ObservedMidiEvent:
    """A MIDI event as it would arrive from a MIDI input boundary."""

    index: int
    role: str
    pitch: int
    velocity: int
    channel: int
    start_offset: float


def _ontology_signature(op: opcode_ontology.Opcode) -> tuple[str, int]:
    return (op.midi.role, op.midi.pitch)


def invertible_opcodes() -> set[int]:
    """Opcodes whose identity can be recovered from MIDI observation."""
    signature_counts: dict[tuple[str, int], int] = {}
    for op in opcode_ontology.OPCODES:
        signature = _ontology_signature(op)
        signature_counts[signature] = signature_counts.get(signature, 0) + 1
    return {
        op.code
        for op in opcode_ontology.OPCODES
        if op.midi.role != "bus"
        and op.midi.velocity > 0
        and signature_counts[_ontology_signature(op)] == 1
    }


def observe_event(event: dict[str, Any]) -> ObservedMidiEvent:
    """Strip semantic identity labels from a forward-projected MIDI event."""
    return ObservedMidiEvent(
        index=int(event["index"]),
        role=str(event["role"]),
        pitch=int(event["pitch"]),
        velocity=int(event["velocity"]),
        channel=int(event["channel"]),
        start_offset=float(event["start_offset"]),
    )


def _opcode_from_observation(
    observed: ObservedMidiEvent,
) -> opcode_ontology.Opcode:
    signature = (observed.role, observed.pitch)
    matches = [
        op for op in opcode_ontology.OPCODES if _ontology_signature(op) == signature
    ]
    if not matches:
        raise ValueError(
            f"No ontology opcode matches MIDI observation {signature!r} "
            f"on event index {observed.index}"
        )
    if len(matches) > 1:
        names = ", ".join(op.name for op in matches)
        raise ValueError(
            f"MIDI observation {signature!r} on event index {observed.index} is "
            f"ambiguous: matches {names}."
        )
    op = matches[0]
    if op.midi.role == "bus":
        raise ValueError(
            f"MIDI event index {observed.index} resolves to bus opcode {op.name!r}; "
            "silent routing events are not recoverable authoring input."
        )
    if op.midi.velocity <= 0:
        raise ValueError(
            f"MIDI event index {observed.index} resolves to opcode {op.name!r} "
            "with zero base velocity; intensity cannot be recovered."
        )
    return op


def _intensity_from_velocity(
    op: opcode_ontology.Opcode,
    observed: ObservedMidiEvent,
) -> float:
    if not 0 <= observed.velocity <= 127:
        raise ValueError(
            f"MIDI event index {observed.index} velocity must be in 0..127"
        )
    if observed.velocity == 127:
        raise ValueError(
            f"MIDI event index {observed.index} is clipped at velocity 127; "
            "original intensity is lossy."
        )
    return observed.velocity / op.midi.velocity


def capture_semantic_core(
    observed: Iterable[ObservedMidiEvent],
    *,
    source_language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Invert observed MIDI events into a semantic-core manifest."""
    entities: list[dict[str, Any]] = []
    for event in observed:
        op = _opcode_from_observation(event)
        intensity = _intensity_from_velocity(op, event)
        entities.append(
            {
                "index": event.index,
                "opcode": op.code,
                "name": op.name,
                "intensity": intensity,
                "signal": 0.0,
                "phase": event.start_offset,
                "channel": event.channel,
            }
        )
    return {
        "kind": CORE_KIND,
        "version": 0,
        "source_language": source_language,
        "source": source_path,
        "ontology": [
            {"code": op.code, "name": op.name}
            for op in opcode_ontology.OPCODES
        ],
        "entities": entities,
        "relations": [],
    }

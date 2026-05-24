#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Inverse sonic projection: observation -> semantic core.

The forward sonic projection (``sonic_projection.py``) takes a
modality-free semantic core and synthesizes a sonic seed manifest. This
module is its architectural counterpart: it takes voices as they would
be observed at the modality boundary -- carrying only what a real audio
analyzer could recover (role, waveform, envelope, frequency, amplitude,
start offset, channel) -- and reconstructs a ``semantic-core-v0``
manifest from them.

The point of this module is to make the polymodal equivalence claim
falsifiable in the sonic direction. If the round trip
``core -> sonic -> observed -> captured-core`` does not preserve
semantic identity for opcodes the ontology says are invertible, the
projection has drifted.

Not every opcode is invertible from observation alone:

- Opcodes that share a ``(role, waveform, envelope)`` tuple in the
  ontology (currently split/merge, attract/repel,
  diffuse/stabilize/resonate) cannot be distinguished by ear and are
  excluded from :func:`invertible_opcodes`.
- ``bus`` voices are emitted silently (``amplitude == 0``) so their
  intensity cannot be recovered and they are also excluded.

For the remaining opcodes the inverse assumes ``signal == 0`` because
the forward amplitude formula
(``intensity * 0.4 + signal * 0.1`` for non-modulator non-bus voices)
is one equation in two unknowns. This matches the convention used by
the seed program at ``docs/browser/spatial-dynamics/program.multi`` and
is documented here rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.semantic_core import CORE_KIND


@dataclass(frozen=True)
class ObservedVoice:
    """A sonic voice as it would arrive from a real audio analyzer.

    Deliberately carries no ``opcode`` or ``name`` label: those are the
    semantic identity the inverse projection must recover.
    """

    index: int
    role: str
    waveform: str
    envelope: str
    frequency_hz: float
    amplitude: float
    start_offset: float
    channel: int


def _ontology_signature(op: opcode_ontology.Opcode) -> tuple[str, str, str]:
    return (op.sonic.role, op.sonic.waveform, op.sonic.envelope)


def invertible_opcodes() -> set[int]:
    """Opcodes whose semantic identity is recoverable from observation.

    An opcode is invertible iff its sonic hints
    ``(role, waveform, envelope)`` are unique across the ontology *and*
    its role is not ``bus`` (buses are silent under forward projection,
    so their intensity is unrecoverable).
    """
    signature_counts: dict[tuple[str, str, str], int] = {}
    for op in opcode_ontology.OPCODES:
        signature_counts[_ontology_signature(op)] = (
            signature_counts.get(_ontology_signature(op), 0) + 1
        )
    return {
        op.code
        for op in opcode_ontology.OPCODES
        if op.sonic.role != "bus" and signature_counts[_ontology_signature(op)] == 1
    }


def _opcode_from_observation(observed: ObservedVoice) -> opcode_ontology.Opcode:
    signature = (observed.role, observed.waveform, observed.envelope)
    matches = [
        op for op in opcode_ontology.OPCODES if _ontology_signature(op) == signature
    ]
    if not matches:
        raise ValueError(
            f"No ontology opcode matches observation {signature!r} "
            f"on voice index {observed.index}"
        )
    if len(matches) > 1:
        names = ", ".join(op.name for op in matches)
        raise ValueError(
            f"Observation {signature!r} on voice index {observed.index} is "
            f"ambiguous: matches {names}. Capture is undefined for shared "
            f"sonic signatures."
        )
    op = matches[0]
    if op.sonic.role == "bus":
        raise ValueError(
            f"Voice index {observed.index} resolves to bus opcode {op.name!r}; "
            f"intensity cannot be recovered from a silent voice."
        )
    return op


def observe_voice(voice: dict[str, Any]) -> ObservedVoice:
    """Strip identity labels from a forward-projected voice.

    Simulates what an audio analyzer at the modality boundary would
    actually have access to: no ``opcode``, no ``name``. Use this in
    tests to assert that the inverse projection recovers semantic
    identity from modality-observable fields alone.
    """
    return ObservedVoice(
        index=int(voice["index"]),
        role=str(voice["role"]),
        waveform=str(voice["waveform"]),
        envelope=str(voice["envelope"]),
        frequency_hz=float(voice["frequency_hz"]),
        amplitude=float(voice["amplitude"]),
        start_offset=float(voice["start_offset"]),
        channel=int(voice["channel"]),
    )


def _intensity_from_amplitude(op: opcode_ontology.Opcode, amplitude: float) -> float:
    # Mirrors the formulas in sonic_projection._voice_from_semantic_entity.
    # Assumes signal == 0 for non-modulator voices (documented in the
    # module docstring).
    if op.sonic.role == "modulator":
        return amplitude / 0.6
    return amplitude / 0.4


def capture_semantic_core(
    observed: Iterable[ObservedVoice],
    *,
    source_language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Invert a stream of observed voices into a semantic-core manifest.

    Raises ``ValueError`` if any observation is ambiguous or maps to an
    opcode the ontology marks as non-invertible.
    """
    entities: list[dict[str, Any]] = []
    for voice in observed:
        op = _opcode_from_observation(voice)
        intensity = _intensity_from_amplitude(op, voice.amplitude)
        entities.append(
            {
                "index": voice.index,
                "opcode": op.code,
                "name": op.name,
                "intensity": intensity,
                "signal": 0.0,
                "phase": voice.start_offset,
                "channel": voice.channel,
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

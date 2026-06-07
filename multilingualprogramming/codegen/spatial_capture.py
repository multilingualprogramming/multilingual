#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Inverse spatial projection: observed 2D marks -> semantic core.

The forward spatial projection (``spatial_manifest.py``) takes a
modality-free semantic core and produces a 2D manifest whose entities
carry the ontology's ``SpatialHint`` (shape, color) plus authoring
coordinates. This module is the architectural counterpart: it takes 2D
marks as they would be observed at the spatial authoring boundary --
the user has selected a shape from the palette, dropped it on the
canvas, dragged it, tuned intensity/phase via direct widgets -- and
reconstructs a ``semantic-core-v0`` manifest from them.

The point of this module is to make the polymodal equivalence claim
falsifiable in the spatial direction without routing edits through
generated text. The 2D runtime owns its own observation surface; that
surface produces ``ObservedSpatialMark`` records that this module
inverts back into the core.

Unlike sonic and MIDI capture, *every* ontology opcode is invertible
from spatial observation. The 12 spatial hints in
``opcode_ontology.OPCODES`` use 12 unique ``(shape, color)`` tuples
(``contain`` included), and an authoring surface has direct widget
access to intensity / signal / phase / channel rather than having to
infer them from a perceptual measurement. The capability contract on
``spatial-seed-v0`` declares ``inverse="exact"`` accordingly.

Stable entity identity:

- If an observation already carries an ``id`` (a manifest-loaded entity
  that the editor moved around), that id flows into the recovered core
  unchanged. This is what lets the captured semantic core remain
  identity-equivalent to the source under non-destructive edits.
- If an observation lacks an ``id`` (a newly authored entity that has
  no source row to anchor against), this module derives one from
  ``stable_entity_id(source_path, index)`` so the recovered manifest
  is still a well-formed ``semantic-core-v0``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.semantic_core import (
    CORE_KIND,
    stable_entity_id,
)


@dataclass(frozen=True)
class ObservedSpatialMark:  # pylint: disable=too-many-instance-attributes
    """A 2D mark as it would arrive from the spatial authoring boundary.

    Deliberately carries no ``opcode`` or ``name`` label: those are the
    semantic identity the inverse projection must recover from the
    ``(shape, color)`` tuple, which is what an authoring surface (or a
    perceiver) actually sees. ``id`` is optional: editors that loaded
    an entity from a manifest carry its id forward, while freshly
    authored entities have none until capture assigns one.
    """

    index: int
    shape: str
    color: str
    intensity: float
    signal: float
    phase: float
    channel: int
    id: str | None = field(default=None)


def _ontology_signature(op: opcode_ontology.Opcode) -> tuple[str, str]:
    return (op.spatial.shape, op.spatial.color)


def invertible_opcodes() -> set[int]:
    """Opcodes whose semantic identity is recoverable from a spatial mark.

    An opcode is invertible iff its spatial hints ``(shape, color)`` are
    unique across the ontology. Every spatial hint in the current
    ontology is unique (including ``contain``), so all 12 opcodes are
    invertible -- spatial is the strongest invertible modality.
    """
    signature_counts: dict[tuple[str, str], int] = {}
    for op in opcode_ontology.OPCODES:
        signature_counts[_ontology_signature(op)] = (
            signature_counts.get(_ontology_signature(op), 0) + 1
        )
    return {
        op.code
        for op in opcode_ontology.OPCODES
        if signature_counts[_ontology_signature(op)] == 1
    }


def _opcode_from_observation(observed: ObservedSpatialMark) -> opcode_ontology.Opcode:
    signature = (observed.shape, observed.color)
    matches = [
        op for op in opcode_ontology.OPCODES if _ontology_signature(op) == signature
    ]
    if not matches:
        raise ValueError(
            f"No ontology opcode matches spatial observation {signature!r} "
            f"on mark index {observed.index}"
        )
    if len(matches) > 1:
        names = ", ".join(op.name for op in matches)
        raise ValueError(
            f"Spatial observation {signature!r} on mark index {observed.index} is "
            f"ambiguous: matches {names}. Capture is undefined for shared "
            f"spatial signatures."
        )
    return matches[0]


def observe_mark(entity: dict[str, Any]) -> ObservedSpatialMark:
    """Strip identity labels from a forward-projected spatial entity.

    Simulates what a spatial authoring surface or a perceiver actually
    has at the modality boundary: ``shape`` and ``color`` instead of
    ``opcode`` / ``name``, plus the semantic fields the surface exposes
    as direct widgets. Use this in tests to assert that the inverse
    projection recovers semantic identity from modality-observable
    fields alone.
    """
    return ObservedSpatialMark(
        index=int(entity["index"]),
        shape=str(entity["shape"]),
        color=str(entity["color"]),
        intensity=float(entity["intensity"]),
        signal=float(entity["signal"]),
        phase=float(entity["phase"]),
        channel=int(entity["channel"]),
        id=entity.get("id"),
    )


def capture_semantic_core(
    observed: Iterable[ObservedSpatialMark],
    *,
    source_language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Invert observed spatial marks into a semantic-core manifest.

    Raises ``ValueError`` if any observation maps to an unknown or
    ambiguous ``(shape, color)`` signature.
    """
    entities: list[dict[str, Any]] = []
    for mark in observed:
        op = _opcode_from_observation(mark)
        entity_id = mark.id or stable_entity_id(source_path, mark.index)
        entities.append(
            {
                "id": entity_id,
                "index": mark.index,
                "opcode": op.code,
                "name": op.name,
                "intensity": mark.intensity,
                "signal": mark.signal,
                "phase": mark.phase,
                "channel": mark.channel,
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

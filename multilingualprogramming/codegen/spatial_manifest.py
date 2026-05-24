#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Spatial (2D) projection of a polymodal program.

Peer of the linear (1D), volumetric (3D), sonic, and (forthcoming)
MIDI projections. Takes the modality-free semantic core and produces
a 2D manifest: each entity becomes a positioned mark with shape and
color drawn from the ontology's :class:`SpatialHint`, plus the raw
coordinate hints (``x_ratio``, ``y_ratio``, ``radius``, ``vx``,
``vy``) that only the spatial runtime needs.

Spatial is the only projection whose authoring surface (``program.multi``)
carries coordinates directly. Other modalities derive position from
``index`` / ``channel`` / ``phase``. Even so, spatial now goes through
the semantic core so it sees relations (containment) and uses the
shared ontology hints, instead of redefining behavior codes and visual
hints in the runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.projection_capabilities import capability_contract
from multilingualprogramming.codegen.semantic_core import (
    SEED_ROW_ARITY,
    build_semantic_core,
    execute_seed,
)

MANIFEST_KIND = "spatial-seed-v0"
ENTITY_ARITY = SEED_ROW_ARITY


def build_spatial_manifest(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return a validated spatial manifest."""
    core = build_semantic_core(source, language=language, source_path=source_path)
    raw_rows = execute_seed(source, language=language, source_path=source_path)
    entities = [
        _entity_from_semantic(core_entity, raw_rows[core_entity["index"]])
        for core_entity in core["entities"]
    ]
    return {
        "kind": MANIFEST_KIND,
        "version": 0,
        "source_language": language,
        "source": source_path,
        "capabilities": capability_contract(
            projection=MANIFEST_KIND,
            preserves=["id", "opcode", "intensity", "signal", "phase", "channel"],
            derived=[],
            lossy=[],
            ambiguous=[],
            inverse="view-only",
        ),
        "entities": entities,
        "relations": core["relations"],
    }


def build_spatial_manifest_file(
    source_path: str | Path,
    output_path: str | Path,
    language: str = "en",
) -> dict[str, Any]:
    """Build and write a spatial manifest from a Multilingual source file."""
    src = Path(source_path)
    out = Path(output_path)
    manifest = build_spatial_manifest(
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


def _entity_from_semantic(
    core_entity: dict[str, Any], raw_row: list[Any]
) -> dict[str, Any]:
    if not isinstance(raw_row, list):
        raise ValueError(
            f"Spatial entity {core_entity['index']} must be a list"
        )
    if len(raw_row) != ENTITY_ARITY:
        raise ValueError(
            f"Spatial entity {core_entity['index']} must have {ENTITY_ARITY} fields"
        )
    try:
        x_ratio = float(raw_row[1])
        y_ratio = float(raw_row[2])
        radius = float(raw_row[3])
        vx = float(raw_row[6])
        vy = float(raw_row[7])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Spatial entity {core_entity['index']} contains non-numeric coordinate fields"
        ) from exc

    if not 0.0 <= x_ratio <= 1.0:
        raise ValueError(
            f"Spatial entity {core_entity['index']} x ratio must be between 0 and 1"
        )
    if not 0.0 <= y_ratio <= 1.0:
        raise ValueError(
            f"Spatial entity {core_entity['index']} y ratio must be between 0 and 1"
        )
    if radius < 0.0:
        raise ValueError(
            f"Spatial entity {core_entity['index']} radius must be nonnegative"
        )

    op = opcode_ontology.get(core_entity["opcode"])
    return {
        "id": core_entity["id"],
        "index": core_entity["index"],
        "opcode": op.code,
        "name": op.name,
        "shape": op.spatial.shape,
        "color": op.spatial.color,
        "x_ratio": x_ratio,
        "y_ratio": y_ratio,
        "radius": radius,
        "intensity": core_entity["intensity"],
        "signal": core_entity["signal"],
        "vx": vx,
        "vy": vy,
        "phase": core_entity["phase"],
        "channel": core_entity["channel"],
    }

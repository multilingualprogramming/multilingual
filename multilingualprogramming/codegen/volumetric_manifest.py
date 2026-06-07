#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Volumetric (3D) projection of a polymodal program.

Peer of the linear (1D), spatial (2D), and sonic projections. Takes
the modality-free semantic core and produces a three-dimensional
manifest: each entity becomes a positioned primitive in 3-space. The
projection deliberately invents its own coordinates from the semantic
fields rather than expecting the core to carry them; the core stays
modality-free.

Coordinate mapping (left to the runtime so the manifest stays thin):

- z is exposed as the per-mark `z` field, derived from ``phase`` -- a
  position along the temporal/depth axis.
- x is derived by the runtime from ``index`` (entity ordering along a
  horizontal lane).
- y is derived by the runtime from ``channel`` (vertical track).

This is the dimensionality peer that closes the 1D / 2D / 3D loop the
user flagged on 2026-05-24. Volumetric primitive names (point, cloud,
cone, helix, shell, ...) deliberately do not overlap with the linear
or spatial vocabularies, so adding a new opcode forces explicit
3D-native naming rather than reuse.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.projection_capabilities import capability_contract
from multilingualprogramming.codegen.semantic_core import build_semantic_core

MANIFEST_KIND = "volumetric-seed-v0"


def build_volumetric_manifest(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return a validated volumetric manifest."""
    core = build_semantic_core(source, language=language, source_path=source_path)
    marks = [_mark_from_semantic_entity(entity) for entity in core["entities"]]
    return {
        "kind": MANIFEST_KIND,
        "version": 0,
        "source_language": language,
        "source": source_path,
        "capabilities": capability_contract(
            projection=MANIFEST_KIND,
            preserves=["id", "opcode", "intensity", "phase", "channel"],
            derived=[],
            lossy=["signal"],
            ambiguous=[],
            inverse="view-only",
        ),
        "tempo_bpm": 96,
        "bar_seconds": 4.0,
        "marks": marks,
    }


def build_volumetric_manifest_file(
    source_path: str | Path,
    output_path: str | Path,
    language: str = "en",
) -> dict[str, Any]:
    """Build and write a volumetric manifest from a Multilingual source file."""
    src = Path(source_path)
    out = Path(output_path)
    manifest = build_volumetric_manifest(
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


def _mark_from_semantic_entity(entity: dict[str, Any]) -> dict[str, Any]:
    op = opcode_ontology.get(entity["opcode"])
    return {
        "id": entity["id"],
        "index": int(entity["index"]),
        "opcode": op.code,
        "name": op.name,
        "primitive": op.volumetric.primitive,
        "color": op.volumetric.color,
        "z": round(float(entity["phase"]) % 1.0, 4),
        "intensity": round(float(entity["intensity"]), 4),
        "channel": int(entity["channel"]),
    }

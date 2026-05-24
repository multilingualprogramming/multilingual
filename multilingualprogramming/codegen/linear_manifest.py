#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Linear (1D timeline) projection of a polymodal program.

Peer of the spatial (2D) and sonic projections. Takes the modality-free
semantic core and produces a one-dimensional manifest: each entity
becomes a positioned mark along a single axis. Phase determines the
position; opcode determines the glyph and color.

Adding 1D as a peer projection (rather than a parameterization of the
2D spatial projection) is deliberate. The 1D rendering primitives
(dot, segment, pulse, ramp, wave, fork, join, band, shift, double)
do not generalize from 2D shapes -- "ring" and "membrane" have no
natural 1D analog. Peer projections force the equivalence test to
exercise the dimensionality axis rather than silently treating
"spatial" as a monolith.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.projection_capabilities import capability_contract
from multilingualprogramming.codegen.semantic_core import build_semantic_core

MANIFEST_KIND = "linear-seed-v0"


def build_linear_manifest(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return a validated linear manifest."""
    core = build_semantic_core(source, language=language, source_path=source_path)
    marks = [_mark_from_semantic_entity(entity) for entity in core["entities"]]
    return {
        "kind": MANIFEST_KIND,
        "version": 0,
        "source_language": language,
        "source": source_path,
        "capabilities": capability_contract(
            projection=MANIFEST_KIND,
            preserves=["opcode", "intensity", "phase", "channel"],
            derived=[],
            lossy=["signal"],
            ambiguous=[],
            inverse="view-only",
        ),
        "tempo_bpm": 96,
        "bar_seconds": 4.0,
        "marks": marks,
    }


def build_linear_manifest_file(
    source_path: str | Path,
    output_path: str | Path,
    language: str = "en",
) -> dict[str, Any]:
    """Build and write a linear manifest from a Multilingual source file."""
    src = Path(source_path)
    out = Path(output_path)
    manifest = build_linear_manifest(
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
        "index": int(entity["index"]),
        "opcode": op.code,
        "name": op.name,
        "glyph": op.linear.glyph,
        "color": op.linear.color,
        "position": round(float(entity["phase"]) % 1.0, 4),
        "intensity": round(float(entity["intensity"]), 4),
        "channel": int(entity["channel"]),
    }

#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Modality-free semantic core for polymodal computation.

The semantic core is the canonical representation of a Multilingual
polymodal program. It deliberately carries no coordinates, no pixels,
no frequencies, no forces. Those concerns belong to per-modality
projections (spatial, sonic, haptic, ...).

A semantic core entity captures only:

- opcode:    stable behavior code from the ontology
- intensity: behavior strength (>= 0)
- signal:    initial activation (>= 0)
- phase:     phase offset in [0, 1) for cyclic behavior
- channel:   integer routing/grouping tag

Containment, coupling, and other relations are deliberately left for
future authoring surfaces. The current seed encodes container *roles*
via the `contain` opcode; *which* entities a membrane contains is a
per-modality runtime question (it depends on geometry in the spatial
projection, on bus routing in the sonic projection, and so on).
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.codegen.runtime_builtins import make_exec_globals

CORE_KIND = "semantic-core-v0"
SEED_ROW_ARITY = 10


def execute_seed(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> list[list[Any]]:
    """Execute Multilingual source and return its raw `seed` value."""
    python_source = ProgramExecutor(
        language=language,
        check_semantics=False,
    ).transpile(source)
    namespace = make_exec_globals(language)

    with contextlib.redirect_stdout(io.StringIO()):
        # Polymodal seeds are trusted Multilingual programs compiled by this package.
        exec(  # pylint: disable=exec-used
            compile(python_source, source_path or "<polymodal>", "exec"), namespace
        )

    if "seed" not in namespace:
        raise ValueError("Polymodal program must define `seed`")

    seed = namespace["seed"]
    if not isinstance(seed, list):
        raise ValueError("Polymodal `seed` must be a list")
    return seed


def build_semantic_core(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return a modality-free semantic core."""
    seed = execute_seed(source, language=language, source_path=source_path)
    entities = [_entity_from_seed_row(row, index) for index, row in enumerate(seed)]
    return {
        "kind": CORE_KIND,
        "version": 0,
        "source_language": language,
        "source": source_path,
        "ontology": [
            {"code": op.code, "name": op.name}
            for op in opcode_ontology.OPCODES
        ],
        "entities": entities,
        "relations": [],
    }


def build_semantic_core_file(
    source_path: str | Path,
    output_path: str | Path,
    language: str = "en",
) -> dict[str, Any]:
    """Build and write a semantic core manifest to disk as JSON."""
    src = Path(source_path)
    out = Path(output_path)
    core = build_semantic_core(
        src.read_text(encoding="utf-8"),
        language=language,
        source_path=str(src),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(core, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return core


def _entity_from_seed_row(row: Any, index: int) -> dict[str, Any]:
    if not isinstance(row, list):
        raise ValueError(f"Polymodal entity {index} must be a list")
    if len(row) != SEED_ROW_ARITY:
        raise ValueError(
            f"Polymodal entity {index} must have {SEED_ROW_ARITY} fields"
        )
    try:
        opcode = int(row[0])
        intensity = float(row[4])
        signal = float(row[5])
        phase = float(row[8])
        channel = int(row[9])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Polymodal entity {index} contains non-numeric semantic fields"
        ) from exc

    if opcode not in opcode_ontology.known_codes():
        raise ValueError(f"Polymodal entity {index} has unknown opcode {opcode}")
    if intensity < 0.0:
        raise ValueError(f"Polymodal entity {index} intensity must be nonnegative")
    if signal < 0.0:
        raise ValueError(f"Polymodal entity {index} signal must be nonnegative")

    return {
        "index": index,
        "opcode": opcode,
        "name": opcode_ontology.get(opcode).name,
        "intensity": intensity,
        "signal": signal,
        "phase": phase,
        "channel": channel,
    }

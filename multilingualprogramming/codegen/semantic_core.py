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

Relations are how the semantic core records structure between
entities (containment, coupling, temporal ordering). Until a
source-level authoring surface exists, the core derives them from
existing entity fields so that *every* peer projection sees the same
structural facts -- otherwise spatial-2D and volumetric-3D could
silently disagree on which entity contains which, breaking the
cross-modal coherence claim.

Currently inferred:

- Containment: each ``contain``-opcode entity on channel C contains
  every non-``contain`` entity on channel C. Coupling and temporal
  ordering will be added once the source language gains explicit
  syntax for them.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen import opcode_ontology
from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.codegen.runtime_builtins import make_exec_globals

CORE_KIND = "semantic-core-v0"
SEED_ROW_ARITY = 10
CONTAIN_OPCODE = 11
RELATION_CONTAINMENT = "containment"
ENTITY_ID_PREFIX = "ent_"


def stable_entity_id(source_path: str, index: int) -> str:
    """Return a deterministic stable identifier for an entity.

    Identity is derived from the source path plus the entity's index in
    the seed program. The hash gives surfaces a stable handle they can
    keep across edits, reorderings, or modality round-trips, while the
    derivation stays purely a function of program structure -- two
    rebuilds of the same source produce the same IDs without state.

    Indexes alone are not enough: when an authoring surface inserts or
    deletes an entity, every downstream index shifts and identity is
    lost. IDs remain stable.
    """
    digest = hashlib.sha256(f"{source_path}|{index}".encode("utf-8")).hexdigest()
    return f"{ENTITY_ID_PREFIX}{digest[:8]}"


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
    entities = [
        _entity_from_seed_row(row, index, source_path)
        for index, row in enumerate(seed)
    ]
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
        "relations": _derive_relations(entities),
    }


def _derive_relations(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive structural relations between entities.

    Each ``contain`` entity on channel C is treated as a container of
    the non-``contain`` entities on channel C. Multiple containers on
    the same channel produce overlapping containment relations -- that
    is deliberate, since a program may genuinely nest membranes.
    Containers whose channel holds no other members produce no
    relation (an empty membrane is not load-bearing structure).
    """
    members_by_channel: dict[int, list[int]] = {}
    for entity in entities:
        if entity["opcode"] == CONTAIN_OPCODE:
            continue
        members_by_channel.setdefault(entity["channel"], []).append(entity["index"])

    relations: list[dict[str, Any]] = []
    for entity in entities:
        if entity["opcode"] != CONTAIN_OPCODE:
            continue
        members = members_by_channel.get(entity["channel"], [])
        if not members:
            continue
        relations.append({
            "kind": RELATION_CONTAINMENT,
            "container": entity["index"],
            "members": list(members),
        })
    return relations


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


def _entity_from_seed_row(row: Any, index: int, source_path: str) -> dict[str, Any]:
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
        "id": stable_entity_id(source_path, index),
        "index": index,
        "opcode": opcode,
        "name": opcode_ontology.get(opcode).name,
        "intensity": intensity,
        "signal": signal,
        "phase": phase,
        "channel": channel,
    }

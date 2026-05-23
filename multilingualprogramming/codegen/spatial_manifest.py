#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Build JSON manifests from Multilingual spatial seed programs."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from typing import Any

from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.codegen.runtime_builtins import make_exec_globals

MANIFEST_KIND = "spatial-seed-v0"
ENTITY_ARITY = 10
KNOWN_BEHAVIORS = set(range(1, 13))


def build_spatial_manifest(
    source: str,
    language: str = "en",
    source_path: str = "",
) -> dict[str, Any]:
    """Execute Multilingual source and return a validated spatial manifest."""
    python_source = ProgramExecutor(
        language=language,
        check_semantics=False,
    ).transpile(source)
    namespace = make_exec_globals(language)

    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(python_source, source_path or "<spatial>", "exec"), namespace)

    if "seed" not in namespace:
        raise ValueError("Spatial program must define `seed`")

    entities = normalize_entities(namespace["seed"])
    return {
        "kind": MANIFEST_KIND,
        "version": 0,
        "source_language": language,
        "source": source_path,
        "entities": entities,
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


def normalize_entities(seed: Any) -> list[list[float | int]]:
    """Validate and normalize spatial entity rows."""
    if not isinstance(seed, list):
        raise ValueError("Spatial `seed` must be a list")

    entities = []
    for index, entity in enumerate(seed):
        if not isinstance(entity, list):
            raise ValueError(f"Spatial entity {index} must be a list")
        if len(entity) != ENTITY_ARITY:
            raise ValueError(
                f"Spatial entity {index} must have {ENTITY_ARITY} fields"
            )
        entities.append(_normalize_entity(entity, index))
    return entities


def _normalize_entity(entity: list[Any], index: int) -> list[float | int]:
    try:
        behavior = int(entity[0])
        x_ratio = float(entity[1])
        y_ratio = float(entity[2])
        radius = float(entity[3])
        intensity = float(entity[4])
        signal = float(entity[5])
        vx = float(entity[6])
        vy = float(entity[7])
        phase = float(entity[8])
        channel = int(entity[9])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Spatial entity {index} contains non-numeric fields") from exc

    if behavior not in KNOWN_BEHAVIORS:
        raise ValueError(f"Spatial entity {index} has unknown behavior {behavior}")
    if not 0.0 <= x_ratio <= 1.0:
        raise ValueError(f"Spatial entity {index} x ratio must be between 0 and 1")
    if not 0.0 <= y_ratio <= 1.0:
        raise ValueError(f"Spatial entity {index} y ratio must be between 0 and 1")
    if radius < 0.0:
        raise ValueError(f"Spatial entity {index} radius must be nonnegative")
    if intensity < 0.0:
        raise ValueError(f"Spatial entity {index} intensity must be nonnegative")
    if signal < 0.0:
        raise ValueError(f"Spatial entity {index} signal must be nonnegative")

    return [
        behavior,
        x_ratio,
        y_ratio,
        radius,
        intensity,
        signal,
        vx,
        vy,
        phase,
        channel,
    ]

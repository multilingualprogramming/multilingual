#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of a *static* (Tier-0) semantic-core-v1 program.

Every other v1 projection assumes a topology of its own: ``process_projection``
and ``process_field_projection`` read a lattice, ``process_sequence_projection``
reads a sequence, ``process_graph_projection`` reads a graph. A **migrated v0
core** (see ``process_migration``) has none of those -- it is a static structure
under a discrete topology, "a v0 program is a v1 program with an empty rule set
and a single-step schedule." So until now a v0 manifest could only be rendered
by the v0 peer projections (``spatial_manifest`` and friends), and the claim
"even v0 flows through the one v1 projection path" was unproven.

This module closes that gap. It is the static, value-rich sibling of
``process_field_projection``: where a field locus carries one ``value`` at a
lattice coordinate, a v0 entity is a *record* of several scalars (opcode,
intensity, signal, phase, ...) with no spatial coordinate at all. So the
projection derives a placement from the two integer fields a v0 entity already
carries -- its ``index`` (a linear position) and its ``channel`` (a lane) -- and
carries the rest of the record verbatim, so the inverse rebuilds each entity
exactly. No field is reinterpreted: ``phase`` does not become an angle and
``intensity`` does not become an amplitude; placement uses only the two fields
that already *are* positions, exactly as the migration refused to invent any.

There is still one source of motion -- ``process_core.run`` -- even though a
static program never moves: running it yields a trajectory of identical frames,
which is precisely the point (a snapshot is a degenerate process, and it travels
the same stepper as Game of Life). The program is Tier 0, "invertible
everywhere," so the contract is always exact; there is no viewport, because a
static structure has no unbounded extent to window. The module names no specific
system -- it reads the generic ``index``/``channel`` placement fields and treats
everything else as opaque payload.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_capabilities, process_core

STATIC_SPATIAL_ANIM_KIND = "static-spatial-anim-v1"
STATIC_SONIC_ANIM_KIND = "static-sonic-anim-v1"

# The two integer fields a v0 entity carries that already *are* positions: a
# linear index along one axis and a channel (lane) along the other. Placement
# reads only these, so nothing else is reinterpreted as a coordinate.
_PLACEMENT_X = "index"
_PLACEMENT_Y = "channel"


def animate(core: dict[str, Any], steps: int = 0) -> list[dict[str, Any]]:
    """Advance the program with the one shared stepper, returning frames.

    A static program does not move, so every frame equals the first; running it
    through the same ``process_core.run`` as any other program is the proof that
    v0 needs no special engine path. ``steps`` defaults to ``0`` -- a single
    frame -- since further frames are identical.
    """
    return process_core.run(core, steps)


def _require_static(core: dict[str, Any]) -> None:
    """Validate that ``core`` is a static (Tier-0) v1 program with placed loci."""
    if core.get("kind") != process_core.CORE_KIND:
        raise ValueError(f"expected a {process_core.CORE_KIND} manifest")
    if core["schedule"].get("kind") != process_core.SCHEDULE_STATIC:
        raise ValueError("static projection requires a static schedule (a Tier-0 program)")
    for rec in core["state"]["loci"]:
        if _PLACEMENT_X not in rec or _PLACEMENT_Y not in rec:
            raise ValueError(
                f"static projection needs {_PLACEMENT_X!r} and {_PLACEMENT_Y!r} on every locus"
            )


def _payload(rec: dict[str, Any]) -> dict[str, Any]:
    """The locus record minus the two placement fields (carried verbatim)."""
    return {k: v for k, v in rec.items() if k not in (_PLACEMENT_X, _PLACEMENT_Y)}


def _entity_of(x: int, y: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a locus record from its placement and carried payload."""
    return {**payload, _PLACEMENT_X: x, _PLACEMENT_Y: y}


# --------------------------------------------------------------------------
# Spatial modality: a frame is a set of marks, one per entity, placed at
# ``(index, channel)`` and carrying the rest of the record -- so the inverse
# recovers every entity exactly.
# --------------------------------------------------------------------------

def to_spatial_frame(frame: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Project one static core frame into a 2D arrangement of placed records."""
    _require_static(frame)
    return {
        "kind": STATIC_SPATIAL_ANIM_KIND,
        "frame": index,
        "marks": [
            {"x": rec[_PLACEMENT_X], "y": rec[_PLACEMENT_Y], "payload": _payload(rec)}
            for rec in frame["state"]["loci"]
        ],
    }


def to_spatial_animation(trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project a whole trajectory into a static spatial animation."""
    return [to_spatial_frame(frame, i) for i, frame in enumerate(trajectory)]


def entities_from_spatial_frame(frame: dict[str, Any]) -> list[dict[str, Any]]:
    """Inverse: recover the entity records a spatial frame represents.

    Sorted by the linear ``index`` so the recovered order is stable and matches
    the migrated core's own locus order.
    """
    return sorted(
        (_entity_of(mark["x"], mark["y"], mark["payload"]) for mark in frame["marks"]),
        key=lambda rec: rec[_PLACEMENT_X],
    )


# --------------------------------------------------------------------------
# Sonic modality: a frame is a set of voices, one per entity. The linear
# ``index`` becomes the step (when the voice sounds) and the ``channel``
# becomes the pitch row (which lane it sings in) -- a bijection -- and the rest
# of the record rides on the voice, so the inverse recovers the exact entity.
# --------------------------------------------------------------------------

def to_sonic_frame(frame: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Project one static core frame into a sonic arrangement of voices."""
    _require_static(frame)
    return {
        "kind": STATIC_SONIC_ANIM_KIND,
        "frame": index,
        "voices": [
            {"step": rec[_PLACEMENT_X], "pitch_row": rec[_PLACEMENT_Y], "payload": _payload(rec)}
            for rec in frame["state"]["loci"]
        ],
    }


def to_sonic_animation(trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project a whole trajectory into a static sonic animation."""
    return [to_sonic_frame(frame, i) for i, frame in enumerate(trajectory)]


def entities_from_sonic_frame(frame: dict[str, Any]) -> list[dict[str, Any]]:
    """Inverse: recover the entity records a sonic frame represents."""
    return sorted(
        (
            _entity_of(voice["step"], voice["pitch_row"], voice["payload"])
            for voice in frame["voices"]
        ),
        key=lambda rec: rec[_PLACEMENT_X],
    )


# --------------------------------------------------------------------------
# Capability contract: a static structure is Tier 0, "invertible everywhere,"
# so the contract is unconditionally exact. There is no viewport -- a snapshot
# has no unbounded extent to window -- so unlike the lattice projections nothing
# can be clipped, and the inverse is never partial.
# --------------------------------------------------------------------------

def projection_capabilities(
    projection: str,
    trajectory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Declare a static projection's capabilities for a trajectory.

    Always exact: a migrated v0 core preserves every entity record, so both
    modalities round-trip the full structure with no loss and no ambiguity.
    """
    return process_capabilities.projection_contract(
        projection=projection,
        core=trajectory[0],
        preserves=["entity-records"],
        inverse="exact",
    )


def spatial_animation_manifest(trajectory: list[dict[str, Any]]) -> dict[str, Any]:
    """A full static spatial animation: declared capabilities + frames."""
    return {
        "kind": STATIC_SPATIAL_ANIM_KIND,
        "capabilities": projection_capabilities(STATIC_SPATIAL_ANIM_KIND, trajectory),
        "frames": to_spatial_animation(trajectory),
    }


def sonic_animation_manifest(trajectory: list[dict[str, Any]]) -> dict[str, Any]:
    """A full static sonic animation: declared capabilities + frames."""
    return {
        "kind": STATIC_SONIC_ANIM_KIND,
        "capabilities": projection_capabilities(STATIC_SONIC_ANIM_KIND, trajectory),
        "frames": to_sonic_animation(trajectory),
    }

#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of an animated *multi-state field* (semantic-core-v1).

``process_projection`` projects the simplest lattice -- a boolean mask, where a
cell is alive or dead -- so a live cell becomes a single spatial mark / sonic
voice and the inverse needs only recover *where* the live cells are. A
heterogeneous field (a several-species ecology, a reaction-diffusion lattice)
carries a *value* at every locus, not just on/off, so the projection must
preserve that value to stay invertible. This module is the value-aware sibling
of ``process_projection``, mirroring its viewport/contract machinery exactly:

- spatial: every locus in the viewport becomes a mark carrying its ``(x, y,
  value)``, so the inverse recovers the full field, value and all;
- sonic: every locus becomes a voice whose column is the step, whose row is the
  pitch row, and which carries its ``value`` as a voice attribute (the way a v0
  sonic voice carried channel/velocity) -- again exactly invertible.

There is still exactly one source of motion (``process_core.run``); both
projections are pure functions of the trajectory and neither steps the program.
Like ``process_projection`` the inverse level is *derived* from viewport
coverage: a window holding the whole field recovers it exactly; a smaller
window is honestly lossy on the clipped cells. The module names no specific
system -- the caller chooses which record field is the cell's value.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_capabilities, process_core

FIELD_SPATIAL_ANIM_KIND = "field-spatial-anim-v1"
FIELD_SONIC_ANIM_KIND = "field-sonic-anim-v1"

_DEFAULT_FIELD = "state"


def animate(core: dict[str, Any], steps: int) -> list[dict[str, Any]]:
    """Advance the program with the one shared stepper, returning frames.

    The only call that produces motion; every projection below consumes its
    output without stepping anything itself.
    """
    return process_core.run(core, steps)


# --------------------------------------------------------------------------
# Viewport: a finite window into the lattice. A fully-populated field lives on
# a bounded lattice, so its natural viewport is the lattice's own extent, which
# contains every locus -- the projection is then exact. A caller may pass a
# smaller window; cells outside it are clipped (present in the core, absent from
# the projection), which the capability contract reports as honest loss.
# --------------------------------------------------------------------------

def finite_viewport(core: dict[str, Any]) -> dict[str, int]:
    """The viewport covering a bounded lattice exactly (origin at 0, 0)."""
    topology = core["topology"]
    if topology.get("kind") != process_core.TOPOLOGY_LATTICE:
        raise ValueError("field projection requires a lattice topology")
    if topology.get("extent") == process_core.LATTICE_EXTENT_INFINITE:
        raise ValueError("infinite topology has no implicit extent; pass a viewport")
    return {"x0": 0, "y0": 0, "width": topology["width"], "height": topology["height"]}


def _resolve_viewport(
    target: dict[str, Any] | list[dict[str, Any]],
    viewport: dict[str, int] | None,
) -> dict[str, int]:
    if viewport is not None:
        return viewport
    sample = target[0] if isinstance(target, list) else target
    return finite_viewport(sample)


def _in_viewport(x: int, y: int, vp: dict[str, int]) -> bool:
    return (
        vp["x0"] <= x < vp["x0"] + vp["width"]
        and vp["y0"] <= y < vp["y0"] + vp["height"]
    )


# --------------------------------------------------------------------------
# Spatial modality: a frame is a set of marks, one per locus in the viewport,
# each carrying global coordinates and the cell's value -- so the inverse is
# exact for everything the window shows.
# --------------------------------------------------------------------------

def to_spatial_frame(
    frame: dict[str, Any],
    index: int,
    field: str = _DEFAULT_FIELD,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Project one core frame into a 2D value field within a viewport."""
    vp = _resolve_viewport(frame, viewport)
    cells = process_core.field_cells(frame, field)
    return {
        "kind": FIELD_SPATIAL_ANIM_KIND,
        "frame": index,
        "field": field,
        "x0": vp["x0"],
        "y0": vp["y0"],
        "width": vp["width"],
        "height": vp["height"],
        "marks": [
            {"x": x, "y": y, "value": value}
            for x, y, value in cells
            if _in_viewport(x, y, vp)
        ],
    }


def to_spatial_animation(
    trajectory: list[dict[str, Any]],
    field: str = _DEFAULT_FIELD,
    viewport: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a spatial field animation through one viewport."""
    vp = _resolve_viewport(trajectory, viewport)
    return [to_spatial_frame(frame, i, field, vp) for i, frame in enumerate(trajectory)]


def field_from_spatial_frame(frame: dict[str, Any]) -> list[tuple[int, int, Any]]:
    """Inverse: recover the ``(x, y, value)`` field a spatial frame represents."""
    return sorted((mark["x"], mark["y"], mark["value"]) for mark in frame["marks"])


# --------------------------------------------------------------------------
# Sonic modality: a frame is a set of voices, one per locus in the viewport.
# The column becomes the step, the row becomes the pitch row -- a bijection
# within the window -- and the cell's value rides on the voice (as channel /
# timbre would), so the inverse recovers the exact global cell *and* its value.
# --------------------------------------------------------------------------

def to_sonic_frame(
    frame: dict[str, Any],
    index: int,
    field: str = _DEFAULT_FIELD,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Project one core frame into a sonic field of voices within a viewport."""
    vp = _resolve_viewport(frame, viewport)
    top = vp["y0"] + vp["height"] - 1  # highest row -> highest pitch
    cells = process_core.field_cells(frame, field)
    return {
        "kind": FIELD_SONIC_ANIM_KIND,
        "frame": index,
        "field": field,
        "x0": vp["x0"],
        "y0": vp["y0"],
        "steps": vp["width"],
        "pitch_rows": vp["height"],
        "voices": [
            {"step": x - vp["x0"], "pitch_row": top - y, "value": value}
            for x, y, value in cells
            if _in_viewport(x, y, vp)
        ],
    }


def to_sonic_animation(
    trajectory: list[dict[str, Any]],
    field: str = _DEFAULT_FIELD,
    viewport: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a sonic field animation through one viewport."""
    vp = _resolve_viewport(trajectory, viewport)
    return [to_sonic_frame(frame, i, field, vp) for i, frame in enumerate(trajectory)]


def field_from_sonic_frame(frame: dict[str, Any]) -> list[tuple[int, int, Any]]:
    """Inverse: recover the ``(x, y, value)`` field a sonic frame represents."""
    top = frame["y0"] + frame["pitch_rows"] - 1
    return sorted(
        (voice["step"] + frame["x0"], top - voice["pitch_row"], voice["value"])
        for voice in frame["voices"]
    )


# --------------------------------------------------------------------------
# Capability contracts: each animation declares what it preserves and loses,
# derived from the viewport rather than asserted by hand. A viewport holding
# every locus recovers the field exactly; one that clips is honestly lossy on
# "cells outside viewport." The contract carries the program's tier too.
# --------------------------------------------------------------------------

def _viewport_covers(
    trajectory: list[dict[str, Any]],
    field: str,
    viewport: dict[str, int],
) -> bool:
    """Whether every locus in the whole trajectory falls in the viewport."""
    return all(
        _in_viewport(x, y, viewport)
        for frame in trajectory
        for x, y, _ in process_core.field_cells(frame, field)
    )


def projection_capabilities(
    projection: str,
    trajectory: list[dict[str, Any]],
    field: str = _DEFAULT_FIELD,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Declare a field projection's capabilities for a trajectory through a viewport.

    The inverse level is *derived*, not labelled: exact when the viewport holds
    every locus, partial (lossy on clipped cells) when it does not.
    """
    vp = _resolve_viewport(trajectory, viewport)
    covers = _viewport_covers(trajectory, field, vp)
    return process_capabilities.projection_contract(
        projection=projection,
        core=trajectory[0],
        preserves=["field-cells-within-viewport"],
        lossy=[] if covers else ["cells-outside-viewport"],
        inverse="exact" if covers else "partial",
        viewport=vp,
    )


def spatial_animation_manifest(
    trajectory: list[dict[str, Any]],
    field: str = _DEFAULT_FIELD,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """A full spatial field animation: declared capabilities + viewport + frames."""
    vp = _resolve_viewport(trajectory, viewport)
    return {
        "kind": FIELD_SPATIAL_ANIM_KIND,
        "field": field,
        "capabilities": projection_capabilities(FIELD_SPATIAL_ANIM_KIND, trajectory, field, vp),
        "viewport": vp,
        "frames": to_spatial_animation(trajectory, field, vp),
    }


def sonic_animation_manifest(
    trajectory: list[dict[str, Any]],
    field: str = _DEFAULT_FIELD,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """A full sonic field animation: declared capabilities + viewport + frames."""
    vp = _resolve_viewport(trajectory, viewport)
    return {
        "kind": FIELD_SONIC_ANIM_KIND,
        "field": field,
        "capabilities": projection_capabilities(FIELD_SONIC_ANIM_KIND, trajectory, field, vp),
        "viewport": vp,
        "frames": to_sonic_animation(trajectory, field, vp),
    }

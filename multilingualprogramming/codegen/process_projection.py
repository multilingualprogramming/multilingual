#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of an animated semantic-core-v1 process.

``semantic_core`` (v0) projects a *static* structure into peer modalities,
and ``polymodal_equivalence_test`` proves those peers agree on frame 0.
``process_core`` (v1) added the missing piece -- a single modality-free
stepper that advances ⟨State, Topology, Rule, Schedule⟩ over time. This
module closes the loop the research doc calls load-bearing:

> the stepper that advances the tuple must be specified once in the
> modality-free core and drive each runtime -- never hand-written per
> modality -- else two runtimes evolve the same program differently and
> cross-modal equivalence dies the instant the program animates.

So there is exactly one source of motion here: ``process_core.run`` produces
a trajectory of full v1 manifests, and every modality is a *pure projection
of that trajectory*. No modality steps anything itself. The forward
projections below turn each frame into a spatial mark set and a sonic voice
set; the inverse recoverers read each modality's frame back to the live-cell
set it represents. If both inverses recover the same cells the core reports
active, for every frame, the animation is genuinely polymodal.

This first step covers the lattice / synchronous slice (so it can animate
Game of Life and any other outer-totalistic program). Both projections are
deliberately *exactly* invertible: a live cell at ``(x, y)`` maps to a
spatial mark at ``(x, y)`` and to a sonic voice whose ``step`` is the column
and whose ``pitch_row`` is the row, so the inverse is a bijection and makes
no perceptual guess. Lossy modalities would declare a capability contract
instead (see ``projection_capabilities``); these two claim exact recovery.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_capabilities, process_core

SPATIAL_ANIM_KIND = "spatial-anim-v1"
SONIC_ANIM_KIND = "sonic-anim-v1"

_ACTIVE_FIELD = "alive"


def animate(core: dict[str, Any], steps: int) -> list[dict[str, Any]]:
    """Advance the program with the one shared stepper, returning frames.

    This is the *only* call that produces motion. Every projection below
    consumes its output; none of them steps the program independently.
    """
    return process_core.run(core, steps)


# --------------------------------------------------------------------------
# Viewport: a finite window into the lattice. A bounded lattice projects
# through its own extent with no loss. An *unbounded* (infinite-topology,
# open-population) program has no extent to project, so a finite surface can
# only show a window -- exactly like a camera on an infinite plane. Cells
# outside the window are clipped: present in the core, absent from the
# projection. That is honest lossiness (a capability contract would mark
# "preserves: cells in viewport; lossy: cells outside"), not a broken claim.
# --------------------------------------------------------------------------

def finite_viewport(core: dict[str, Any]) -> dict[str, int]:
    """The viewport covering a bounded lattice exactly (origin at 0, 0)."""
    topology = core["topology"]
    if topology.get("extent") == process_core.LATTICE_EXTENT_INFINITE:
        raise ValueError("infinite topology has no implicit extent; pass a viewport")
    return {"x0": 0, "y0": 0, "width": topology["width"], "height": topology["height"]}


def bounding_box(
    trajectory: list[dict[str, Any]],
    margin: int = 1,
) -> dict[str, int]:
    """A viewport that contains every live cell across a whole trajectory.

    Stable for the length of the animation so the window does not jitter as
    the pattern moves -- a glider simply travels across a fixed frame.
    """
    cells = [
        cell
        for frame in trajectory
        for cell in process_core.active_cells(frame, _ACTIVE_FIELD)
    ]
    if not cells:
        return {"x0": 0, "y0": 0, "width": 1, "height": 1}
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    x0, y0 = min(xs) - margin, min(ys) - margin
    return {
        "x0": x0,
        "y0": y0,
        "width": max(xs) - min(xs) + 1 + 2 * margin,
        "height": max(ys) - min(ys) + 1 + 2 * margin,
    }


def _resolve_viewport(
    target: dict[str, Any] | list[dict[str, Any]],
    viewport: dict[str, int] | None,
) -> dict[str, int]:
    if viewport is not None:
        return viewport
    sample = target[0] if isinstance(target, list) else target
    if sample["topology"].get("extent") == process_core.LATTICE_EXTENT_INFINITE:
        frames = target if isinstance(target, list) else [target]
        return bounding_box(frames)
    return finite_viewport(sample)


def _in_viewport(x: int, y: int, vp: dict[str, int]) -> bool:
    return (
        vp["x0"] <= x < vp["x0"] + vp["width"]
        and vp["y0"] <= y < vp["y0"] + vp["height"]
    )


# --------------------------------------------------------------------------
# Spatial modality: a frame is a set of marks at live-cell coordinates that
# fall inside the viewport. Marks carry global coordinates, so the inverse
# is exact for everything the window shows.
# --------------------------------------------------------------------------

def to_spatial_frame(
    frame: dict[str, Any],
    index: int,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Project one core frame into a 2D spatial frame within a viewport."""
    vp = _resolve_viewport(frame, viewport)
    cells = process_core.active_cells(frame, _ACTIVE_FIELD)
    return {
        "kind": SPATIAL_ANIM_KIND,
        "frame": index,
        "x0": vp["x0"],
        "y0": vp["y0"],
        "width": vp["width"],
        "height": vp["height"],
        "marks": [{"x": x, "y": y} for x, y in cells if _in_viewport(x, y, vp)],
    }


def to_spatial_animation(
    trajectory: list[dict[str, Any]],
    viewport: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a spatial animation through one viewport."""
    vp = _resolve_viewport(trajectory, viewport)
    return [to_spatial_frame(frame, i, vp) for i, frame in enumerate(trajectory)]


def live_cells_from_spatial_frame(frame: dict[str, Any]) -> list[tuple[int, int]]:
    """Inverse: recover the live-cell set a spatial frame represents."""
    return sorted((mark["x"], mark["y"]) for mark in frame["marks"])


# --------------------------------------------------------------------------
# Sonic modality: a frame is a set of voices, one per live cell in the
# viewport. The column becomes the rhythmic step, the row becomes the pitch
# row -- a bijection within the window, so the inverse recovers the exact
# global cell with no perceptual inference.
# --------------------------------------------------------------------------

def to_sonic_frame(
    frame: dict[str, Any],
    index: int,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Project one core frame into a sonic frame of voices within a viewport."""
    vp = _resolve_viewport(frame, viewport)
    top = vp["y0"] + vp["height"] - 1  # highest row -> highest pitch
    cells = process_core.active_cells(frame, _ACTIVE_FIELD)
    return {
        "kind": SONIC_ANIM_KIND,
        "frame": index,
        "x0": vp["x0"],
        "y0": vp["y0"],
        "steps": vp["width"],
        "pitch_rows": vp["height"],
        "voices": [
            {"step": x - vp["x0"], "pitch_row": top - y}
            for x, y in cells
            if _in_viewport(x, y, vp)
        ],
    }


def to_sonic_animation(
    trajectory: list[dict[str, Any]],
    viewport: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a sonic animation through one viewport."""
    vp = _resolve_viewport(trajectory, viewport)
    return [to_sonic_frame(frame, i, vp) for i, frame in enumerate(trajectory)]


def live_cells_from_sonic_frame(frame: dict[str, Any]) -> list[tuple[int, int]]:
    """Inverse: recover the live-cell set a sonic frame represents."""
    top = frame["y0"] + frame["pitch_rows"] - 1
    return sorted(
        (voice["step"] + frame["x0"], top - voice["pitch_row"])
        for voice in frame["voices"]
    )


# --------------------------------------------------------------------------
# Capability contracts: each animation declares what it preserves and loses,
# computed from the viewport rather than asserted by hand. A viewport that
# contains every live cell across the run recovers the program exactly; one
# that clips is honestly lossy on "cells outside viewport." The contract also
# carries the program's expressiveness tier (see process_capabilities).
# --------------------------------------------------------------------------

def _viewport_covers(
    trajectory: list[dict[str, Any]],
    viewport: dict[str, int],
) -> bool:
    """Whether every live cell in the whole trajectory falls in the viewport."""
    return all(
        _in_viewport(x, y, viewport)
        for frame in trajectory
        for x, y in process_core.active_cells(frame, _ACTIVE_FIELD)
    )


def projection_capabilities(
    projection: str,
    trajectory: list[dict[str, Any]],
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Declare a projection's capabilities for a trajectory through a viewport.

    The inverse level is *derived*, not labelled: exact when the viewport
    shows the whole program, partial (lossy on clipped cells) when it does
    not. This is the honesty frontier made machine-checkable.
    """
    vp = _resolve_viewport(trajectory, viewport)
    covers = _viewport_covers(trajectory, vp)
    return process_capabilities.projection_contract(
        projection=projection,
        core=trajectory[0],
        preserves=["live-cells-within-viewport"],
        lossy=[] if covers else ["cells-outside-viewport"],
        inverse="exact" if covers else "partial",
        viewport=vp,
    )


def spatial_animation_manifest(
    trajectory: list[dict[str, Any]],
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """A full spatial animation: declared capabilities + viewport + frames."""
    vp = _resolve_viewport(trajectory, viewport)
    return {
        "kind": SPATIAL_ANIM_KIND,
        "capabilities": projection_capabilities(SPATIAL_ANIM_KIND, trajectory, vp),
        "viewport": vp,
        "frames": to_spatial_animation(trajectory, vp),
    }


def sonic_animation_manifest(
    trajectory: list[dict[str, Any]],
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """A full sonic animation: declared capabilities + viewport + frames."""
    vp = _resolve_viewport(trajectory, viewport)
    return {
        "kind": SONIC_ANIM_KIND,
        "capabilities": projection_capabilities(SONIC_ANIM_KIND, trajectory, vp),
        "viewport": vp,
        "frames": to_sonic_animation(trajectory, vp),
    }

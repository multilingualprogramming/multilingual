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

from multilingualprogramming.codegen import process_core

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
# Spatial modality: a frame is a set of marks at live-cell coordinates.
# --------------------------------------------------------------------------

def to_spatial_frame(frame: dict[str, Any], index: int) -> dict[str, Any]:
    """Project one core frame into a 2D spatial frame."""
    topology = frame["topology"]
    cells = process_core.active_cells(frame, _ACTIVE_FIELD)
    return {
        "kind": SPATIAL_ANIM_KIND,
        "frame": index,
        "width": topology["width"],
        "height": topology["height"],
        "marks": [{"x": x, "y": y} for x, y in cells],
    }


def to_spatial_animation(trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project a whole trajectory into a spatial animation."""
    return [to_spatial_frame(frame, i) for i, frame in enumerate(trajectory)]


def live_cells_from_spatial_frame(frame: dict[str, Any]) -> list[tuple[int, int]]:
    """Inverse: recover the live-cell set a spatial frame represents."""
    return sorted((mark["x"], mark["y"]) for mark in frame["marks"])


# --------------------------------------------------------------------------
# Sonic modality: a frame is a set of voices, one per live cell. The column
# becomes the rhythmic step, the row becomes the pitch row -- a bijection,
# so the inverse recovers the exact cell with no perceptual inference.
# --------------------------------------------------------------------------

def to_sonic_frame(frame: dict[str, Any], index: int) -> dict[str, Any]:
    """Project one core frame into a sonic frame of voices."""
    topology = frame["topology"]
    height = topology["height"]
    cells = process_core.active_cells(frame, _ACTIVE_FIELD)
    return {
        "kind": SONIC_ANIM_KIND,
        "frame": index,
        "steps": topology["width"],
        "pitch_rows": height,
        # Pitch ascends going up the lattice (row 0 at the bottom), the
        # convention a piano roll or staff would use.
        "voices": [
            {"step": x, "pitch_row": (height - 1 - y)}
            for x, y in cells
        ],
    }


def to_sonic_animation(trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project a whole trajectory into a sonic animation."""
    return [to_sonic_frame(frame, i) for i, frame in enumerate(trajectory)]


def live_cells_from_sonic_frame(frame: dict[str, Any]) -> list[tuple[int, int]]:
    """Inverse: recover the live-cell set a sonic frame represents."""
    height = frame["pitch_rows"]
    return sorted(
        (voice["step"], height - 1 - voice["pitch_row"])
        for voice in frame["voices"]
    )

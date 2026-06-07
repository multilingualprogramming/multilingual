#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of an animated *sequence* (generative) process.

``process_projection`` covers the lattice / synchronous slice -- it animates
Game of Life and other outer-totalistic programs. This module is its
generative sibling: it projects a sequence-topology core (an L-system / string
rewriting program) frame by frame into peer modalities, so the generative axis
is polymodal end-to-end just like the lattice axis is.

The discipline is identical to ``process_projection`` and the research doc's
load-bearing rule: there is exactly one source of motion. ``animate`` delegates
to the single shared ``process_core.run`` stepper; every modality below is a
*pure projection of that trajectory*, and none steps the program itself.

A sequence frame is an ordered word of symbols. The pitch axis is the
**alphabet** -- the sorted distinct symbols across the whole run, stable so the
mapping does not jitter as the word grows (the generative analogue of
``process_projection``'s viewport for an unbounded lattice). Each symbol at
position ``i`` projects to a spatial mark at ``(i, row)`` and to a sonic voice
whose ``step`` is ``i`` and whose ``pitch_row`` is ``row``, where ``row`` is the
symbol's index in the alphabet. Both maps are exact bijections within the
alphabet, so the inverse recovers the exact word with no perceptual guess --
spatial-recovered == sonic-recovered == ``process_core.sequence_symbols``. A
caller may pass a partial alphabet (a window on the symbol set); symbols outside
it are clipped, which is honest, contract-declared loss, never invented.

This is deliberately a *generic* layout (a piano-roll of position x symbol), not
turtle graphics: turtle interpretation (``F``=forward, ``+``=turn, ...) is a
specific program's reading of its symbols and would bake a system into the
projection. Like the engine, the projection names no system.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_capabilities, process_core

SEQ_SPATIAL_ANIM_KIND = "sequence-spatial-anim-v1"
SEQ_SONIC_ANIM_KIND = "sequence-sonic-anim-v1"

_SYMBOL_FIELD = "symbol"


def animate(core: dict[str, Any], steps: int) -> list[dict[str, Any]]:
    """Advance the generative program with the one shared stepper.

    The *only* call that produces motion. Every projection below consumes its
    output; none of them steps the program independently.
    """
    return process_core.run(core, steps)


# --------------------------------------------------------------------------
# Alphabet: the pitch axis. A sequence has no fixed extent (a generative rule
# grows it without bound), but its set of distinct symbols is small and stable.
# The alphabet plays the role the viewport plays for a lattice: it is the
# finite window the modalities lay the word out against. Derived from the whole
# trajectory by default so the row of a given symbol never moves between frames.
# --------------------------------------------------------------------------

def sequence_alphabet(trajectory: list[dict[str, Any]]) -> list[Any]:
    """The sorted distinct symbols across every frame of a trajectory."""
    symbols = {
        symbol
        for frame in trajectory
        for symbol in process_core.sequence_symbols(frame, _SYMBOL_FIELD)
    }
    return sorted(symbols)


def _resolve_alphabet(
    target: dict[str, Any] | list[dict[str, Any]],
    alphabet: list[Any] | None,
) -> list[Any]:
    if alphabet is not None:
        return list(alphabet)
    frames = target if isinstance(target, list) else [target]
    return sequence_alphabet(frames)


# --------------------------------------------------------------------------
# Spatial modality: a frame is a set of marks, one per symbol that falls in the
# alphabet, at (position, alphabet-row). Marks carry the position and the
# alphabet, so the inverse recovers the exact ordered word.
# --------------------------------------------------------------------------

def to_spatial_frame(
    frame: dict[str, Any],
    index: int,
    alphabet: list[Any] | None = None,
) -> dict[str, Any]:
    """Project one sequence frame into a 2D spatial frame over an alphabet."""
    alpha = _resolve_alphabet(frame, alphabet)
    row = {symbol: i for i, symbol in enumerate(alpha)}
    symbols = process_core.sequence_symbols(frame, _SYMBOL_FIELD)
    return {
        "kind": SEQ_SPATIAL_ANIM_KIND,
        "frame": index,
        "alphabet": list(alpha),
        "length": len(symbols),
        "marks": [
            {"x": position, "y": row[symbol]}
            for position, symbol in enumerate(symbols)
            if symbol in row
        ],
    }


def to_spatial_animation(
    trajectory: list[dict[str, Any]],
    alphabet: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a spatial animation over one alphabet."""
    alpha = _resolve_alphabet(trajectory, alphabet)
    return [to_spatial_frame(frame, i, alpha) for i, frame in enumerate(trajectory)]


def symbols_from_spatial_frame(frame: dict[str, Any]) -> list[Any]:
    """Inverse: recover the ordered word a spatial frame represents."""
    alpha = frame["alphabet"]
    return [
        alpha[mark["y"]]
        for mark in sorted(frame["marks"], key=lambda m: m["x"])
    ]


# --------------------------------------------------------------------------
# Sonic modality: a frame is a melody, one voice per symbol in the alphabet.
# The position becomes the rhythmic step, the alphabet row becomes the pitch
# row -- a bijection within the alphabet, so the inverse recovers the exact
# word with no perceptual inference.
# --------------------------------------------------------------------------

def to_sonic_frame(
    frame: dict[str, Any],
    index: int,
    alphabet: list[Any] | None = None,
) -> dict[str, Any]:
    """Project one sequence frame into a sonic frame of voices over an alphabet."""
    alpha = _resolve_alphabet(frame, alphabet)
    row = {symbol: i for i, symbol in enumerate(alpha)}
    symbols = process_core.sequence_symbols(frame, _SYMBOL_FIELD)
    return {
        "kind": SEQ_SONIC_ANIM_KIND,
        "frame": index,
        "alphabet": list(alpha),
        "pitch_rows": len(alpha),
        "steps": len(symbols),
        "voices": [
            {"step": position, "pitch_row": row[symbol]}
            for position, symbol in enumerate(symbols)
            if symbol in row
        ],
    }


def to_sonic_animation(
    trajectory: list[dict[str, Any]],
    alphabet: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a sonic animation over one alphabet."""
    alpha = _resolve_alphabet(trajectory, alphabet)
    return [to_sonic_frame(frame, i, alpha) for i, frame in enumerate(trajectory)]


def symbols_from_sonic_frame(frame: dict[str, Any]) -> list[Any]:
    """Inverse: recover the ordered word a sonic frame represents."""
    alpha = frame["alphabet"]
    return [
        alpha[voice["pitch_row"]]
        for voice in sorted(frame["voices"], key=lambda v: v["step"])
    ]


# --------------------------------------------------------------------------
# Capability contracts: derived from alphabet coverage, not asserted. An
# alphabet holding every symbol in the run recovers the word exactly; a partial
# alphabet is honestly lossy on the symbols it omits.
# --------------------------------------------------------------------------

def _alphabet_covers(
    trajectory: list[dict[str, Any]],
    alphabet: list[Any],
) -> bool:
    """Whether every symbol in the whole trajectory is in the alphabet."""
    alpha = set(alphabet)
    return all(
        symbol in alpha
        for frame in trajectory
        for symbol in process_core.sequence_symbols(frame, _SYMBOL_FIELD)
    )


def projection_capabilities(
    projection: str,
    trajectory: list[dict[str, Any]],
    alphabet: list[Any] | None = None,
) -> dict[str, Any]:
    """Declare a sequence projection's capabilities for a trajectory.

    The inverse level is *derived*: exact when the alphabet holds every symbol
    in the run, partial (lossy on omitted symbols) when it does not.
    """
    alpha = _resolve_alphabet(trajectory, alphabet)
    covers = _alphabet_covers(trajectory, alpha)
    contract = process_capabilities.projection_contract(
        projection=projection,
        core=trajectory[0],
        preserves=["symbols-in-alphabet"],
        lossy=[] if covers else ["symbols-outside-alphabet"],
        inverse="exact" if covers else "partial",
    )
    contract["alphabet"] = list(alpha)
    return contract


def spatial_animation_manifest(
    trajectory: list[dict[str, Any]],
    alphabet: list[Any] | None = None,
) -> dict[str, Any]:
    """A full sequence spatial animation: capabilities + alphabet + frames."""
    alpha = _resolve_alphabet(trajectory, alphabet)
    return {
        "kind": SEQ_SPATIAL_ANIM_KIND,
        "capabilities": projection_capabilities(SEQ_SPATIAL_ANIM_KIND, trajectory, alpha),
        "alphabet": list(alpha),
        "frames": to_spatial_animation(trajectory, alpha),
    }


def sonic_animation_manifest(
    trajectory: list[dict[str, Any]],
    alphabet: list[Any] | None = None,
) -> dict[str, Any]:
    """A full sequence sonic animation: capabilities + alphabet + frames."""
    alpha = _resolve_alphabet(trajectory, alphabet)
    return {
        "kind": SEQ_SONIC_ANIM_KIND,
        "capabilities": projection_capabilities(SEQ_SONIC_ANIM_KIND, trajectory, alpha),
        "alphabet": list(alpha),
        "frames": to_sonic_animation(trajectory, alpha),
    }

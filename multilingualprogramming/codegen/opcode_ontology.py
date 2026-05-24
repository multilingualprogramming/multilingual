#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Shared opcode ontology for polymodal computation.

The ontology is the single source of truth for the stable behavioral
primitives used by the semantic core and every modality projection
(spatial, sonic, and future ones). Each opcode entry carries a stable
integer ID, a canonical name, and per-modality realization hints.

Adding a new primitive means adding one row here. Both the Python
projections and the JS runtimes read from this ontology so they cannot
drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class SonicHint:
    """How an opcode realizes in the sonic modality."""

    role: str  # source | modulator | bus | effect | trigger
    waveform: str = "sine"  # sine | triangle | sawtooth | square | noise
    envelope: str = "sustained"  # sustained | percussive | swelling | tremolo


@dataclass(frozen=True)
class SpatialHint:
    """How an opcode realizes in the 2D spatial modality."""

    shape: str
    color: str


@dataclass(frozen=True)
class Opcode:
    """A stable polymodal behavior primitive."""

    code: int
    name: str
    description: str
    sonic: SonicHint
    spatial: SpatialHint


OPCODES: tuple[Opcode, ...] = (
    Opcode(
        code=1, name="emit", description="Produce signal over time.",
        sonic=SonicHint(role="source", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="source", color="#de3c4b"),
    ),
    Opcode(
        code=2, name="diffuse", description="Equalize signal with local neighbors.",
        sonic=SonicHint(role="effect", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="ring", color="#3a86ff"),
    ),
    Opcode(
        code=3, name="attract", description="Pull nearby entities through proximity.",
        sonic=SonicHint(role="modulator", waveform="triangle", envelope="swelling"),
        spatial=SpatialHint(shape="up", color="#2d6a4f"),
    ),
    Opcode(
        code=4, name="repel", description="Push nearby entities away.",
        sonic=SonicHint(role="modulator", waveform="triangle", envelope="swelling"),
        spatial=SpatialHint(shape="down", color="#f77f00"),
    ),
    Opcode(
        code=5, name="stabilize", description="Dampen transient activation.",
        sonic=SonicHint(role="effect", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="square", color="#6c757d"),
    ),
    Opcode(
        code=6, name="oscillate", description="Produce periodic signal.",
        sonic=SonicHint(role="modulator", waveform="sine", envelope="tremolo"),
        spatial=SpatialHint(shape="phase", color="#8338ec"),
    ),
    Opcode(
        code=7, name="transform", description="Convert nearby signal into local signal.",
        sonic=SonicHint(role="effect", waveform="triangle", envelope="sustained"),
        spatial=SpatialHint(shape="diamond", color="#00a896"),
    ),
    Opcode(
        code=8, name="resonate", description="Amplify through phase alignment.",
        sonic=SonicHint(role="effect", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="double", color="#ffbe0b"),
    ),
    Opcode(
        code=9, name="split", description="Divide activation into propagating entities.",
        sonic=SonicHint(role="trigger", waveform="square", envelope="percussive"),
        spatial=SpatialHint(shape="split", color="#fb5607"),
    ),
    Opcode(
        code=10, name="merge", description="Combine nearby activations.",
        sonic=SonicHint(role="trigger", waveform="square", envelope="percussive"),
        spatial=SpatialHint(shape="merge", color="#7209b7"),
    ),
    Opcode(
        code=11, name="contain", description="Create a local membrane or boundary.",
        sonic=SonicHint(role="bus", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="membrane", color="#252422"),
    ),
    Opcode(
        code=12, name="propagate", description="Move activation through space.",
        sonic=SonicHint(role="source", waveform="sawtooth", envelope="percussive"),
        spatial=SpatialHint(shape="arrow", color="#0077b6"),
    ),
)


_BY_CODE: dict[int, Opcode] = {op.code: op for op in OPCODES}
_BY_NAME: dict[str, Opcode] = {op.name: op for op in OPCODES}


def known_codes() -> set[int]:
    """Return the set of stable opcode integers."""
    return set(_BY_CODE.keys())


def get(code: int) -> Opcode:
    """Return the opcode entry for a stable integer code."""
    if code not in _BY_CODE:
        raise ValueError(f"Unknown opcode {code}")
    return _BY_CODE[code]


def get_by_name(name: str) -> Opcode:
    """Return the opcode entry for its canonical name."""
    if name not in _BY_NAME:
        raise ValueError(f"Unknown opcode name {name!r}")
    return _BY_NAME[name]


def to_json_table() -> list[dict]:
    """Serialize the ontology to a plain list for cross-runtime consumption."""
    return [
        {
            "code": op.code,
            "name": op.name,
            "description": op.description,
            "sonic": {
                "role": op.sonic.role,
                "waveform": op.sonic.waveform,
                "envelope": op.sonic.envelope,
            },
            "spatial": {
                "shape": op.spatial.shape,
                "color": op.spatial.color,
            },
        }
        for op in OPCODES
    ]


def codes_for_names(names: Iterable[str]) -> list[int]:
    """Helper to convert a list of opcode names to their stable integers."""
    return [get_by_name(name).code for name in names]

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

import json
from dataclasses import dataclass
from pathlib import Path
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
class LinearHint:
    """How an opcode realizes in the 1D linear (timeline) modality.

    Distinct from SpatialHint because the 1D rendering primitives do not
    generalize from 2D shapes -- a "ring" or "membrane" has no natural
    1D analog. The 1D glyph vocabulary describes marks along a single
    axis: a dot, a horizontal segment, a vertical pulse, a wavy ribbon,
    a ramp, a fork, etc.
    """

    glyph: str  # dot | segment | pulse | wave | ramp | fall | fork | join | band | shift | double
    color: str


@dataclass(frozen=True)
class VolumetricHint:
    """How an opcode realizes in the 3D volumetric modality.

    Distinct from SpatialHint (2D) and LinearHint (1D). The 3D
    primitives describe shapes that live natively in three-space and
    have no 2D or 1D analog -- a "shell" is concentric 3D surfaces, a
    "helix" is a 3D coil, a "cell" is an enclosing 3D volume. Adding
    primitives to this vocabulary forces the equivalence test to
    exercise the dimensionality axis without falling back on 2D names.
    """

    # point | cloud | cone | burst | cube | helix | twist | shell | branch | funnel | cell | flow
    primitive: str
    color: str


@dataclass(frozen=True)
class MidiHint:
    """How an opcode realizes in the MIDI modality.

    Discrete-event peer of the continuous-shape projections. Each
    opcode maps to a MIDI role (``note``, ``drum``, ``cc``,
    ``program``, ``bus``) plus a base value: a MIDI note number for
    note/drum roles, a CC number for cc roles, a program number for
    program roles, and 0 for bus. Velocity is the peak velocity that
    intensity scales against (0-127).
    """

    role: str  # note | drum | cc | program | bus
    pitch: int  # 0-127 base value (note number / CC number / program number)
    velocity: int  # 0-127 peak velocity


@dataclass(frozen=True)
class Opcode:  # pylint: disable=too-many-instance-attributes
    """A stable polymodal behavior primitive."""

    code: int
    name: str
    description: str
    sonic: SonicHint
    spatial: SpatialHint
    linear: LinearHint
    volumetric: VolumetricHint
    midi: MidiHint


OPCODES: tuple[Opcode, ...] = (
    Opcode(
        code=1, name="emit", description="Produce signal over time.",
        sonic=SonicHint(role="source", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="source", color="#de3c4b"),
        linear=LinearHint(glyph="dot", color="#de3c4b"),
        volumetric=VolumetricHint(primitive="point", color="#de3c4b"),
        midi=MidiHint(role="note", pitch=69, velocity=96),  # A4
    ),
    Opcode(
        code=2, name="diffuse", description="Equalize signal with local neighbors.",
        sonic=SonicHint(role="effect", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="ring", color="#3a86ff"),
        linear=LinearHint(glyph="band", color="#3a86ff"),
        volumetric=VolumetricHint(primitive="cloud", color="#3a86ff"),
        midi=MidiHint(role="cc", pitch=91, velocity=100),  # CC 91 reverb send
    ),
    Opcode(
        code=3, name="attract", description="Pull nearby entities through proximity.",
        sonic=SonicHint(role="modulator", waveform="triangle", envelope="swelling"),
        spatial=SpatialHint(shape="up", color="#2d6a4f"),
        linear=LinearHint(glyph="ramp", color="#2d6a4f"),
        volumetric=VolumetricHint(primitive="cone", color="#2d6a4f"),
        midi=MidiHint(role="cc", pitch=1, velocity=110),  # CC 1 mod wheel (rising)
    ),
    Opcode(
        code=4, name="repel", description="Push nearby entities away.",
        sonic=SonicHint(role="modulator", waveform="triangle", envelope="swelling"),
        spatial=SpatialHint(shape="down", color="#f77f00"),
        linear=LinearHint(glyph="fall", color="#f77f00"),
        volumetric=VolumetricHint(primitive="burst", color="#f77f00"),
        midi=MidiHint(role="cc", pitch=2, velocity=110),  # CC 2 breath (falling)
    ),
    Opcode(
        code=5, name="stabilize", description="Dampen transient activation.",
        sonic=SonicHint(role="effect", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="square", color="#6c757d"),
        linear=LinearHint(glyph="segment", color="#6c757d"),
        volumetric=VolumetricHint(primitive="cube", color="#6c757d"),
        midi=MidiHint(role="cc", pitch=11, velocity=80),  # CC 11 expression
    ),
    Opcode(
        code=6, name="oscillate", description="Produce periodic signal.",
        sonic=SonicHint(role="modulator", waveform="sine", envelope="tremolo"),
        spatial=SpatialHint(shape="phase", color="#8338ec"),
        linear=LinearHint(glyph="wave", color="#8338ec"),
        volumetric=VolumetricHint(primitive="helix", color="#8338ec"),
        midi=MidiHint(role="note", pitch=64, velocity=92),  # E4 (oscillating)
    ),
    Opcode(
        code=7, name="transform", description="Convert nearby signal into local signal.",
        sonic=SonicHint(role="effect", waveform="triangle", envelope="sustained"),
        spatial=SpatialHint(shape="diamond", color="#00a896"),
        linear=LinearHint(glyph="double", color="#00a896"),
        volumetric=VolumetricHint(primitive="twist", color="#00a896"),
        midi=MidiHint(role="program", pitch=8, velocity=0),  # program 8 (celesta)
    ),
    Opcode(
        code=8, name="resonate", description="Amplify through phase alignment.",
        sonic=SonicHint(role="effect", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="double", color="#ffbe0b"),
        linear=LinearHint(glyph="pulse", color="#ffbe0b"),
        volumetric=VolumetricHint(primitive="shell", color="#ffbe0b"),
        midi=MidiHint(role="cc", pitch=93, velocity=100),  # CC 93 chorus depth
    ),
    Opcode(
        code=9, name="split", description="Divide activation into propagating entities.",
        sonic=SonicHint(role="trigger", waveform="square", envelope="percussive"),
        spatial=SpatialHint(shape="split", color="#fb5607"),
        linear=LinearHint(glyph="fork", color="#fb5607"),
        volumetric=VolumetricHint(primitive="branch", color="#fb5607"),
        midi=MidiHint(role="drum", pitch=36, velocity=110),  # kick drum (GM)
    ),
    Opcode(
        code=10, name="merge", description="Combine nearby activations.",
        sonic=SonicHint(role="trigger", waveform="square", envelope="percussive"),
        spatial=SpatialHint(shape="merge", color="#7209b7"),
        linear=LinearHint(glyph="join", color="#7209b7"),
        volumetric=VolumetricHint(primitive="funnel", color="#7209b7"),
        midi=MidiHint(role="drum", pitch=38, velocity=110),  # snare (GM)
    ),
    Opcode(
        code=11, name="contain", description="Create a local membrane or boundary.",
        sonic=SonicHint(role="bus", waveform="sine", envelope="sustained"),
        spatial=SpatialHint(shape="membrane", color="#252422"),
        linear=LinearHint(glyph="band", color="#252422"),
        volumetric=VolumetricHint(primitive="cell", color="#252422"),
        midi=MidiHint(role="bus", pitch=0, velocity=0),  # silent (contain routes only)
    ),
    Opcode(
        code=12, name="propagate", description="Move activation through space.",
        sonic=SonicHint(role="source", waveform="sawtooth", envelope="percussive"),
        spatial=SpatialHint(shape="arrow", color="#0077b6"),
        linear=LinearHint(glyph="shift", color="#0077b6"),
        volumetric=VolumetricHint(primitive="flow", color="#0077b6"),
        midi=MidiHint(role="note", pitch=74, velocity=104),  # D5 (propagating, staccato)
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
            "linear": {
                "glyph": op.linear.glyph,
                "color": op.linear.color,
            },
            "volumetric": {
                "primitive": op.volumetric.primitive,
                "color": op.volumetric.color,
            },
            "midi": {
                "role": op.midi.role,
                "pitch": op.midi.pitch,
                "velocity": op.midi.velocity,
            },
        }
        for op in OPCODES
    ]


def codes_for_names(names: Iterable[str]) -> list[int]:
    """Helper to convert a list of opcode names to their stable integers."""
    return [get_by_name(name).code for name in names]


ONTOLOGY_KIND = "opcode-ontology-v0"


def build_ontology_manifest() -> dict:
    """Return a self-describing ontology manifest for cross-runtime use."""
    return {
        "kind": ONTOLOGY_KIND,
        "version": 0,
        "opcodes": to_json_table(),
    }


def write_ontology_manifest(output_path: str | Path) -> dict:
    """Write the ontology manifest as JSON for browser runtimes to fetch."""
    manifest = build_ontology_manifest()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest

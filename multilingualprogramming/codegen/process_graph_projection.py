#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of an animated *graph* process (semantic-core-v1).

``process_field_projection`` projects a lattice field, keyed by coordinate;
``process_sequence_projection`` projects a generated word, keyed by position in
an alphabet. This module is their graph sibling: it projects a graph-topology
core -- a network whose nodes carry state -- frame by frame into peer
modalities, so the graph axis is polymodal too.

The discipline is the research doc's load-bearing rule, identical to the others:
there is exactly one source of motion. ``animate`` delegates to the single
shared ``process_core.run`` stepper, and every modality below is a *pure
projection of that trajectory*; none steps the program.

A graph's fundamental index is the **node**, not a position -- which is the whole
point of the graph topology (adjacency is the wiring, not the geometry). So the
**node set** -- the sorted distinct node ids across the run -- plays the role the
viewport plays for a lattice and the alphabet plays for a sequence: it is the
stable finite index the modalities lay the field against (with a fixed
population it is simply constant). Each node's state projects to:

- **spatial** -- a mark at the node's ``locus`` (a *view hint* the program
  carries for drawing) coloured by its value, plus the edge set so a renderer
  can draw the wiring. The spatial surface therefore needs an embedding; the
  inverse recovers ``(node, value)`` exactly within the node set.
- **sonic** -- a voice whose rhythmic ``step`` is the node's index in the node
  set and whose ``pitch_row`` *is the node's value* (each state a distinct
  pitch), so the melody carries the field's values and needs no geometry -- it
  projects an abstract graph too. The inverse is an exact bijection within the
  node set.

So spatial-recovered == sonic-recovered == ``process_core.node_cells``. A caller
may pass a partial node set (a window on the nodes); nodes outside it are
clipped, which is honest, contract-declared loss, never invented.

The **edges** ride along as view-only structure: they are the static topology,
recoverable from the core itself, not a projected value -- so the inverse claim
is about node states, and the wiring is metadata for rendering. This mirrors the
expressiveness ladder's reading of the graph tier: universal at representation,
with the structure shown rather than perceptually authored.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_capabilities, process_core

GRAPH_SPATIAL_ANIM_KIND = "graph-spatial-anim-v1"
GRAPH_SONIC_ANIM_KIND = "graph-sonic-anim-v1"

_STATE_FIELD = "state"


def animate(core: dict[str, Any], steps: int) -> list[dict[str, Any]]:
    """Advance the graph program with the one shared stepper, returning frames.

    The *only* call that produces motion. Every projection below consumes its
    output; none of them steps the program independently.
    """
    return process_core.run(core, steps)


# --------------------------------------------------------------------------
# Node set: the index axis. A graph has no coordinate extent and no linear
# order, but its set of node ids is finite and (with a fixed population)
# constant. Derived from the whole trajectory by default so a node's row never
# moves between frames.
# --------------------------------------------------------------------------

def node_set(trajectory: list[dict[str, Any]], field: str = _STATE_FIELD) -> list[Any]:
    """The sorted distinct node ids across every frame of a trajectory."""
    nodes = {
        node
        for frame in trajectory
        for node, _ in process_core.node_cells(frame, field)
    }
    return sorted(nodes)


def _resolve_node_set(
    target: dict[str, Any] | list[dict[str, Any]],
    nodes: list[Any] | None,
    field: str,
) -> list[Any]:
    if nodes is not None:
        return list(nodes)
    frames = target if isinstance(target, list) else [target]
    return node_set(frames, field)


def _positions(frame: dict[str, Any]) -> dict[Any, list[int]]:
    """Map each node to its ``locus`` view hint (its drawing position)."""
    return {
        rec["node"]: rec["locus"]
        for rec in frame["state"]["loci"]
        if "locus" in rec
    }


def _edges(frame: dict[str, Any]) -> list[list[Any]]:
    """The static edge set carried as view-only structure for rendering."""
    return [list(edge) for edge in frame["topology"].get("edges", [])]


# --------------------------------------------------------------------------
# Spatial modality: a frame is a set of marks, one per node in the node set,
# each at the node's embedded position and carrying its value, plus the edges.
# The inverse recovers (node, value) for everything the node set holds.
# --------------------------------------------------------------------------

def to_spatial_frame(
    frame: dict[str, Any],
    index: int,
    field: str = _STATE_FIELD,
    nodes: list[Any] | None = None,
) -> dict[str, Any]:
    """Project one graph frame into a spatial frame of placed, coloured nodes."""
    node_index = _resolve_node_set(frame, nodes, field)
    positions = _positions(frame)
    present = set(node_index)
    missing = [n for n in present if n not in positions]
    if missing:
        raise ValueError(
            "graph spatial projection needs a locus per node (an embedding); "
            f"missing for nodes {sorted(missing)!r}"
        )
    return {
        "kind": GRAPH_SPATIAL_ANIM_KIND,
        "frame": index,
        "field": field,
        "nodes": list(node_index),
        "edges": _edges(frame),
        "marks": [
            {"node": node, "x": positions[node][0], "y": positions[node][1], "value": value}
            for node, value in process_core.node_cells(frame, field)
            if node in present
        ],
    }


def to_spatial_animation(
    trajectory: list[dict[str, Any]],
    field: str = _STATE_FIELD,
    nodes: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a spatial animation over one node set."""
    node_index = _resolve_node_set(trajectory, nodes, field)
    return [to_spatial_frame(frame, i, field, node_index) for i, frame in enumerate(trajectory)]


def nodes_from_spatial_frame(frame: dict[str, Any]) -> list[tuple[Any, Any]]:
    """Inverse: recover the ``(node, value)`` field a spatial frame represents."""
    return sorted((mark["node"], mark["value"]) for mark in frame["marks"])


# --------------------------------------------------------------------------
# Sonic modality: a frame is a melody, one voice per node in the node set. The
# rhythmic step is the node's index in the node set; the pitch row *is* the
# node's value (each state a distinct pitch). Both maps are bijections within
# the node set, so the inverse recovers the exact (node, value) field with no
# geometry -- the sonic surface projects an abstract graph too.
# --------------------------------------------------------------------------

def to_sonic_frame(
    frame: dict[str, Any],
    index: int,
    field: str = _STATE_FIELD,
    nodes: list[Any] | None = None,
) -> dict[str, Any]:
    """Project one graph frame into a sonic frame of voices over a node set."""
    node_index = _resolve_node_set(frame, nodes, field)
    step = {node: i for i, node in enumerate(node_index)}
    return {
        "kind": GRAPH_SONIC_ANIM_KIND,
        "frame": index,
        "field": field,
        "nodes": list(node_index),
        "steps": len(node_index),
        "voices": [
            {"step": step[node], "pitch_row": value, "node": node}
            for node, value in process_core.node_cells(frame, field)
            if node in step
        ],
    }


def to_sonic_animation(
    trajectory: list[dict[str, Any]],
    field: str = _STATE_FIELD,
    nodes: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Project a whole trajectory into a sonic animation over one node set."""
    node_index = _resolve_node_set(trajectory, nodes, field)
    return [to_sonic_frame(frame, i, field, node_index) for i, frame in enumerate(trajectory)]


def nodes_from_sonic_frame(frame: dict[str, Any]) -> list[tuple[Any, Any]]:
    """Inverse: recover the ``(node, value)`` field a sonic frame represents.

    The node comes from the node set at the voice's ``step``; the value is the
    ``pitch_row`` (which encodes the state directly).
    """
    index = frame["nodes"]
    return sorted((index[voice["step"]], voice["pitch_row"]) for voice in frame["voices"])


# --------------------------------------------------------------------------
# Capability contracts: derived from node-set coverage, not asserted. A node set
# holding every node in the run recovers the field exactly; a partial node set
# is honestly lossy on the nodes it omits. The graph tier (4) rides on the
# contract too -- and an exact inverse here shows tier and invertibility are
# orthogonal: a fixed-structure graph round-trips exactly though its class
# (graph rewriting) tops the ladder.
# --------------------------------------------------------------------------

def _node_set_covers(
    trajectory: list[dict[str, Any]],
    nodes: list[Any],
    field: str,
) -> bool:
    """Whether every node in the whole trajectory is in the node set."""
    index = set(nodes)
    return all(
        node in index
        for frame in trajectory
        for node, _ in process_core.node_cells(frame, field)
    )


def projection_capabilities(
    projection: str,
    trajectory: list[dict[str, Any]],
    field: str = _STATE_FIELD,
    nodes: list[Any] | None = None,
) -> dict[str, Any]:
    """Declare a graph projection's capabilities for a trajectory.

    The inverse level is *derived*: exact when the node set holds every node in
    the run, partial (lossy on omitted nodes) when it does not. Edges are
    carried as view-only structure, not part of the value inverse.
    """
    node_index = _resolve_node_set(trajectory, nodes, field)
    covers = _node_set_covers(trajectory, node_index, field)
    contract = process_capabilities.projection_contract(
        projection=projection,
        core=trajectory[0],
        preserves=["node-states-in-node-set"],
        derived=["graph-structure-view-only"],
        lossy=[] if covers else ["nodes-outside-node-set"],
        inverse="exact" if covers else "partial",
    )
    contract["nodes"] = list(node_index)
    return contract


def spatial_animation_manifest(
    trajectory: list[dict[str, Any]],
    field: str = _STATE_FIELD,
    nodes: list[Any] | None = None,
) -> dict[str, Any]:
    """A full graph spatial animation: capabilities + node set + frames."""
    node_index = _resolve_node_set(trajectory, nodes, field)
    return {
        "kind": GRAPH_SPATIAL_ANIM_KIND,
        "field": field,
        "capabilities": projection_capabilities(
            GRAPH_SPATIAL_ANIM_KIND, trajectory, field, node_index
        ),
        "nodes": list(node_index),
        "frames": to_spatial_animation(trajectory, field, node_index),
    }


def sonic_animation_manifest(
    trajectory: list[dict[str, Any]],
    field: str = _STATE_FIELD,
    nodes: list[Any] | None = None,
) -> dict[str, Any]:
    """A full graph sonic animation: capabilities + node set + frames."""
    node_index = _resolve_node_set(trajectory, nodes, field)
    return {
        "kind": GRAPH_SONIC_ANIM_KIND,
        "field": field,
        "capabilities": projection_capabilities(
            GRAPH_SONIC_ANIM_KIND, trajectory, field, node_index
        ),
        "nodes": list(node_index),
        "frames": to_sonic_animation(trajectory, field, node_index),
    }

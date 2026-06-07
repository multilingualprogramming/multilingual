#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Example: a network contagion as a ``semantic-core-v1`` program.

Game of Life and the cyclic-dominance ecology run on a *lattice*, where what
counts as a neighbour is decided by position -- the eight cells around you. A
great many real processes are not like that: an epidemic, a rumour, a packet,
a cascading failure spread along an arbitrary **graph** of contacts, and two
nodes wired together may sit anywhere in space. The graph topology is the axis
that decouples *interaction* from *position*: adjacency is the explicit edge
set, not the geometry.

Like Game of Life and the L-system, this is nothing but a filling of the
modality-free ⟨State, Topology, Rule, Schedule⟩ tuple in
``multilingualprogramming.codegen.process_core`` -- the core engine knows no
epidemiology; everything specific lives here, as data. What it adds is the new
topology axis:

- **State**    -- a per-node ``{"state": s}`` with ``s`` in
  ``{0 susceptible, 1 infected, 2 recovered}`` (a multi-valued field, as the
  ecology had), plus a ``node`` id and a ``locus`` *view hint* (the node's
  position when drawn -- never read by the engine).
- **Topology** -- a **graph**: two well-connected communities joined by a single
  bridge edge, so an outbreak must sweep one community and then cross the bridge.
- **Rule**     -- the standard discrete SIR transition as rewrite clauses: an
  infected node recovers; a susceptible node with at least one infected
  neighbour catches it; a recovered (or contact-free) node is left unchanged
  (the rule has no ``default``, so identity-on-no-match keeps it put).
- **Schedule** -- synchronous (every node updates from the previous frame).

The *same* core stepper that runs Conway's Life on a lattice runs this contagion
on a graph with no new engine code -- the rewrite rule is unchanged; only the
topology decides who a node's neighbours are. That is the universality claim
``semantic-core-v1`` exists to make, now on the graph axis.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_core

STATE_FIELD = "state"
SUSCEPTIBLE = 0
INFECTED = 1
RECOVERED = 2

NODES_PER_CLUSTER = 6
# Integer hexagon offsets, so a community is a ring of six nodes with three
# long diagonals -- dense enough to be a "community." Coordinates are computed
# with integer arithmetic only (no trigonometry) so the .multi authoring and
# this reference build a byte-identical manifest.
_HEX = [[2, 0], [1, 2], [-1, 2], [-2, 0], [-1, -2], [1, -2]]
_CLUSTER_SPAN = 8  # x-distance between the two community centres
_CENTRE_X = 3
_CENTRE_Y = 3
_SEED_NODE = 3  # a node on the far (left) side of community A, away from the bridge
_BRIDGE = [0, 9]  # community A's right-side node <-> community B's left-side node


def community_edges() -> list[list[int]]:
    """The contact graph: two six-node communities joined by one bridge.

    Each community is a ring (``i -- i+1``) plus the three long diagonals, so
    every node has degree three or four within its community; node ids ``0..5``
    are community A and ``6..11`` community B. A single bridge wires A's
    right-side node to B's left-side node, so an outbreak in A must traverse the
    community before it can cross to B.
    """
    ring = [[i, (i + 1) % NODES_PER_CLUSTER] for i in range(NODES_PER_CLUSTER)]
    chords = [[0, 3], [1, 4], [2, 5]]
    within = ring + chords
    edges = [
        [c * NODES_PER_CLUSTER + a, c * NODES_PER_CLUSTER + b]
        for c in range(2)
        for a, b in within
    ]
    edges.append(list(_BRIDGE))
    return edges


def community_loci(seed: int = _SEED_NODE) -> list[dict[str, Any]]:
    """Lay the two communities out as two hexagons, ``seed`` infected.

    The ``locus`` each node carries is a *view hint* for spatial projection (a
    hexagon on the left for A, on the right for B); the engine never reads it,
    only ``node`` and the edges. Exactly one node starts infected.
    """
    loci = []
    for c in range(2):
        cx = _CENTRE_X + c * _CLUSTER_SPAN
        for i in range(NODES_PER_CLUSTER):
            node = c * NODES_PER_CLUSTER + i
            loci.append(
                {
                    "node": node,
                    "locus": [cx + _HEX[i][0], _CENTRE_Y + _HEX[i][1]],
                    STATE_FIELD: INFECTED if node == seed else SUSCEPTIBLE,
                }
            )
    return loci


def sir_rule(node_count: int, field: str = STATE_FIELD) -> dict[str, Any]:
    """Compile the discrete SIR transition into generic rewrite clauses.

    Tried in order: an infected node recovers; a susceptible node with at least
    one infected neighbour becomes infected. A node matching neither clause --
    recovered, or susceptible with no infected contact -- is left unchanged (no
    ``default``). "At least one" is the totalistic count ``1..node_count-1`` (a
    node can have at most ``node_count - 1`` neighbours).
    """
    contact = list(range(1, node_count))
    clauses = [
        {"match": {"self": {field: INFECTED}}, "produce": {field: RECOVERED}},
        {
            "match": {
                "self": {field: SUSCEPTIBLE},
                "neighbor_count": [{"field": field, "value": INFECTED, "in": contact}],
            },
            "produce": {field: INFECTED},
        },
    ]
    return process_core.rewrite_rule(clauses=clauses, default=None)


def network_epidemic(
    seed: int = _SEED_NODE,
    field: str = STATE_FIELD,
    source_path: str = "",
) -> dict[str, Any]:
    """Assemble a synchronous SIR contagion on the two-community contact graph."""
    loci = community_loci(seed)
    return process_core.build_process_core(
        state={"loci": loci},
        topology=process_core.graph_topology(community_edges()),
        rule=sir_rule(len(loci), field),
        schedule=process_core.synchronous_schedule(),
        source_path=source_path,
    )


def _render(core: dict[str, Any]) -> str:
    """One glyph per node state, in node order, for the demo."""
    glyph = {SUSCEPTIBLE: ".", INFECTED: "#", RECOVERED: "o"}
    return " ".join(glyph[v] for _, v in process_core.node_cells(core, STATE_FIELD))


def _demo() -> None:
    """Run the outbreak for a few ticks and print each frame's node states."""
    core = network_epidemic()
    for tick, frame in enumerate(process_core.run(core, 8)):
        print(f"tick {tick}: {_render(frame)}")


if __name__ == "__main__":
    _demo()

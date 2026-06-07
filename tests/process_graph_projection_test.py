#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of an animated graph process (semantic-core-v1).

The lattice and sequence projections prove spatial == sonic == core for every
frame; this suite makes the same polymodal claim for the graph projection on a
network contagion: for every animated frame, the node field recovered from the
spatial marks equals the field recovered from the sonic voices equals the
core's own ``node_cells`` -- node and value alike. It also checks the honesty
frontier and an instructive subtlety of the graph tier:

- a node set holding every node declares (and delivers) an exact inverse; a
  partial node set declares partial and drops exactly the omitted nodes;
- the sonic surface needs no geometry (it indexes by the node set), so it
  projects an abstract graph; the spatial surface needs an embedding and says
  so loudly when a node lacks one;
- the program sits at **Tier 4** (graph rewriting) yet the projection inverts
  **exactly** -- tier (the class ceiling) and invertibility (this fixed-
  structure instance) are orthogonal.
"""

import unittest

from examples import network_epidemic as ne
from multilingualprogramming.codegen import process_core
from multilingualprogramming.codegen import process_graph_projection as gp

FIELD = "state"


def _trajectory(steps: int = 6):
    return process_core.run(ne.network_epidemic(), steps)


class GraphEquivalenceTestSuite(unittest.TestCase):
    """Spatial and sonic recover the same node field as the core, every frame."""

    def test_spatial_equals_sonic_equals_core_each_frame(self):
        trajectory = _trajectory()
        for i, frame in enumerate(trajectory):
            core_field = process_core.node_cells(frame, FIELD)
            spatial = gp.nodes_from_spatial_frame(gp.to_spatial_frame(frame, i, FIELD))
            sonic = gp.nodes_from_sonic_frame(gp.to_sonic_frame(frame, i, FIELD))
            self.assertEqual(core_field, spatial)
            self.assertEqual(core_field, sonic)

    def test_marks_carry_node_position_and_value_plus_edges(self):
        frame = _trajectory(0)[0]
        spatial = gp.to_spatial_frame(frame, 0, FIELD)
        self.assertTrue(all({"node", "x", "y", "value"} <= set(m) for m in spatial["marks"]))
        self.assertEqual(len(spatial["marks"]), 12)
        # Edges ride along as view-only structure for drawing the wiring.
        self.assertEqual(spatial["edges"], [list(e) for e in frame["topology"]["edges"]])

    def test_sonic_pitch_row_is_the_state_value(self):
        frame = _trajectory(0)[0]
        sonic = gp.to_sonic_frame(frame, 0, FIELD)
        by_node = {v["node"]: v["pitch_row"] for v in sonic["voices"]}
        for node, value in process_core.node_cells(frame, FIELD):
            self.assertEqual(by_node[node], value)

    def test_animation_lengths_match_trajectory(self):
        trajectory = _trajectory(4)
        self.assertEqual(len(gp.to_spatial_animation(trajectory, FIELD)), 5)
        self.assertEqual(len(gp.to_sonic_animation(trajectory, FIELD)), 5)


class GraphContractTestSuite(unittest.TestCase):
    """Contracts are derived from node-set coverage, and tier is orthogonal."""

    def test_full_node_set_is_exact_and_tier_four(self):
        trajectory = _trajectory()
        for kind, manifest in (
            (gp.GRAPH_SPATIAL_ANIM_KIND, gp.spatial_animation_manifest(trajectory, FIELD)),
            (gp.GRAPH_SONIC_ANIM_KIND, gp.sonic_animation_manifest(trajectory, FIELD)),
        ):
            caps = manifest["capabilities"]
            self.assertEqual(manifest["kind"], kind)
            self.assertEqual(caps["inverse"], "exact")
            self.assertEqual(caps["lossy"], [])
            # Tier 4 (graph) yet exact inverse -- the orthogonality of class and instance.
            self.assertEqual(caps["tier"]["tier"], 4)

    def test_exact_contract_round_trips_every_node(self):
        trajectory = _trajectory()
        manifest = gp.sonic_animation_manifest(trajectory, FIELD)
        self.assertEqual(manifest["capabilities"]["inverse"], "exact")
        for idx, sonic_frame in enumerate(manifest["frames"]):
            recovered = gp.nodes_from_sonic_frame(sonic_frame)
            self.assertEqual(recovered, process_core.node_cells(trajectory[idx], FIELD))

    def test_partial_node_set_is_partial_and_drops_only_omitted_nodes(self):
        trajectory = _trajectory()
        subset = [0, 1, 2, 3, 4, 5]  # community A only
        caps = gp.projection_capabilities(gp.GRAPH_SONIC_ANIM_KIND, trajectory, FIELD, subset)
        self.assertEqual(caps["inverse"], "partial")
        self.assertEqual(caps["lossy"], ["nodes-outside-node-set"])
        frame = trajectory[0]
        recovered = gp.nodes_from_sonic_frame(gp.to_sonic_frame(frame, 0, FIELD, subset))
        inside = [(n, v) for n, v in process_core.node_cells(frame, FIELD) if n in set(subset)]
        self.assertEqual(recovered, inside)


class GraphEmbeddingTestSuite(unittest.TestCase):
    """Sonic needs no geometry; spatial needs an embedding and says so."""

    def _abstract_graph(self):
        # Nodes with no ``locus`` -- a purely abstract graph.
        loci = [{"node": i, FIELD: (1 if i == 0 else 0)} for i in range(3)]
        return process_core.build_process_core(
            state={"loci": loci},
            topology=process_core.graph_topology([[0, 1], [1, 2]]),
            rule=ne.sir_rule(3, FIELD),
            schedule=process_core.synchronous_schedule(),
        )

    def test_sonic_projects_an_abstract_graph(self):
        core = self._abstract_graph()
        sonic = gp.to_sonic_frame(core, 0, FIELD)
        self.assertEqual(gp.nodes_from_sonic_frame(sonic), process_core.node_cells(core, FIELD))

    def test_spatial_requires_an_embedding(self):
        core = self._abstract_graph()
        with self.assertRaises(ValueError):
            gp.to_spatial_frame(core, 0, FIELD)


if __name__ == "__main__":
    unittest.main()

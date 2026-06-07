#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""The graph topology of semantic-core-v1.

Game of Life exercised the synchronous lattice; the L-system exercised
generative rewriting; the ecology exercised the asynchronous schedule on a
multi-state field. The remaining engine axis -- an arbitrary **graph**
topology, where adjacency is the explicit edge set rather than position -- is
exercised here by a discrete SIR network contagion. The sharp claims this
suite guards:

- ``neighbors`` answers a graph from its edges (undirected by default,
  directed when asked), and the *same* rewrite primitive that flips a lattice
  cell drives a graph node -- only the topology decides who is a neighbour;
- a node's ``locus`` is a view hint the engine ignores: rewiring the edges,
  not moving nodes, changes the dynamics;
- open population on a graph is refused loudly (it would be full graph
  rewriting, not yet specified);
- the program classifies onto Tier 4 (graph rewriting) -- the tier no example
  reached before;
- the English and French ``.multi`` sources, and the Python reference, all
  agree byte-for-byte and step identically.
"""

import unittest
from pathlib import Path

from examples import network_epidemic as ne
from multilingualprogramming.codegen import process_capabilities, process_core
from multilingualprogramming.codegen import process_program as pproc

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
EN_SOURCE = EXAMPLES / "network_epidemic.multi"
FR_SOURCE = EXAMPLES / "network_epidemic.fr.multi"

FIELD = "state"


def _build(source_path: Path, language: str = "en") -> dict:
    return pproc.execute_process(
        source_path.read_text(encoding="utf-8"),
        language=language,
        source_path=str(source_path),
    )


class GraphTopologyTestSuite(unittest.TestCase):
    """neighbors reads the edge set, not geometry."""

    def test_undirected_edges_are_mutual(self):
        topo = process_core.graph_topology([[0, 1], [1, 2]])
        self.assertEqual(process_core.neighbors(topo, 1), [0, 2])
        self.assertEqual(process_core.neighbors(topo, 0), [1])
        self.assertEqual(process_core.neighbors(topo, 2), [1])

    def test_directed_edges_are_one_way(self):
        topo = process_core.graph_topology([[0, 1], [1, 2]], directed=True)
        self.assertEqual(process_core.neighbors(topo, 0), [1])
        self.assertEqual(process_core.neighbors(topo, 1), [2])
        self.assertEqual(process_core.neighbors(topo, 2), [])

    def test_isolated_node_has_no_neighbours(self):
        topo = process_core.graph_topology([[0, 1]])
        self.assertEqual(process_core.neighbors(topo, 7), [])

    def test_string_node_ids_work(self):
        topo = process_core.graph_topology([["a", "b"], ["b", "c"]])
        self.assertEqual(process_core.neighbors(topo, "b"), ["a", "c"])


class GraphEngineTestSuite(unittest.TestCase):
    """The same rewrite primitive drives a graph; node_cells reads it."""

    def _path_sir(self, schedule=None):
        # A path 0 -- 1 -- 2 -- 3, node 0 infected, SIR rule.
        loci = [{"node": i, "locus": [i, 0], FIELD: 0} for i in range(4)]
        loci[0][FIELD] = 1
        return process_core.build_process_core(
            state={"loci": loci},
            topology=process_core.graph_topology([[0, 1], [1, 2], [2, 3]]),
            rule=ne.sir_rule(4, FIELD),
            schedule=schedule or process_core.synchronous_schedule(),
        )

    def test_contagion_walks_the_graph(self):
        core = self._path_sir()
        states = [process_core.node_cells(f, FIELD) for f in process_core.run(core, 3)]
        # The infection front travels one hop per tick, recovering behind it.
        self.assertEqual(states[0], [(0, 1), (1, 0), (2, 0), (3, 0)])
        self.assertEqual(states[1], [(0, 2), (1, 1), (2, 0), (3, 0)])
        self.assertEqual(states[2], [(0, 2), (1, 2), (2, 1), (3, 0)])
        self.assertEqual(states[3], [(0, 2), (1, 2), (2, 2), (3, 1)])

    def test_locus_is_a_view_hint_only(self):
        # Moving the nodes' coordinates must not change the dynamics: adjacency
        # is the wiring, not the geometry.
        core = self._path_sir()
        scrambled = {
            **core,
            "state": {
                "loci": [
                    {**rec, "locus": [99 - rec["node"], 7]}
                    for rec in core["state"]["loci"]
                ]
            },
        }
        a = [process_core.node_cells(f, FIELD) for f in process_core.run(core, 3)]
        b = [process_core.node_cells(f, FIELD) for f in process_core.run(scrambled, 3)]
        self.assertEqual(a, b)

    def test_step_does_not_mutate_input(self):
        core = self._path_sir()
        before = process_core.node_cells(core, FIELD)
        process_core.step(core)
        self.assertEqual(process_core.node_cells(core, FIELD), before)

    def test_node_cells_sorted_by_node(self):
        core = self._path_sir()
        cells = process_core.node_cells(core, FIELD)
        self.assertEqual([n for n, _ in cells], [0, 1, 2, 3])

    def test_open_population_on_graph_is_rejected(self):
        core = process_core.build_process_core(
            state={"loci": [{"node": 0, "locus": [0, 0], FIELD: 1}],
                   "population": process_core.POPULATION_OPEN,
                   "empty": {FIELD: 0}},
            topology=process_core.graph_topology([[0, 1]]),
            rule=ne.sir_rule(2, FIELD),
            schedule=process_core.synchronous_schedule(),
        )
        with self.assertRaises(NotImplementedError):
            process_core.step(core)


class GraphTierTestSuite(unittest.TestCase):
    """A graph topology classifies onto Tier 4."""

    def test_graph_is_tier_four(self):
        core = _build(EN_SOURCE)
        self.assertEqual(process_capabilities.expressiveness_tier(core), 4)

    def test_same_rule_on_a_lattice_is_not_tier_four(self):
        # The tier reads the topology axis: the identical SIR clauses on a
        # lattice would not be Tier 4 (it is the graph that lifts it).
        core = _build(EN_SOURCE)
        as_lattice = {**core, "topology": process_core.lattice_topology(4, 3)}
        self.assertNotEqual(process_capabilities.expressiveness_tier(as_lattice), 4)


class GraphProgramTestSuite(unittest.TestCase):
    """The .multi contagion matches the Python reference and the French source."""

    def test_authored_without_python(self):
        text = EN_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("import", text)
        self.assertIn("graph_topology", text)
        self.assertIn("build_process_core", text)

    def test_byte_identical_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = ne.network_epidemic(source_path=core["source"])
        self.assertEqual(core, reference)

    def test_steps_identically_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = ne.network_epidemic(source_path=core["source"])
        built = [process_core.node_cells(f, FIELD) for f in process_core.run(core, 8)]
        expected = [process_core.node_cells(f, FIELD) for f in process_core.run(reference, 8)]
        self.assertEqual(built, expected)

    def test_outbreak_actually_spreads_and_settles(self):
        core = _build(EN_SOURCE)
        trajectory = process_core.run(core, 8)
        # Starts with one infected, ends with everyone recovered.
        self.assertEqual(
            sum(1 for _, v in process_core.node_cells(trajectory[0], FIELD) if v == 1),
            1,
        )
        self.assertTrue(
            all(v == 2 for _, v in process_core.node_cells(trajectory[-1], FIELD))
        )

    def test_english_and_french_lower_to_identical_core(self):
        en = _build(EN_SOURCE, language="en")
        fr = _build(FR_SOURCE, language="fr")
        en.pop("source")
        fr.pop("source")
        self.assertEqual(en, fr)


if __name__ == "__main__":
    unittest.main()

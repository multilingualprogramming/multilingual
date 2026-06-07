#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for the semantic-core-v1 process core.

Two concerns, kept deliberately separate:

- ``ProcessCore*`` suites exercise the **language** -- the generic rewrite
  engine, topology query, and synchronous stepper. They mention no
  specific system; a tiny hand-written rewrite rule stands in for "some
  program."
- ``GameOfLife*`` suites exercise an **example program**
  (``examples/game_of_life_polymodal``) built entirely on that engine.
  They are the falsifiable proof that one modality-free tuple, advanced by
  the single core stepper, reproduces canonical Life behaviour (period-2
  oscillator, still life, translating glider) -- and that swapping the rule
  *data* yields a different automaton with no engine change.

The split is the architectural claim: Game of Life is a filling of the
form, not part of the computation.
"""

import json
import unittest

from examples import game_of_life_polymodal as gol
from multilingualprogramming.codegen import process_core
from multilingualprogramming.codegen.process_core import (
    CORE_KIND,
    RULE_REWRITE,
    SCHEDULE_SYNCHRONOUS,
    TOPOLOGY_LATTICE,
    active_cells,
    build_process_core,
    lattice_topology,
    neighbors,
    rewrite_rule,
    run,
    step,
    synchronous_schedule,
)


def _single_field_lattice(width, height, live, field="alive", wrap=False, rule=None):
    """Build a minimal synchronous lattice core for engine-level tests."""
    liveset = {(x, y) for x, y in live}
    loci = [
        {"locus": [x, y], field: 1 if (x, y) in liveset else 0}
        for y in range(height)
        for x in range(width)
    ]
    return build_process_core(
        state={"loci": loci},
        topology=lattice_topology(width, height, wrap=wrap),
        rule=rule or rewrite_rule(clauses=[], default={field: 0}),
        schedule=synchronous_schedule(),
    )


class ProcessCoreShapeTestSuite(unittest.TestCase):
    """The v1 manifest is well-formed, modality-free, and serializable."""

    def test_manifest_shape(self):
        core = _single_field_lattice(3, 3, [(1, 1)])
        self.assertEqual(core["kind"], CORE_KIND)
        self.assertEqual(core["version"], 1)
        self.assertEqual(core["topology"]["kind"], TOPOLOGY_LATTICE)
        self.assertEqual(core["rule"]["kind"], RULE_REWRITE)
        self.assertEqual(core["schedule"]["kind"], SCHEDULE_SYNCHRONOUS)
        self.assertEqual(len(core["state"]["loci"]), 9)

    def test_manifest_is_json_serializable(self):
        # No coordinates-as-dict-keys, no callables: the whole tuple is data.
        core = _single_field_lattice(3, 3, [(1, 1)])
        restored = json.loads(json.dumps(core))
        self.assertEqual(restored["kind"], CORE_KIND)

    def test_core_module_knows_no_specific_system(self):
        # Guard the architectural boundary: the language must not name a
        # program. Game of Life lives in examples/, not the core.
        names = dir(process_core)
        self.assertNotIn("game_of_life", names)
        self.assertNotIn("life_like_rule", names)
        self.assertFalse(
            any("life" in name.lower() for name in names),
            "process_core must not reference any specific automaton",
        )


class LatticeTopologyTestSuite(unittest.TestCase):
    """The single topology query: neighbors(locus)."""

    def test_moore8_interior_has_eight_neighbors(self):
        topo = lattice_topology(5, 5, wrap=False)
        self.assertEqual(len(neighbors(topo, (2, 2))), 8)

    def test_bounded_corner_has_three_neighbors(self):
        topo = lattice_topology(5, 5, wrap=False)
        self.assertEqual(set(neighbors(topo, (0, 0))), {(1, 0), (0, 1), (1, 1)})

    def test_toroidal_corner_wraps_to_eight(self):
        topo = lattice_topology(5, 5, wrap=True)
        nbs = neighbors(topo, (0, 0))
        self.assertEqual(len(nbs), 8)
        self.assertIn((4, 4), nbs)  # diagonal wrap
        self.assertIn((4, 0), nbs)
        self.assertIn((0, 4), nbs)


class ProcessCoreEngineTestSuite(unittest.TestCase):
    """The generic rewrite stepper, exercised without any named system."""

    def test_empty_clause_set_applies_default_everywhere(self):
        # No clause matches, so every locus takes the default (dead).
        core = _single_field_lattice(3, 3, [(0, 0), (1, 1), (2, 2)])
        self.assertEqual(active_cells(step(core)), [])

    def test_self_only_clause_with_no_neighbor_predicate(self):
        # A clause matching purely on the locus's own state: every live
        # cell stays live, every dead cell stays dead -- a pure identity
        # written as data, proving "self" matching works in isolation.
        rule = rewrite_rule(
            clauses=[{"match": {"self": {"alive": 1}}, "produce": {"alive": 1}}],
            default={"alive": 0},
        )
        core = _single_field_lattice(3, 3, [(0, 0), (2, 2)], rule=rule)
        self.assertEqual(active_cells(step(core)), [(0, 0), (2, 2)])

    def test_neighbor_count_matching(self):
        # "Born with exactly one live neighbour, never survive": isolates
        # the totalistic neighbour-count predicate. The cell at (1,1) has
        # one live neighbour (2,1) so it is born; (2,1) also has exactly
        # one live neighbour (none others) -> stays/born; symmetric.
        rule = rewrite_rule(
            clauses=[
                {
                    "match": {
                        "self": {"alive": 0},
                        "neighbor_count": [{"field": "alive", "value": 1, "in": [1]}],
                    },
                    "produce": {"alive": 1},
                }
            ],
            default={"alive": 0},
        )
        core = _single_field_lattice(3, 1, [(1, 0)], rule=rule)  # one live cell
        # Its two orthogonal/diagonal neighbours (0,0) and (2,0) each see
        # exactly one live neighbour and are born; the live cell itself has
        # no clause for self==1 so it dies.
        self.assertEqual(active_cells(step(core)), [(0, 0), (2, 0)])

    def test_step_does_not_mutate_input(self):
        rule = gol.life_like_rule()
        core = _single_field_lattice(5, 5, [(1, 1), (2, 1), (3, 1)], rule=rule)
        before = json.dumps(core)
        step(core)
        self.assertEqual(json.dumps(core), before)

    def test_run_returns_initial_plus_each_step(self):
        core = _single_field_lattice(3, 3, [])
        trajectory = run(core, 3)
        self.assertEqual(len(trajectory), 4)
        self.assertIs(trajectory[0], core)

    def test_unknown_schedule_kind_raises(self):
        core = _single_field_lattice(3, 3, [(1, 1)])
        core = {**core, "schedule": {"kind": "continuous-dt"}}
        with self.assertRaises(NotImplementedError):
            step(core)

    def test_unknown_rule_kind_raises(self):
        core = _single_field_lattice(3, 3, [(1, 1)])
        core = {**core, "rule": {"kind": "graph-rewrite"}}
        with self.assertRaises(NotImplementedError):
            step(core)

    def test_unknown_topology_kind_raises(self):
        with self.assertRaises(NotImplementedError):
            neighbors({"kind": "graph"}, (0, 0))


class GameOfLifeBehaviourTestSuite(unittest.TestCase):
    """The example program: canonical Life patterns evolve exactly."""

    def test_program_is_data_built_on_the_core(self):
        core = gol.game_of_life(4, 4, gol.BLOCK)
        self.assertEqual(core["kind"], CORE_KIND)
        self.assertEqual(core["rule"]["kind"], RULE_REWRITE)  # generic primitive
        self.assertEqual(active_cells(core), sorted(gol.BLOCK))

    def test_blinker_oscillates_with_period_two(self):
        horizontal = gol.BLINKER  # (1,1),(2,1),(3,1)
        vertical = [(2, 0), (2, 1), (2, 2)]
        core = gol.game_of_life(5, 5, horizontal, wrap=False)

        after1 = step(core)
        self.assertEqual(active_cells(after1), sorted(vertical))

        after2 = step(after1)
        self.assertEqual(active_cells(after2), sorted(horizontal))

    def test_block_is_a_still_life(self):
        core = gol.game_of_life(4, 4, gol.BLOCK, wrap=False)
        for frame in run(core, 5):
            self.assertEqual(active_cells(frame), sorted(gol.BLOCK))

    def test_glider_translates_by_one_one_every_four_steps(self):
        core = gol.game_of_life(10, 10, gol.GLIDER, wrap=True)
        trajectory = run(core, 4)
        self.assertEqual(len(trajectory), 5)
        expected = sorted((x + 1, y + 1) for x, y in gol.GLIDER)
        self.assertEqual(active_cells(trajectory[4]), expected)


class RuleIsDataTestSuite(unittest.TestCase):
    """Swapping rule data -- not engine code -- changes the universe."""

    def test_seeds_automaton_from_same_engine(self):
        # Seeds is B2/S: nothing survives. A lone live cell has no dead
        # cell with exactly two live neighbours, so it simply dies.
        core = gol.cellular_lattice(
            5, 5, [(2, 2)], rule=gol.life_like_rule(birth=(2,), survival=()), wrap=False
        )
        self.assertEqual(active_cells(step(core)), [])

    def test_seeds_pair_ignites(self):
        # Under B2/S the cells flanking an adjacent pair each see exactly
        # two live neighbours and are born, while the pair dies (S empty).
        core = gol.cellular_lattice(
            5, 5, [(1, 2), (2, 2)],
            rule=gol.life_like_rule(birth=(2,), survival=()), wrap=False,
        )
        born = active_cells(step(core))
        for cell in [(1, 1), (2, 1), (1, 3), (2, 3)]:
            self.assertIn(cell, born)
        self.assertNotIn((1, 2), born)
        self.assertNotIn((2, 2), born)


if __name__ == "__main__":
    unittest.main()

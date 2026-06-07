#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tier-3 open-population rewriting for semantic-core-v1.

Open population is the first capability that genuinely exceeds the
fixed-population lattice (and v0): a rewrite match may *create or destroy*
loci, not merely flip a field, so a program runs on an unbounded space with
only its live loci stored. The whole v1 thesis hinges on this relaxing
"preserves entity count" to "preserves the rule's trajectory."

These tests pin the claim down:

- **Same rule, new meaning.** The open-population Game of Life uses rule
  data byte-identical to the fixed-population one; only population mode and
  topology differ. Birth/death are not new rule logic.
- **Open == fixed where they overlap.** On a region no pattern reaches the
  edge of, open-population Life reproduces fixed-population Life frame for
  frame -- the correctness oracle.
- **Genuinely unbounded.** A glider travels past any pre-declared extent.
- **Creation and destruction really happen.** Population shrinks to zero,
  and a still pattern reshapes by simultaneous birth and death.
- **Backward compatible.** Cores without a population field still step as
  fixed population.
"""

import unittest

from examples import game_of_life_polymodal as gol
from multilingualprogramming.codegen.process_core import (
    POPULATION_OPEN,
    active_cells,
    run,
    step,
)


def _open_cells(core, steps):
    """Live-cell set per frame of an open-population run."""
    return [active_cells(frame) for frame in run(core, steps)]


class SameRuleDataTestSuite(unittest.TestCase):
    """Open population reuses the exact fixed-population rule."""

    def test_open_life_rule_is_identical_to_fixed(self):
        fixed = gol.game_of_life(10, 10, gol.GLIDER)
        opened = gol.game_of_life_open(gol.GLIDER)
        self.assertEqual(opened["rule"], fixed["rule"])
        # The difference lives entirely in State + Topology, not the Rule.
        self.assertEqual(opened["state"]["population"], POPULATION_OPEN)
        self.assertEqual(opened["topology"]["extent"], "infinite")

    def test_open_state_stores_only_live_cells(self):
        opened = gol.game_of_life_open(gol.BLOCK)
        self.assertEqual(len(opened["state"]["loci"]), len(gol.BLOCK))
        self.assertEqual(active_cells(opened), sorted(gol.BLOCK))


class OpenMatchesFixedTestSuite(unittest.TestCase):
    """Where no pattern hits a wall, open Life == fixed (bounded) Life."""

    def _assert_matches(self, pattern, steps, *, offset):
        # Place the pattern away from the origin in both worlds; a bounded
        # grid large enough that the pattern never reaches its edge behaves
        # like an unbounded one.
        ox, oy = offset
        shifted = [(x + ox, y + oy) for x, y in pattern]
        fixed = gol.game_of_life(40, 40, shifted, wrap=False)
        opened = gol.game_of_life_open(shifted)
        fixed_frames = [active_cells(f) for f in run(fixed, steps)]
        open_frames = _open_cells(opened, steps)
        self.assertEqual(open_frames, fixed_frames)

    def test_blinker_agrees(self):
        self._assert_matches(gol.BLINKER, 6, offset=(15, 15))

    def test_block_agrees(self):
        self._assert_matches(gol.BLOCK, 6, offset=(15, 15))

    def test_glider_agrees(self):
        self._assert_matches(gol.GLIDER, 12, offset=(10, 10))


class UnboundedTravelTestSuite(unittest.TestCase):
    """A glider is not confined to any pre-declared extent."""

    def test_glider_travels_past_initial_bounds(self):
        opened = gol.game_of_life_open(gol.GLIDER)  # within x,y <= 2
        # 20 steps = 5 periods -> displaced (5, 5); cells reach >= 5 in x.
        final = active_cells(run(opened, 20)[-1])
        self.assertEqual(len(final), len(gol.GLIDER))  # glider stays a glider
        self.assertTrue(max(x for x, _ in final) >= 5)
        self.assertTrue(max(y for _, y in final) >= 5)

    def test_translation_is_exactly_one_one_per_period(self):
        opened = gol.game_of_life_open(gol.GLIDER)
        start = active_cells(opened)
        after = active_cells(run(opened, 4)[-1])
        self.assertEqual(after, sorted((x + 1, y + 1) for x, y in start))


class CreationAndDestructionTestSuite(unittest.TestCase):
    """Birth and death actually change the locus set."""

    def test_lone_cell_dies_population_reaches_zero(self):
        opened = gol.game_of_life_open([(0, 0)])
        after = step(opened)
        self.assertEqual(after["state"]["loci"], [])
        self.assertEqual(active_cells(after), [])

    def test_blinker_reshapes_by_simultaneous_birth_and_death(self):
        opened = gol.game_of_life_open([(0, 0), (1, 0), (2, 0)])  # horizontal
        before = set(active_cells(opened))
        after = set(active_cells(step(opened)))
        self.assertEqual(after, {(1, -1), (1, 0), (1, 1)})  # vertical
        # The two ends died and two new cells were born; the centre survived.
        self.assertTrue(before - after)   # something destroyed
        self.assertTrue(after - before)   # something created
        self.assertEqual(len(before), len(after))

    def test_negative_coordinates_are_allowed(self):
        # Birth above the origin proves the lattice has no floor at zero.
        opened = gol.game_of_life_open([(0, 0), (1, 0), (2, 0)])
        self.assertIn((1, -1), active_cells(step(opened)))


class BackwardCompatibilityTestSuite(unittest.TestCase):
    """Cores without a population field still step as fixed population."""

    def test_fixed_core_has_no_population_field(self):
        fixed = gol.game_of_life(5, 5, gol.BLINKER, wrap=False)
        self.assertNotIn("population", fixed["state"])
        # And it still steps correctly (defaulting to fixed).
        self.assertEqual(
            active_cells(step(fixed)),
            sorted([(2, 0), (2, 1), (2, 2)]),
        )

    def test_unknown_population_mode_raises(self):
        opened = gol.game_of_life_open(gol.BLOCK)
        opened = {**opened, "state": {**opened["state"], "population": "swarm"}}
        with self.assertRaises(NotImplementedError):
            step(opened)


if __name__ == "__main__":
    unittest.main()

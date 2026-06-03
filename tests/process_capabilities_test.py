#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Expressiveness tiers and v1 capability-contract enforcement.

Two claims:

- **Classification is derived from the axes, not labelled.** Game of Life on
  a fixed lattice is Tier 2; the same rule under open population is Tier 3;
  an empty rule set is Tier 0 (a v0-equivalent static structure); a non-
  lattice topology is Tier 4. Power is monotone -- opening the population can
  only raise the tier, never lower it.
- **The contract must match behaviour.** A projection that declares
  ``inverse: exact`` must round-trip every cell; one that declares ``partial``
  with ``lossy: cells-outside-viewport`` must drop exactly the clipped cells
  and recover the rest. The declaration is checked against reality, closing
  the doc's "richer capability enforcement" milestone for v1.
"""

import unittest

from examples import game_of_life_polymodal as gol
from multilingualprogramming.codegen import (
    process_capabilities as caps,
    process_core,
    process_projection as pp,
)


class ExpressivenessTierTestSuite(unittest.TestCase):
    """A v1 core is classified onto the doc's ladder from its axes."""

    def test_fixed_lattice_life_is_tier_two(self):
        self.assertEqual(caps.expressiveness_tier(gol.game_of_life(8, 8, gol.GLIDER)), 2)

    def test_open_population_life_is_tier_three(self):
        self.assertEqual(caps.expressiveness_tier(gol.game_of_life_open(gol.GLIDER)), 3)

    def test_empty_rule_set_is_tier_zero(self):
        # No clauses -> nothing rewrites -> a static structure (v0-equivalent).
        static = process_core.build_process_core(
            state={"loci": [{"locus": [0, 0], "alive": 1}]},
            topology=process_core.lattice_topology(3, 3),
            rule=process_core.rewrite_rule(clauses=[], default={"alive": 0}),
            schedule=process_core.synchronous_schedule(),
        )
        self.assertEqual(caps.expressiveness_tier(static), 0)

    def test_non_lattice_topology_is_tier_four(self):
        graphish = {
            **gol.game_of_life(4, 4, gol.BLOCK),
            "topology": {"kind": "graph", "edges": []},
        }
        self.assertEqual(caps.expressiveness_tier(graphish), 4)

    def test_continuous_schedule_fixed_lattice_is_tier_one(self):
        core = {
            **gol.game_of_life(4, 4, gol.BLOCK),
            "schedule": {"kind": "continuous-dt", "dt": 0.1},
        }
        self.assertEqual(caps.expressiveness_tier(core), 1)

    def test_opening_population_never_lowers_the_tier(self):
        fixed = caps.expressiveness_tier(gol.game_of_life(20, 20, gol.GLIDER))
        opened = caps.expressiveness_tier(gol.game_of_life_open(gol.GLIDER))
        self.assertGreaterEqual(opened, fixed)

    def test_tier_contract_describes_name_and_invertibility(self):
        contract = caps.tier_contract(gol.game_of_life_open(gol.GLIDER))
        self.assertEqual(contract["tier"], 3)
        self.assertIn("open-population", contract["name"])
        self.assertTrue(contract["invertibility"])


class ProjectionContractTestSuite(unittest.TestCase):
    """The declared contract carries the tier and a valid v0-shaped body."""

    def test_contract_shape_and_tier(self):
        trajectory = pp.animate(gol.game_of_life_open(gol.GLIDER), 8)
        contract = pp.projection_capabilities(pp.SPATIAL_ANIM_KIND, trajectory)
        self.assertEqual(contract["projection"], pp.SPATIAL_ANIM_KIND)
        self.assertEqual(contract["tier"]["tier"], 3)
        for field in ("preserves", "derived", "lossy", "ambiguous"):
            self.assertIsInstance(contract[field], list)

    def test_animation_manifest_bundles_capabilities_and_frames(self):
        trajectory = pp.animate(gol.game_of_life(10, 10, gol.GLIDER), 6)
        manifest = pp.spatial_animation_manifest(trajectory)
        self.assertEqual(manifest["kind"], pp.SPATIAL_ANIM_KIND)
        self.assertEqual(manifest["capabilities"]["projection"], pp.SPATIAL_ANIM_KIND)
        self.assertEqual(len(manifest["frames"]), len(trajectory))


class ContractMatchesBehaviourTestSuite(unittest.TestCase):
    """Enforcement: a declaration that contradicts the round-trip fails here."""

    def test_covering_viewport_declares_and_delivers_exact(self):
        trajectory = pp.animate(gol.game_of_life_open(gol.GLIDER), 12)
        contract = pp.projection_capabilities(pp.SPATIAL_ANIM_KIND, trajectory)
        # Declaration:
        self.assertEqual(contract["inverse"], "exact")
        self.assertEqual(contract["lossy"], [])
        # Behaviour matches the declaration: every cell round-trips.
        spatial = pp.to_spatial_animation(trajectory)
        for index, frame in enumerate(trajectory):
            self.assertEqual(
                pp.live_cells_from_spatial_frame(spatial[index]),
                process_core.active_cells(frame),
            )

    def test_clipping_viewport_declares_and_delivers_partial(self):
        core = gol.game_of_life_open([(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)])
        trajectory = pp.animate(core, 0)
        window = {"x0": 1, "y0": 0, "width": 3, "height": 1}
        contract = pp.projection_capabilities(pp.SONIC_ANIM_KIND, trajectory, window)
        # Declaration:
        self.assertEqual(contract["inverse"], "partial")
        self.assertEqual(contract["lossy"], ["cells-outside-viewport"])
        # Behaviour matches: only the inside cells are recovered, and the
        # clipped cells genuinely remain alive in the core (real loss, not
        # corruption).
        frame = pp.to_sonic_frame(trajectory[0], 0, window)
        self.assertEqual(
            pp.live_cells_from_sonic_frame(frame), [(1, 0), (2, 0), (3, 0)]
        )
        self.assertIn((0, 0), process_core.active_cells(core))
        self.assertIn((4, 0), process_core.active_cells(core))


if __name__ == "__main__":
    unittest.main()

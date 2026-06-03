#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Animated cross-modal equivalence for semantic-core-v1.

This is the milestone-9 proof: one rule-bearing manifest, advanced by the
single core stepper, animates *identically* in two peer modalities. Where
``polymodal_equivalence_test`` proves the v0 peers agree on a static frame,
these tests prove the v1 spatial and sonic projections agree on *every*
frame of a Game of Life trajectory -- including that a glider has visibly
moved -- so the dynamics layer is polymodal, not just the snapshot.
"""

import unittest

from examples import game_of_life_polymodal as gol
from multilingualprogramming.codegen import process_core, process_projection as pp


class AnimatedEquivalenceTestSuite(unittest.TestCase):
    """Both modalities recover the same cells the core reports, per frame."""

    def _trajectory(self):
        core = gol.game_of_life(10, 10, gol.GLIDER, wrap=True)
        return pp.animate(core, 8)

    def test_one_stepper_drives_both_modalities_every_frame(self):
        trajectory = self._trajectory()
        spatial = pp.to_spatial_animation(trajectory)
        sonic = pp.to_sonic_animation(trajectory)

        self.assertEqual(len(spatial), len(trajectory))
        self.assertEqual(len(sonic), len(trajectory))

        for index, frame in enumerate(trajectory):
            core_cells = process_core.active_cells(frame)
            spatial_cells = pp.live_cells_from_spatial_frame(spatial[index])
            sonic_cells = pp.live_cells_from_sonic_frame(sonic[index])
            # The whole claim, frame by frame: neither modality drifts from
            # the shared stepper's output, and neither drifts from the other.
            self.assertEqual(spatial_cells, core_cells)
            self.assertEqual(sonic_cells, core_cells)
            self.assertEqual(spatial_cells, sonic_cells)

    def test_animation_actually_moves(self):
        # A proof of equivalence on a frozen frame would be hollow; confirm
        # the glider has genuinely translated by (1, 1) after one period.
        trajectory = self._trajectory()
        start = pp.live_cells_from_spatial_frame(pp.to_spatial_frame(trajectory[0], 0))
        moved = pp.live_cells_from_spatial_frame(pp.to_spatial_frame(trajectory[4], 4))
        self.assertEqual(moved, sorted((x + 1, y + 1) for x, y in start))
        self.assertNotEqual(moved, start)

    def test_sonic_frame_is_a_bijection_with_the_lattice(self):
        # Exact (non-lossy) recovery is only honest if the forward map is a
        # bijection; verify a populated frame round-trips without collision.
        core = gol.game_of_life(5, 4, [(0, 0), (4, 3), (2, 1)], wrap=False)
        frame = pp.to_sonic_frame(core, 0)
        self.assertEqual(
            pp.live_cells_from_sonic_frame(frame),
            process_core.active_cells(core),
        )

    def test_projections_consume_trajectory_not_restep(self):
        # Structural guard for the load-bearing rule: the modalities project
        # an already-computed trajectory. Projecting the same frame twice is
        # pure -- it cannot advance the program.
        trajectory = self._trajectory()
        once = pp.to_spatial_frame(trajectory[3], 3)
        twice = pp.to_spatial_frame(trajectory[3], 3)
        self.assertEqual(once, twice)


class OpenPopulationProjectionTestSuite(unittest.TestCase):
    """An unbounded (infinite-topology) program animates through a window."""

    def _trajectory(self):
        core = gol.game_of_life_open(gol.GLIDER)
        return pp.animate(core, 12)

    def test_bounding_box_contains_the_whole_trajectory(self):
        trajectory = self._trajectory()
        vp = pp.bounding_box(trajectory)
        for frame in trajectory:
            for x, y in process_core.active_cells(frame):
                self.assertTrue(pp._in_viewport(x, y, vp))

    def test_one_stepper_drives_both_modalities_within_viewport(self):
        trajectory = self._trajectory()
        spatial = pp.to_spatial_animation(trajectory)
        sonic = pp.to_sonic_animation(trajectory)
        for index, frame in enumerate(trajectory):
            # The auto viewport contains every cell, so the window shows all.
            core_cells = process_core.active_cells(frame)
            spatial_cells = pp.live_cells_from_spatial_frame(spatial[index])
            sonic_cells = pp.live_cells_from_sonic_frame(sonic[index])
            self.assertEqual(spatial_cells, core_cells)
            self.assertEqual(sonic_cells, core_cells)
            self.assertEqual(spatial_cells, sonic_cells)

    def test_unbounded_glider_animates_and_travels(self):
        trajectory = self._trajectory()
        spatial = pp.to_spatial_animation(trajectory)
        start = pp.live_cells_from_spatial_frame(spatial[0])
        end = pp.live_cells_from_spatial_frame(spatial[8])  # two periods
        self.assertEqual(end, sorted((x + 2, y + 2) for x, y in start))

    def test_negative_coordinates_recover_exactly(self):
        # A blinker straddling negative rows must round-trip through both
        # modalities -- the viewport handles a negative origin.
        core = gol.game_of_life_open([(0, -1), (0, 0), (0, 1)])
        frame = pp.animate(core, 0)[0]
        vp = pp.bounding_box([frame])
        spatial = pp.to_spatial_frame(frame, 0, vp)
        sonic = pp.to_sonic_frame(frame, 0, vp)
        self.assertEqual(
            pp.live_cells_from_spatial_frame(spatial),
            process_core.active_cells(core),
        )
        self.assertEqual(
            pp.live_cells_from_sonic_frame(sonic),
            process_core.active_cells(core),
        )


class ViewportClippingTestSuite(unittest.TestCase):
    """A window smaller than the program shows only what it contains."""

    def test_clipping_is_documented_loss_not_silent_corruption(self):
        # Five cells in a row; a 3-wide window centred on them recovers only
        # the three inside. The inverse never invents the clipped cells.
        core = gol.game_of_life_open([(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)])
        frame = pp.animate(core, 0)[0]
        window = {"x0": 1, "y0": 0, "width": 3, "height": 1}
        spatial = pp.to_spatial_frame(frame, 0, window)
        sonic = pp.to_sonic_frame(frame, 0, window)
        inside = [(1, 0), (2, 0), (3, 0)]
        self.assertEqual(pp.live_cells_from_spatial_frame(spatial), inside)
        self.assertEqual(pp.live_cells_from_sonic_frame(sonic), inside)
        # The clipped cells really are still alive in the core.
        self.assertIn((0, 0), process_core.active_cells(core))
        self.assertIn((4, 0), process_core.active_cells(core))


if __name__ == "__main__":
    unittest.main()

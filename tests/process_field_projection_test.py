#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of an animated multi-state field (semantic-core-v1).

``process_projection`` projects a boolean mask (a cell is alive or dead) and
proves spatial == sonic == core for every frame. A *field* carries a value at
every locus, so the projection must preserve that value to stay invertible.
This suite makes the same polymodal claim for the value-aware projection on a
cyclic-dominance ecology: for every animated frame, the field recovered from
the spatial marks equals the field recovered from the sonic voices equals the
core's own ``field_cells`` -- value and all. It also checks the honesty
frontier: a viewport holding the whole field declares (and delivers) an exact
inverse; a clipping viewport declares partial and drops exactly the cells
outside the window.
"""

import unittest

from examples import ecosystem_polymodal as eco
from multilingualprogramming.codegen import process_core
from multilingualprogramming.codegen import process_field_projection as fp

FIELD = "species"


def _trajectory(steps: int = 5):
    return process_core.run(eco.cyclic_dominance(8, 8), steps)


class FieldEquivalenceTestSuite(unittest.TestCase):
    """Spatial and sonic recover the same field as the core, every frame."""

    def test_spatial_equals_sonic_equals_core_each_frame(self):
        trajectory = _trajectory()
        for i, frame in enumerate(trajectory):
            core_field = process_core.field_cells(frame, FIELD)
            spatial = fp.field_from_spatial_frame(fp.to_spatial_frame(frame, i, FIELD))
            sonic = fp.field_from_sonic_frame(fp.to_sonic_frame(frame, i, FIELD))
            self.assertEqual(core_field, spatial)
            self.assertEqual(core_field, sonic)

    def test_marks_and_voices_carry_the_value(self):
        frame = _trajectory(0)[0]
        marks = fp.to_spatial_frame(frame, 0, FIELD)["marks"]
        voices = fp.to_sonic_frame(frame, 0, FIELD)["voices"]
        self.assertTrue(all("value" in m for m in marks))
        self.assertTrue(all("value" in v for v in voices))
        # The full field is projected (every cell exists, not just "active" ones).
        self.assertEqual(len(marks), 64)
        self.assertEqual(len(voices), 64)

    def test_animation_lengths_match_trajectory(self):
        trajectory = _trajectory(4)
        spatial = fp.to_spatial_animation(trajectory, FIELD)
        sonic = fp.to_sonic_animation(trajectory, FIELD)
        self.assertEqual(len(spatial), 5)
        self.assertEqual(len(sonic), 5)


class FieldContractTestSuite(unittest.TestCase):
    """Capability contracts are derived from viewport coverage, and enforced."""

    def test_full_viewport_is_exact_and_tier_one(self):
        trajectory = _trajectory()
        for kind, manifest in (
            (fp.FIELD_SPATIAL_ANIM_KIND, fp.spatial_animation_manifest(trajectory, FIELD)),
            (fp.FIELD_SONIC_ANIM_KIND, fp.sonic_animation_manifest(trajectory, FIELD)),
        ):
            caps = manifest["capabilities"]
            self.assertEqual(manifest["kind"], kind)
            self.assertEqual(caps["inverse"], "exact")
            self.assertEqual(caps["lossy"], [])
            self.assertEqual(caps["tier"]["tier"], 1)

    def test_exact_contract_round_trips_every_cell(self):
        # A contract claiming exact must actually recover the whole field.
        trajectory = _trajectory()
        manifest = fp.spatial_animation_manifest(trajectory, FIELD)
        self.assertEqual(manifest["capabilities"]["inverse"], "exact")
        for frame_idx, spatial_frame in enumerate(manifest["frames"]):
            recovered = fp.field_from_spatial_frame(spatial_frame)
            self.assertEqual(recovered, process_core.field_cells(trajectory[frame_idx], FIELD))

    def test_clipping_viewport_is_partial_and_drops_only_outside_cells(self):
        trajectory = _trajectory()
        viewport = {"x0": 0, "y0": 0, "width": 4, "height": 4}
        caps = fp.projection_capabilities(fp.FIELD_SPATIAL_ANIM_KIND, trajectory, FIELD, viewport)
        self.assertEqual(caps["inverse"], "partial")
        self.assertEqual(caps["lossy"], ["cells-outside-viewport"])
        # The partial recovery must equal exactly the field within the window.
        frame = trajectory[0]
        recovered = fp.field_from_spatial_frame(fp.to_spatial_frame(frame, 0, FIELD, viewport))
        inside = [
            (x, y, v)
            for x, y, v in process_core.field_cells(frame, FIELD)
            if 0 <= x < 4 and 0 <= y < 4
        ]
        self.assertEqual(recovered, inside)

    def test_negative_origin_viewport_round_trips(self):
        # A window with a negative origin must recover global coordinates.
        loci = [{"locus": [x, y], FIELD: (x + y) % 3} for x in (-2, -1, 0) for y in (-2, -1, 0)]
        core = process_core.build_process_core(
            state={"loci": loci},
            topology=process_core.lattice_topology(3, 3, wrap=False),
            rule=eco.cyclic_dominance_rule(3, 3, FIELD),
            schedule=process_core.asynchronous_schedule(),
        )
        viewport = {"x0": -2, "y0": -2, "width": 3, "height": 3}
        spatial = fp.to_spatial_frame(core, 0, FIELD, viewport)
        sonic = fp.to_sonic_frame(core, 0, FIELD, viewport)
        self.assertEqual(
            fp.field_from_spatial_frame(spatial),
            process_core.field_cells(core, FIELD),
        )
        self.assertEqual(
            fp.field_from_sonic_frame(sonic),
            process_core.field_cells(core, FIELD),
        )

    def test_infinite_topology_needs_explicit_viewport(self):
        core = process_core.build_process_core(
            state={"loci": [{"locus": [0, 0], FIELD: 0}], "population": "open",
                   "empty": {FIELD: 0}},
            topology=process_core.infinite_lattice_topology(),
            rule=eco.cyclic_dominance_rule(3, 3, FIELD),
            schedule=process_core.synchronous_schedule(),
        )
        with self.assertRaises(ValueError):
            fp.to_spatial_frame(core, 0, FIELD)


if __name__ == "__main__":
    unittest.main()

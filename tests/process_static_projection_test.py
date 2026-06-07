#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal projection of a migrated (Tier-0) v0 core through the v1 path.

Every other v1 projection reads a topology of its own (lattice / sequence /
graph), so a migrated v0 manifest -- a static structure under a discrete
topology -- could only be rendered by the v0 peer projections, leaving the claim
"even v0 flows through the one v1 projection path" unproven. This suite proves it
against the frozen golden v0 fixture:

- the v0 core is migrated to a Tier-0 v1 core (``process_migration``), then
  projected by ``process_static_projection`` to spatial marks and sonic voices;
- for every animated frame, the entities recovered from the spatial marks equal
  the entities recovered from the sonic voices equal the migrated core's own
  loci -- record for record, every scalar intact (the same polymodal claim the
  lattice/field projections make, on the static structure v0 is);
- the round-trip recovers the *original v0 entities* exactly, so projecting a v0
  program through the v1 path loses nothing;
- the contract is Tier 0 and unconditionally exact (a static structure is
  "invertible everywhere"); there is no viewport to clip.
"""

import json
import unittest
from pathlib import Path

from multilingualprogramming.codegen import (
    process_capabilities as caps,
    process_core,
    process_migration as mig,
    process_static_projection as sp,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_V0 = ROOT / "tests" / "fixtures" / "polymodal" / "semantic_core_v0_sample.json"


def _load_v0():
    return json.loads(GOLDEN_V0.read_text(encoding="utf-8"))


def _migrated_core():
    return mig.migrate_v0_to_v1(_load_v0())


class StaticEquivalenceTestSuite(unittest.TestCase):
    """Spatial and sonic recover the same entities as the core, every frame."""

    def test_spatial_equals_sonic_equals_core_each_frame(self):
        core = _migrated_core()
        # The one shared stepper produces motion even for a static program;
        # every frame is identical, which is exactly the Tier-0 claim.
        trajectory = sp.animate(core, 3)
        loci = mig.recover_v0_entities(core)
        expected = sorted(loci, key=lambda rec: rec["index"])
        for i, frame in enumerate(trajectory):
            spatial = sp.entities_from_spatial_frame(sp.to_spatial_frame(frame, i))
            sonic = sp.entities_from_sonic_frame(sp.to_sonic_frame(frame, i))
            self.assertEqual(expected, spatial)
            self.assertEqual(expected, sonic)

    def test_round_trip_recovers_original_v0_entities_exactly(self):
        # Projecting a v0 program through the v1 path and inverting it must hand
        # back the original v0 entities, scalar for scalar -- nothing lost, no
        # field reinterpreted.
        v0 = _load_v0()
        core = mig.migrate_v0_to_v1(v0)
        frame = sp.animate(core, 0)[0]
        recovered = sp.entities_from_spatial_frame(sp.to_spatial_frame(frame, 0))
        expected = sorted(v0["entities"], key=lambda rec: rec["index"])
        self.assertEqual(expected, recovered)

    def test_placement_uses_only_index_and_channel(self):
        # Placement reads the two fields that already ARE positions; every other
        # scalar rides verbatim in the payload, untouched and unplaced.
        frame = sp.animate(_migrated_core(), 0)[0]
        entity = frame["state"]["loci"][0]
        mark = sp.to_spatial_frame(frame, 0)["marks"][0]
        self.assertEqual(mark["x"], entity["index"])
        self.assertEqual(mark["y"], entity["channel"])
        self.assertNotIn("index", mark["payload"])
        self.assertNotIn("channel", mark["payload"])
        # The record's other scalars survive in the payload, unreinterpreted.
        for field in ("id", "opcode", "name", "intensity", "signal", "phase"):
            self.assertEqual(mark["payload"][field], entity[field])

    def test_one_mark_and_voice_per_entity(self):
        core = _migrated_core()
        n = len(core["state"]["loci"])
        frame = sp.animate(core, 0)[0]
        self.assertEqual(len(sp.to_spatial_frame(frame, 0)["marks"]), n)
        self.assertEqual(len(sp.to_sonic_frame(frame, 0)["voices"]), n)

    def test_animation_lengths_match_trajectory(self):
        trajectory = sp.animate(_migrated_core(), 4)
        self.assertEqual(len(sp.to_spatial_animation(trajectory)), 5)
        self.assertEqual(len(sp.to_sonic_animation(trajectory)), 5)


class StaticContractTestSuite(unittest.TestCase):
    """The contract is Tier 0 and unconditionally exact."""

    def test_contract_is_tier_zero_and_exact(self):
        trajectory = sp.animate(_migrated_core(), 2)
        for kind, manifest in (
            (sp.STATIC_SPATIAL_ANIM_KIND, sp.spatial_animation_manifest(trajectory)),
            (sp.STATIC_SONIC_ANIM_KIND, sp.sonic_animation_manifest(trajectory)),
        ):
            contract = manifest["capabilities"]
            self.assertEqual(contract["projection"], kind)
            self.assertEqual(contract["inverse"], "exact")
            self.assertEqual(contract["lossy"], [])
            self.assertEqual(contract["tier"]["tier"], 0)
            self.assertEqual(len(manifest["frames"]), 3)

    def test_exact_contract_round_trips_every_entity(self):
        # Enforce the declaration: an "exact" contract must actually recover the
        # full structure (mirrors the field projection's contract enforcement).
        core = _migrated_core()
        trajectory = sp.animate(core, 1)
        manifest = sp.spatial_animation_manifest(trajectory)
        self.assertEqual(manifest["capabilities"]["inverse"], "exact")
        expected = sorted(mig.recover_v0_entities(core), key=lambda r: r["index"])
        for frame in manifest["frames"]:
            self.assertEqual(sp.entities_from_spatial_frame(frame), expected)

    def test_tier_matches_the_core_classifier(self):
        core = _migrated_core()
        self.assertEqual(caps.expressiveness_tier(core), 0)


class StaticValidationTestSuite(unittest.TestCase):
    """The projection refuses cores it cannot faithfully render."""

    def test_non_static_schedule_is_rejected(self):
        # A program that actually moves is not this projection's job -- the
        # lattice / field / graph projections render those.
        moving = process_core.build_process_core(
            state={"loci": [{"index": 0, "channel": 0, "locus": [0, 0], "alive": 1}]},
            topology=process_core.lattice_topology(1, 1),
            rule=process_core.rewrite_rule(clauses=[], default={}),
            schedule=process_core.synchronous_schedule(),
        )
        with self.assertRaises(ValueError):
            sp.to_spatial_frame(moving, 0)

    def test_locus_without_placement_is_rejected(self):
        core = _migrated_core()
        core["state"]["loci"][0].pop("channel")
        with self.assertRaises(ValueError):
            sp.to_sonic_frame(core, 0)

    def test_non_v1_manifest_is_rejected(self):
        with self.assertRaises(ValueError):
            sp.to_spatial_frame({"kind": "semantic-core-v0", "schedule": {}, "state": {"loci": []}}, 0)


if __name__ == "__main__":
    unittest.main()

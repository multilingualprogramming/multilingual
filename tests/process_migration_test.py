#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Explicit semantic-core-v0 -> v1 migration.

The versioning promise: a v0 manifest keeps meaning exactly what it meant,
and v1 may only enrich it through an explicit migration that never silently
reinterprets a field. These tests pin that down against the frozen golden v0
fixture:

- every v0 entity and relation survives the migration *verbatim*;
- the result is a Tier-0 static program whose stepping is a verified no-op;
- the migration round-trips (recovering the original entities exactly);
- a non-v0 input is rejected rather than mangled.

They also confirm the static-schedule identity holds identically in the JS
stepper (under Node), so the v0-as-v1 no-op is not a Python-only convention.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from multilingualprogramming.codegen import (
    process_capabilities as caps,
    process_core,
    process_migration as mig,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_V0 = ROOT / "tests" / "fixtures" / "polymodal" / "semantic_core_v0_sample.json"
CORE_JS = ROOT / "docs" / "browser" / "process-dynamics" / "process_core.js"
NODE = shutil.which("node")


def _load_v0():
    return json.loads(GOLDEN_V0.read_text(encoding="utf-8"))


class MigrationFaithfulnessTestSuite(unittest.TestCase):
    """Nothing is reinterpreted; everything is carried through."""

    def setUp(self):
        self.v0 = _load_v0()
        self.v1 = mig.migrate_v0_to_v1(self.v0)

    def test_envelope_is_v1_static_tier_zero(self):
        self.assertEqual(self.v1["kind"], process_core.CORE_KIND)
        self.assertEqual(self.v1["version"], process_core.CORE_VERSION)
        self.assertEqual(self.v1["schedule"]["kind"], process_core.SCHEDULE_STATIC)
        self.assertEqual(self.v1["rule"]["clauses"], [])
        self.assertEqual(self.v1["migrated_from"], "semantic-core-v0")
        self.assertTrue(mig.is_migrated_v0(self.v1))
        tier = caps.tier_contract(self.v1)
        self.assertEqual(tier["tier"], 0)
        self.assertEqual(tier["name"], "static structure")

    def test_entities_are_carried_verbatim_as_loci(self):
        self.assertEqual(self.v1["state"]["loci"], self.v0["entities"])

    def test_relations_are_carried_verbatim(self):
        self.assertEqual(self.v1["relations"], self.v0["relations"])

    def test_source_is_preserved(self):
        self.assertEqual(self.v1["source"], self.v0.get("source", ""))

    def test_no_field_is_reinterpreted(self):
        # Spot-check that semantic fields keep their exact values -- the
        # migration must not turn phase into a position or intensity into an
        # amplitude (those are projection concerns).
        for original, locus in zip(self.v0["entities"], self.v1["state"]["loci"]):
            for field in ("id", "index", "opcode", "name",
                          "intensity", "signal", "phase", "channel"):
                self.assertEqual(locus[field], original[field])

    def test_migration_is_a_deep_copy_not_an_alias(self):
        # Mutating the migrated core must not reach back into the v0 manifest.
        self.v1["state"]["loci"][0]["intensity"] = -999
        self.assertNotEqual(self.v0["entities"][0]["intensity"], -999)


class MigratedSteppingTestSuite(unittest.TestCase):
    """A static snapshot does not evolve."""

    def test_stepping_is_identity(self):
        v1 = mig.migrate_v0_to_v1(_load_v0())
        trajectory = process_core.run(v1, 4)
        self.assertEqual(len(trajectory), 5)
        for frame in trajectory:
            self.assertEqual(frame["state"]["loci"], v1["state"]["loci"])

    def test_step_does_not_require_lattice_or_coordinates(self):
        # The migrated core has a "discrete" topology and loci without any
        # "locus" coordinate; stepping must still succeed (identity).
        v1 = mig.migrate_v0_to_v1(_load_v0())
        self.assertNotIn("locus", v1["state"]["loci"][0])
        stepped = process_core.step(v1)
        self.assertEqual(stepped["state"]["loci"], v1["state"]["loci"])

    def test_round_trip_recovers_original_entities(self):
        v0 = _load_v0()
        recovered = mig.recover_v0_entities(mig.migrate_v0_to_v1(v0))
        self.assertEqual(recovered, v0["entities"])


class MigrationRejectionTestSuite(unittest.TestCase):
    """Only v0 manifests are accepted."""

    def test_non_v0_kind_raises(self):
        with self.assertRaises(ValueError):
            mig.migrate_v0_to_v1({"kind": "semantic-core-v1", "entities": []})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            mig.migrate_v0_to_v1([1, 2, 3])


@unittest.skipUnless(NODE, "node is not installed")
class StaticScheduleJsParityTestSuite(unittest.TestCase):
    """The static-schedule no-op must hold identically in the JS stepper."""

    _STATE_DRIVER = """\
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [, , corePath, manifestPath, steps] = process.argv;
const { run } = await import(pathToFileURL(corePath).href);
const core = JSON.parse(readFileSync(manifestPath, 'utf-8'));
process.stdout.write(JSON.stringify(run(core, Number(steps)).map((f) => f.state.loci)));
"""

    def test_js_steps_migrated_core_as_identity(self):
        v1 = mig.migrate_v0_to_v1(_load_v0())
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "migrated.v1.json"
            manifest.write_text(json.dumps(v1), encoding="utf-8")
            driver = Path(tmp) / "driver.mjs"
            driver.write_text(self._STATE_DRIVER, encoding="utf-8")
            out = subprocess.run(
                [NODE, str(driver), str(CORE_JS), str(manifest), "3"],
                capture_output=True, text=True, check=True,
            )
        js = json.loads(out.stdout)
        py = [f["state"]["loci"] for f in process_core.run(v1, 3)]
        self.assertEqual(js, py)
        # Identity: every frame equals the original loci.
        for frame in js:
            self.assertEqual(frame, v1["state"]["loci"])


if __name__ == "__main__":
    unittest.main()

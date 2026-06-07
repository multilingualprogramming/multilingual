#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Continuous-time dynamics: the continuous-dt schedule + rate rule axis.

Game of Life, the L-system and the cyclic ecology are all *discrete* rewriting.
Diffusion is the first program on the *continuous* axis: there is no pattern
match, only a rate of change integrated over time. These tests pin down the new
axis end to end:

- the rate rule and continuous-dt schedule are genuine continuous dynamics (the
  field moves, unlike a static snapshot) -- a hot spot relaxes while a toroidal
  mean-stencil conserves total mass exactly;
- the step is deterministic, does not mutate its input, and classifies as
  Tier 1 (fixed-population continuous dynamics) -- swapping only the schedule to
  synchronous would NOT move it (a rate rule is never a discrete rewrite), so
  the classifier reads the axis, not a label;
- the same value-aware field projection that renders the ecology renders this
  continuous field, exactly invertible (spatial == sonic == core) frame by
  frame -- continuous values and all;
- the `.multi` program (en + fr) lowers to a core byte-identical to the Python
  oracle and steps identically, so the textual front door adds no drift and the
  multilingual claim holds on continuous dynamics too.
"""

import json
import unittest
from pathlib import Path

from examples import diffusion_polymodal as df
from multilingualprogramming.codegen import (
    process_capabilities as caps,
    process_core,
    process_field_projection as fp,
    process_program as pproc,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
EN_SOURCE = EXAMPLES / "diffusion.multi"
FR_SOURCE = EXAMPLES / "diffusion.fr.multi"

FIELD = "u"


def _build(source_path: Path, language: str = "en") -> dict:
    return pproc.execute_process(
        source_path.read_text(encoding="utf-8"),
        language=language,
        source_path=str(source_path),
    )


def _mass(frame) -> float:
    return sum(v for _, _, v in process_core.field_cells(frame, FIELD))


def _peak(frame) -> float:
    return max(v for _, _, v in process_core.field_cells(frame, FIELD))


class ContinuousEngineTestSuite(unittest.TestCase):
    """The rate rule integrates a genuine continuous dynamics."""

    def test_field_moves_and_relaxes(self):
        core = df.diffusion_field(11, 11)
        trajectory = process_core.run(core, 6)
        # Unlike a static snapshot, the field changes...
        self.assertNotEqual(
            process_core.field_cells(trajectory[0], FIELD),
            process_core.field_cells(trajectory[1], FIELD),
        )
        # ...and the seeded bump relaxes (its peak strictly decreases).
        peaks = [_peak(f) for f in trajectory]
        self.assertTrue(all(b < a for a, b in zip(peaks, peaks[1:])))

    def test_toroidal_mean_stencil_conserves_mass(self):
        core = df.diffusion_field(9, 9)
        masses = [_mass(f) for f in process_core.run(core, 10)]
        for m in masses:
            self.assertAlmostEqual(m, masses[0], places=12)

    def test_pure_decay_without_neighbor_term(self):
        # A rate rule may speak only of a cell's own value: exponential decay,
        # du/dt = -0.5 u, no neighbour coupling.
        rule = process_core.rate_rule({"u": {"self": {"u": -0.5}}})
        loci = [{"locus": [0, 0], "u": 1.0}]
        core = process_core.build_process_core(
            state={"loci": loci},
            topology=process_core.lattice_topology(1, 1),
            rule=rule,
            schedule=process_core.continuous_schedule(1.0),
        )
        trajectory = process_core.run(core, 3)
        values = [process_core.field_cells(f, FIELD)[0][2] for f in trajectory]
        self.assertEqual(values, [1.0, 0.5, 0.25, 0.125])

    def test_step_is_deterministic_and_pure(self):
        core = df.diffusion_field(7, 7)
        before = json.dumps(core)
        a = json.dumps([process_core.field_cells(f, FIELD) for f in process_core.run(core, 5)])
        b = json.dumps([process_core.field_cells(f, FIELD) for f in process_core.run(core, 5)])
        self.assertEqual(a, b)  # deterministic
        self.assertEqual(json.dumps(core), before)  # input unmutated

    def test_dt_is_part_of_the_schedule(self):
        # Halving dt halves the first-step change -- the step size is real data.
        big = df.diffusion_field(5, 5, dt=1.0)
        small = df.diffusion_field(5, 5, dt=0.5)
        c = 2  # the seeded centre on a 5x5 grid
        b1 = process_core.run(big, 1)[1]
        s1 = process_core.run(small, 1)[1]
        by = {(x, y): v for x, y, v in process_core.field_cells(b1, FIELD)}
        sy = {(x, y): v for x, y, v in process_core.field_cells(s1, FIELD)}
        # centre dropped from 1.0; the small-dt drop is half the big-dt drop.
        self.assertAlmostEqual(1.0 - sy[(c, c)], (1.0 - by[(c, c)]) / 2, places=12)


class ContinuousTierTestSuite(unittest.TestCase):
    """Continuous-dt on a fixed lattice is Tier 1, read from the axes."""

    def test_diffusion_is_tier_one(self):
        self.assertEqual(caps.expressiveness_tier(df.diffusion_field(8, 8)), 1)

    def test_rate_rule_is_not_misread_as_static(self):
        # A rate rule has no `clauses`; the classifier must not treat that as an
        # empty (static, Tier-0) rewrite rule.
        core = df.diffusion_field(8, 8)
        self.assertNotEqual(core["rule"].get("clauses"), [])
        self.assertEqual(core["rule"]["kind"], process_core.RULE_RATE)
        self.assertNotEqual(caps.expressiveness_tier(core), 0)


class ContinuousGuardTestSuite(unittest.TestCase):
    """The engine refuses the axis combinations it does not yet specify."""

    def test_continuous_with_non_rate_rule_raises(self):
        core = df.diffusion_field(4, 4)
        core = {**core, "rule": process_core.rewrite_rule(clauses=[], default={})}
        with self.assertRaises(NotImplementedError):
            process_core.step(core)

    def test_continuous_open_population_raises(self):
        core = df.diffusion_field(4, 4)
        core = {**core, "state": {**core["state"], "population": process_core.POPULATION_OPEN}}
        with self.assertRaises(NotImplementedError):
            process_core.step(core)

    def test_negative_or_zero_dt_rejected(self):
        with self.assertRaises(ValueError):
            process_core.continuous_schedule(0)
        with self.assertRaises(ValueError):
            process_core.continuous_schedule(-1.0)


class ContinuousFieldProjectionTestSuite(unittest.TestCase):
    """The value-aware field projection renders the continuous field exactly."""

    def test_spatial_equals_sonic_equals_core_each_frame(self):
        trajectory = process_core.run(df.diffusion_field(9, 9), 6)
        for i, frame in enumerate(trajectory):
            core_field = process_core.field_cells(frame, FIELD)
            spatial = fp.field_from_spatial_frame(fp.to_spatial_frame(frame, i, FIELD))
            sonic = fp.field_from_sonic_frame(fp.to_sonic_frame(frame, i, FIELD))
            self.assertEqual(core_field, spatial)
            self.assertEqual(core_field, sonic)

    def test_full_viewport_contract_is_exact_tier_one(self):
        trajectory = process_core.run(df.diffusion_field(9, 9), 4)
        contract = fp.projection_capabilities(fp.FIELD_SPATIAL_ANIM_KIND, trajectory, FIELD)
        self.assertEqual(contract["inverse"], "exact")
        self.assertEqual(contract["lossy"], [])
        self.assertEqual(contract["tier"]["tier"], 1)


class ContinuousMultiTestSuite(unittest.TestCase):
    """The .multi program lowers to the oracle and across languages."""

    def test_builds_a_continuous_core(self):
        core = _build(EN_SOURCE)
        self.assertEqual(core["kind"], "semantic-core-v1")
        self.assertEqual(core["schedule"]["kind"], process_core.SCHEDULE_CONTINUOUS)
        self.assertEqual(core["rule"]["kind"], process_core.RULE_RATE)
        self.assertEqual(core["topology"]["kind"], process_core.TOPOLOGY_LATTICE)

    def test_byte_identical_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = df.diffusion_field(11, 11, source_path=core["source"])
        self.assertEqual(core, reference)

    def test_steps_identically_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = df.diffusion_field(11, 11, source_path=core["source"])
        built = [process_core.field_cells(f, FIELD) for f in process_core.run(core, 6)]
        expected = [process_core.field_cells(f, FIELD) for f in process_core.run(reference, 6)]
        self.assertEqual(built, expected)

    def test_english_and_french_lower_to_identical_core(self):
        en = _build(EN_SOURCE, language="en")
        fr = _build(FR_SOURCE, language="fr")
        en.pop("source")
        fr.pop("source")
        self.assertEqual(en, fr)


if __name__ == "__main__":
    unittest.main()

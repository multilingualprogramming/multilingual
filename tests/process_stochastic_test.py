#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""The stochastic axis: the `chance` clause predicate and its deterministic RNG.

Game of Life, the ecology, the L-system, diffusion and Gray-Scott are all
deterministic. `chance` adds the one ingredient they lack -- a clause that fires
only a fraction of the time -- without giving up reproducibility: the roll is a
pure hash of (locus, step, salt), so a stochastic trajectory is still a
deterministic function of the manifest, identical in every runtime. These tests
pin the hash, the predicate's gating, and the Eden-growth example end to end.
"""

import json
import unittest
from pathlib import Path

from multilingualprogramming.codegen import (
    process_capabilities as caps,
    process_core,
    process_program as pproc,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
EDEN_EN = EXAMPLES / "eden_growth.multi"
EDEN_FR = EXAMPLES / "eden_growth.fr.multi"


def _alive(core):
    return process_core.active_cells(core, "alive")


def _single(rule, schedule=None, **seed_fields):
    loci = [{"locus": [0, 0], **seed_fields}]
    return process_core.build_process_core(
        state={"loci": loci},
        topology=process_core.lattice_topology(1, 1),
        rule=rule,
        schedule=schedule or process_core.synchronous_schedule(),
    )


class HashTestSuite(unittest.TestCase):
    """The deterministic [0, 1) hash backing `chance`."""

    def test_values_are_in_unit_interval(self):
        for x in range(0, 50, 7):
            for y in range(0, 50, 5):
                v = process_core._hash01(x, y, 3, 0)
                self.assertGreaterEqual(v, 0.0)
                self.assertLess(v, 1.0)

    def test_is_pure_and_repeatable(self):
        self.assertEqual(
            process_core._hash01(13, 27, 5, 9), process_core._hash01(13, 27, 5, 9)
        )

    def test_varies_with_each_input(self):
        base = process_core._hash01(3, 4, 5, 6)
        self.assertNotEqual(base, process_core._hash01(4, 4, 5, 6))  # x
        self.assertNotEqual(base, process_core._hash01(3, 5, 5, 6))  # y
        self.assertNotEqual(base, process_core._hash01(3, 4, 6, 6))  # step
        self.assertNotEqual(base, process_core._hash01(3, 4, 5, 7))  # salt

    def test_distribution_is_roughly_uniform(self):
        vals = [process_core._hash01(x, y, 1, 0) for x in range(64) for y in range(64)]
        mean = sum(vals) / len(vals)
        self.assertTrue(0.45 < mean < 0.55, f"mean {mean} not near 0.5")


class ChancePredicateTestSuite(unittest.TestCase):
    """`chance(p)` gates a clause by probability, deterministically."""

    def _grid_fraction(self, p, salt=0):
        # 40x40 cells, each rolls once at step 0; report the fraction that fire.
        n = 40
        rule = process_core.rewrite_rule(
            clauses=[{"match": {"chance": {"p": p, "salt": salt}}, "produce": {"on": 1}}],
            default={"on": 0},
        )
        loci = [{"locus": [x, y], "on": 0} for x in range(n) for y in range(n)]
        core = process_core.build_process_core(
            state={"loci": loci},
            topology=process_core.lattice_topology(n, n),
            rule=rule,
            schedule=process_core.synchronous_schedule(),
        )
        after = process_core.run(core, 1)[1]
        fired = sum(1 for _, _, v in process_core.field_cells(after, "on") if v == 1)
        return fired / (n * n)

    def test_probability_zero_never_fires(self):
        self.assertEqual(self._grid_fraction(0.0), 0.0)

    def test_probability_one_always_fires(self):
        self.assertEqual(self._grid_fraction(1.0), 1.0)

    def test_probability_is_approximately_honoured(self):
        # The hash is roughly uniform, so ~p of cells fire (sampled over 1600).
        self.assertAlmostEqual(self._grid_fraction(0.3), 0.3, delta=0.05)

    def test_chance_combinator_builds_the_predicate(self):
        cl = process_core.clause(
            process_core.when(alive=0),
            process_core.chance(0.25, 7),
            process_core.becomes(alive=1),
        )
        self.assertEqual(cl["match"]["chance"], {"p": 0.25, "salt": 7})

    def test_salt_decorrelates_two_clauses(self):
        # Same cell+step, different salt -> independent rolls.
        a = self._grid_fraction(0.5, salt=0)
        b = self._grid_fraction(0.5, salt=12345)
        self.assertNotEqual(a, b)


class EdenGrowthTestSuite(unittest.TestCase):
    """The stochastic Eden cluster, authored end to end in .multi."""

    def _build(self, path, language="en"):
        return pproc.execute_process(
            path.read_text(encoding="utf-8"), language=language, source_path=str(path)
        )

    def test_builds_a_stochastic_synchronous_core(self):
        core = self._build(EDEN_EN)
        self.assertEqual(core["schedule"]["kind"], process_core.SCHEDULE_SYNCHRONOUS)
        self.assertEqual(core["rule"]["kind"], process_core.RULE_REWRITE)
        self.assertIn("chance", core["rule"]["clauses"][0]["match"])

    def test_cluster_grows_monotonically_from_one_seed(self):
        core = self._build(EDEN_EN)
        counts = [len(_alive(f)) for f in process_core.run(core, 20)]
        self.assertEqual(counts[0], 1)
        self.assertTrue(all(b >= a for a, b in zip(counts, counts[1:])))  # never shrinks
        self.assertGreater(counts[-1], 50)  # and it genuinely spread

    def test_step_is_deterministic_and_pure(self):
        core = self._build(EDEN_EN)
        before = json.dumps(core)
        a = json.dumps([_alive(f) for f in process_core.run(core, 12)])
        b = json.dumps([_alive(f) for f in process_core.run(core, 12)])
        self.assertEqual(a, b)
        self.assertEqual(json.dumps(core), before)

    def test_is_tier_two_synchronous_lattice(self):
        self.assertEqual(caps.expressiveness_tier(self._build(EDEN_EN)), 2)

    def test_english_and_french_lower_to_identical_core(self):
        en = self._build(EDEN_EN, "en")
        fr = self._build(EDEN_FR, "fr")
        en.pop("source")
        fr.pop("source")
        self.assertEqual(en, fr)


if __name__ == "__main__":
    unittest.main()

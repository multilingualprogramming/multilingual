#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""L-systems: generative string rewriting through the one process core.

Game of Life exercises lattice + totalistic rules; an L-system exercises the
other half of the rewrite primitive the research doc promised -- a
*production* whose replacement is longer than its match, so the structure
grows ("generativity/recursion for free"). These tests prove that the shared
stepper runs a Lindenmayer system authored in ``.multi`` (no Python) and
yields the canonical algae generations, and that the engine still names no
specific system (the production data lives in the example).
"""

import unittest
from pathlib import Path

from multilingualprogramming.codegen import process_core as pc
from multilingualprogramming.codegen import process_capabilities as caps
from multilingualprogramming.codegen import process_program as pproc

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
LSYSTEM_SOURCE = EXAMPLES / "lindenmayer.multi"

# Lindenmayer's 1968 algae system: axiom A, A->AB, B->A. Lengths are Fibonacci.
ALGAE = ["A", "AB", "ABA", "ABAAB", "ABAABABA", "ABAABABAABAAB"]


def _word(core):
    return "".join(pc.sequence_symbols(core))


class GenerativeStepperTestSuite(unittest.TestCase):
    """The core stepper grows a sequence under a generative schedule."""

    def _algae_core(self):
        rule = pc.rewrite_rule(
            [
                {"match": {"self": {"symbol": "A"}},
                 "produce": [{"symbol": "A"}, {"symbol": "B"}]},
                {"match": {"self": {"symbol": "B"}},
                 "produce": [{"symbol": "A"}]},
            ],
            None,
        )
        return pc.build_process_core(
            state={"sequence": [{"symbol": "A"}]},
            topology=pc.sequence_topology(),
            rule=rule,
            schedule=pc.generative_schedule(),
        )

    def test_produces_canonical_algae_generations(self):
        core = self._algae_core()
        words = [_word(frame) for frame in pc.run(core, 5)]
        self.assertEqual(words, ALGAE)

    def test_lengths_follow_fibonacci(self):
        core = self._algae_core()
        lengths = [len(_word(frame)) for frame in pc.run(core, 6)]
        self.assertEqual(lengths, [1, 2, 3, 5, 8, 13, 21])

    def test_unmatched_symbol_maps_to_itself(self):
        # A constant symbol with no production passes through unchanged --
        # the standard L-system identity for terminals like '+'/'-'/'['.
        rule = pc.rewrite_rule(
            [{"match": {"self": {"symbol": "A"}},
              "produce": [{"symbol": "A"}, {"symbol": "+"}]}],
            None,
        )
        core = pc.build_process_core(
            state={"sequence": [{"symbol": "A"}, {"symbol": "+"}]},
            topology=pc.sequence_topology(),
            rule=rule,
            schedule=pc.generative_schedule(),
        )
        nxt = pc.step(core)
        self.assertEqual(_word(nxt), "A++")

    def test_step_does_not_mutate_input(self):
        core = self._algae_core()
        before = _word(core)
        pc.step(core)
        self.assertEqual(_word(core), before)

    def test_classified_as_generative_tier_three(self):
        self.assertEqual(caps.expressiveness_tier(self._algae_core()), 3)


class LSystemMultiProgramTestSuite(unittest.TestCase):
    """The .multi L-system authors the same generative core, no Python."""

    def _build(self):
        return pproc.execute_process(
            LSYSTEM_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=str(LSYSTEM_SOURCE),
        )

    def test_builds_sequence_generative_core(self):
        core = self._build()
        self.assertEqual(core["kind"], pc.CORE_KIND)
        self.assertEqual(core["topology"]["kind"], pc.TOPOLOGY_SEQUENCE)
        self.assertEqual(core["schedule"]["kind"], pc.SCHEDULE_GENERATIVE)
        self.assertEqual(_word(core), "A")

    def test_multi_program_runs_canonical_algae(self):
        words = [_word(frame) for frame in pc.run(self._build(), 5)]
        self.assertEqual(words, ALGAE)

    def test_authored_without_python(self):
        text = LSYSTEM_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("import", text)
        self.assertIn("generative_schedule", text)

    def test_tier_three_generative(self):
        self.assertEqual(caps.expressiveness_tier(self._build()), 3)


class EngineNamesNoSystemTestSuite(unittest.TestCase):
    """The core remains system-agnostic after the generative extension.

    Mirrors the existing guard in ``process_core_test``: the language must
    not name a program. The generative axis is general (sequence topology +
    generative schedule + productions-as-data); the algae L-system lives in
    ``examples/lindenmayer.multi``, not in the core's symbols.
    """

    def test_core_module_exposes_no_lsystem_symbols(self):
        names = [name.lower() for name in dir(pc)]
        for token in ("lindenmayer", "algae", "lsystem", "l_system"):
            self.assertFalse(
                any(token in name for name in names),
                f"process_core must not name a specific system ({token})",
            )


if __name__ == "__main__":
    unittest.main()

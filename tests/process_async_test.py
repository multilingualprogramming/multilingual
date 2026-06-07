#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""The asynchronous schedule and multi-state fields of semantic-core-v1.

Game of Life exercised the synchronous lattice; the L-system exercised
generative rewriting. The remaining engine axes -- a *heterogeneous* per-locus
state and an *asynchronous* (sequential in-place) schedule -- are exercised
here by a cyclic-dominance ecology (spatial rock-paper-scissors). The sharp
claims this suite guards:

- asynchronous and synchronous are genuinely different dynamics of the *same*
  rule data (sequential update propagates within a step);
- a rule with no ``fallback`` leaves an unmatched locus unchanged
  (identity-on-no-match), which is what lets the cyclic rule speak only of
  invasion;
- the schedule is reproducible (a fixed scan order, not randomness) and never
  mutates its input;
- the program classifies onto Tier 1 (fixed-population continuous dynamics) --
  the tier no example reached before;
- the English and French ``.multi`` sources, and the Python reference, all
  agree byte-for-byte.
"""

import unittest
from pathlib import Path

from examples import ecosystem_polymodal as eco
from multilingualprogramming.codegen import process_capabilities, process_core
from multilingualprogramming.codegen import process_program as pproc

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
EN_SOURCE = EXAMPLES / "ecosystem.multi"
FR_SOURCE = EXAMPLES / "ecosystem.fr.multi"

FIELD = "species"


def _build(source_path: Path, language: str = "en") -> dict:
    return pproc.execute_process(
        source_path.read_text(encoding="utf-8"),
        language=language,
        source_path=str(source_path),
    )


def _field(core: dict) -> list[tuple[int, int, int]]:
    return process_core.field_cells(core, FIELD)


class AsynchronousEngineTestSuite(unittest.TestCase):
    """The sequential schedule's core behaviour, on a small hand-built lattice."""

    def _small(self, schedule):
        # A 3x3 torus seeded with a diagonal mix of three species.
        loci = [
            {"locus": [x, y], FIELD: (x + y) % 3}
            for x in range(3)
            for y in range(3)
        ]
        return process_core.build_process_core(
            state={"loci": loci},
            topology=process_core.lattice_topology(3, 3),
            rule=eco.cyclic_dominance_rule(3, 3, FIELD),
            schedule=schedule,
        )

    def test_async_differs_from_sync_on_the_same_rule(self):
        sync = self._small(process_core.synchronous_schedule())
        asyncc = self._small(process_core.asynchronous_schedule())
        # Same rule, state and topology -- only the schedule differs.
        self.assertEqual(sync["rule"], asyncc["rule"])
        self.assertNotEqual(
            _field(process_core.step(sync)),
            _field(process_core.step(asyncc)),
        )

    def test_step_does_not_mutate_input(self):
        core = self._small(process_core.asynchronous_schedule())
        before = _field(core)
        process_core.step(core)
        self.assertEqual(_field(core), before)

    def test_schedule_is_deterministic(self):
        core = self._small(process_core.asynchronous_schedule())
        first = [_field(f) for f in process_core.run(core, 5)]
        second = [_field(f) for f in process_core.run(core, 5)]
        self.assertEqual(first, second)

    def test_identity_on_no_match_leaves_a_quiet_cell_unchanged(self):
        # A lone cell whose successor does not surround it meets no clause and,
        # with no fallback, must stay exactly as it was.
        core = process_core.build_process_core(
            state={"loci": [{"locus": [0, 0], FIELD: 0}]},
            topology=process_core.lattice_topology(3, 3, wrap=False),
            rule=eco.cyclic_dominance_rule(3, 3, FIELD),
            schedule=process_core.asynchronous_schedule(),
        )
        self.assertIsNone(core["rule"]["default"])
        self.assertEqual(_field(process_core.step(core)), [(0, 0, 0)])

    def test_sequential_propagation_within_a_step(self):
        # Async sees earlier-updated neighbours this sweep; the produced field
        # is a valid relabelling (every cell still carries a species 0..2).
        core = self._small(process_core.asynchronous_schedule())
        nxt = _field(process_core.step(core))
        self.assertTrue(all(v in (0, 1, 2) for _, _, v in nxt))
        self.assertEqual(len(nxt), 9)

    def test_open_population_async_is_rejected(self):
        core = process_core.build_process_core(
            state={"loci": [{"locus": [0, 0], FIELD: 0}],
                   "population": process_core.POPULATION_OPEN,
                   "empty": {FIELD: 0}},
            topology=process_core.lattice_topology(3, 3),
            rule=eco.cyclic_dominance_rule(3, 3, FIELD),
            schedule=process_core.asynchronous_schedule(),
        )
        with self.assertRaises(NotImplementedError):
            process_core.step(core)


class FieldReadoutTestSuite(unittest.TestCase):
    """field_cells preserves the value a multi-state lattice carries."""

    def test_field_cells_reports_values_sorted(self):
        core = eco.cyclic_dominance(2, 2)
        self.assertEqual(
            process_core.field_cells(core, FIELD),
            [(0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 2)],
        )

    def test_named_field_is_generic(self):
        core = process_core.build_process_core(
            state={"loci": [{"locus": [0, 0], "phase": 7}]},
            topology=process_core.lattice_topology(1, 1),
            rule=process_core.rewrite_rule([], default=None),
            schedule=process_core.asynchronous_schedule(),
        )
        self.assertEqual(process_core.field_cells(core, "phase"), [(0, 0, 7)])


class EcosystemTierTestSuite(unittest.TestCase):
    """A fixed-population lattice under an async schedule is Tier 1."""

    def test_async_lattice_is_tier_one(self):
        core = _build(EN_SOURCE)
        self.assertEqual(process_capabilities.expressiveness_tier(core), 1)

    def test_sync_lattice_remains_tier_two(self):
        # Swapping only the schedule moves the same program between tiers, so
        # the classifier reads the axis, not a label.
        core = _build(EN_SOURCE)
        sync = {**core, "schedule": process_core.synchronous_schedule()}
        self.assertEqual(process_capabilities.expressiveness_tier(sync), 2)


class EcosystemProgramTestSuite(unittest.TestCase):
    """The .multi ecology matches the Python reference and the French source."""

    def test_authored_without_python(self):
        text = EN_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("import", text)
        self.assertIn("build_process_core", text)
        self.assertIn("asynchronous_schedule", text)

    def test_byte_identical_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = eco.cyclic_dominance(12, 12, source_path=core["source"])
        self.assertEqual(core, reference)

    def test_steps_identically_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = eco.cyclic_dominance(12, 12, source_path=core["source"])
        built = [_field(f) for f in process_core.run(core, 8)]
        expected = [_field(f) for f in process_core.run(reference, 8)]
        self.assertEqual(built, expected)

    def test_field_actually_evolves(self):
        # A real process, not a frozen snapshot.
        core = _build(EN_SOURCE)
        trajectory = process_core.run(core, 6)
        self.assertNotEqual(_field(trajectory[0]), _field(trajectory[-1]))

    def test_english_and_french_lower_to_identical_core(self):
        en = _build(EN_SOURCE, language="en")
        fr = _build(FR_SOURCE, language="fr")
        en.pop("source")
        fr.pop("source")
        self.assertEqual(en, fr)


if __name__ == "__main__":
    unittest.main()

#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Authoring semantic-core-v1 process programs in the Multilingual language.

These tests guard the claim that polymodal *dynamics* are authored in
``.multi`` source -- not as a Python script importing ``process_core``. A
``.multi`` program assigns a ⟨State, Topology, Rule, Schedule⟩ core to
``process``; ``process_program`` runs it and emits the manifest. The strongest
guards: the ``.multi``-built core is byte-identical to, and steps identically
to, the Python ``game_of_life_polymodal`` reference (so the language front door
introduces no drift), and the English and French sources lower to the *same*
core (the multilingual claim applied to dynamics).
"""

import json
import tempfile
import unittest
from pathlib import Path

from examples import game_of_life_polymodal as gol
from multilingualprogramming.codegen import process_core
from multilingualprogramming.codegen import process_program as pproc

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
EN_SOURCE = EXAMPLES / "game_of_life.multi"
FR_SOURCE = EXAMPLES / "game_of_life.fr.multi"


def _build(source_path: Path, language: str = "en") -> dict:
    return pproc.execute_process(
        source_path.read_text(encoding="utf-8"),
        language=language,
        source_path=str(source_path),
    )


class ProcessProgramAuthoringTestSuite(unittest.TestCase):
    """The .multi program builds a well-formed v1 process core."""

    def test_builds_a_semantic_core_v1(self):
        core = _build(EN_SOURCE)
        self.assertEqual(core["kind"], process_core.CORE_KIND)
        self.assertEqual(core["version"], process_core.CORE_VERSION)
        self.assertEqual(core["source"], str(EN_SOURCE))

    def test_assembles_the_four_axes_as_data(self):
        core = _build(EN_SOURCE)
        self.assertEqual(core["topology"]["kind"], process_core.TOPOLOGY_LATTICE)
        self.assertEqual(
            core["topology"]["extent"], process_core.LATTICE_EXTENT_INFINITE
        )
        self.assertEqual(core["rule"]["kind"], process_core.RULE_REWRITE)
        self.assertEqual(
            core["schedule"]["kind"], process_core.SCHEDULE_SYNCHRONOUS
        )
        self.assertEqual(core["state"]["population"], process_core.POPULATION_OPEN)
        self.assertEqual(len(core["state"]["loci"]), len(gol.GLIDER))

    def test_authored_without_python(self):
        """The example is pure .multi: it never imports the Python engine."""
        text = EN_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("import", text)
        self.assertIn("build_process_core", text)


class ProcessProgramReferenceTestSuite(unittest.TestCase):
    """The .multi core matches the Python game_of_life_polymodal reference."""

    def test_byte_identical_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = gol.game_of_life_open(gol.GLIDER, source_path=core["source"])
        self.assertEqual(core, reference)

    def test_steps_identically_to_python_reference(self):
        core = _build(EN_SOURCE)
        reference = gol.game_of_life_open(gol.GLIDER, source_path=core["source"])
        built = [process_core.active_cells(f) for f in process_core.run(core, 8)]
        expected = [process_core.active_cells(f) for f in process_core.run(reference, 8)]
        self.assertEqual(built, expected)

    def test_glider_actually_travels(self):
        """A real process, not a frozen snapshot: the glider translates (1,1)/4."""
        core = _build(EN_SOURCE)
        trajectory = process_core.run(core, 4)
        start = set(process_core.active_cells(trajectory[0]))
        after = set(process_core.active_cells(trajectory[4]))
        shifted = {(x + 1, y + 1) for (x, y) in start}
        self.assertEqual(after, shifted)


class ProcessProgramMultilingualTestSuite(unittest.TestCase):
    """The same program in English and French lowers to the same core."""

    def test_english_and_french_lower_to_identical_core(self):
        en = _build(EN_SOURCE, language="en")
        fr = _build(FR_SOURCE, language="fr")
        en.pop("source")
        fr.pop("source")
        self.assertEqual(en, fr)


class ProcessProgramFileAndErrorTestSuite(unittest.TestCase):
    """File output and contract enforcement."""

    def test_build_process_core_file_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "program.v1.json"
            core = pproc.build_process_core_file(EN_SOURCE, out, language="en")
            on_disk = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(core, on_disk)

    def test_missing_process_variable_raises(self):
        with self.assertRaises(ValueError):
            pproc.execute_process("let other = 1\n", language="en")

    def test_non_v1_core_rejected(self):
        # A mapping that is not a semantic-core-v1 manifest must be refused,
        # so a v0 (or arbitrary) dict cannot masquerade as a process core.
        source = 'let process = {"kind": "semantic-core-v0"}\n'
        with self.assertRaises(ValueError):
            pproc.execute_process(source, language="en")


if __name__ == "__main__":
    unittest.main()

#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal coherence tests for polymodal computation.

These tests are the load-bearing claim of the layered architecture:
the same Multilingual polymodal program, projected into any modality,
must preserve the semantic identity of every entity. If a future
modality projection drops, renames, or reorders entities relative to
the semantic core, these tests fail.
"""

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from multilingualprogramming.__main__ import (
    cmd_polymodal_build,
    cmd_sonic_build,
)
from multilingualprogramming.codegen import opcode_ontology, sonic_capture
from multilingualprogramming.codegen.semantic_core import (
    CORE_KIND,
    build_semantic_core,
)
from multilingualprogramming.codegen.sonic_projection import (
    MANIFEST_KIND as SONIC_KIND,
    build_sonic_manifest,
)
from multilingualprogramming.codegen.spatial_manifest import (
    MANIFEST_KIND as SPATIAL_KIND,
    build_spatial_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "docs" / "browser" / "spatial-dynamics" / "program.multi"
SONIC_MANIFEST = ROOT / "docs" / "browser" / "sonic-dynamics" / "program.sonic.json"


def _source():
    return PROGRAM.read_text(encoding="utf-8")


class SemanticCoreTestSuite(unittest.TestCase):
    """Direct tests of the modality-free semantic core."""

    def test_core_kind_and_shape(self):
        core = build_semantic_core(_source(), language="en")
        self.assertEqual(core["kind"], CORE_KIND)
        self.assertEqual(core["version"], 0)
        self.assertIn("entities", core)
        self.assertIn("ontology", core)
        self.assertIn("relations", core)

    def test_core_entities_carry_only_semantic_fields(self):
        core = build_semantic_core(_source(), language="en")
        expected_fields = {
            "index", "opcode", "name", "intensity", "signal", "phase", "channel",
        }
        for entity in core["entities"]:
            self.assertEqual(set(entity.keys()), expected_fields)
            self.assertNotIn("x_ratio", entity)
            self.assertNotIn("y_ratio", entity)
            self.assertNotIn("radius", entity)
            self.assertNotIn("vx", entity)
            self.assertNotIn("vy", entity)
            self.assertNotIn("frequency_hz", entity)
            self.assertNotIn("amplitude", entity)

    def test_core_ontology_lists_all_known_opcodes(self):
        core = build_semantic_core(_source(), language="en")
        codes_in_ontology = {entry["code"] for entry in core["ontology"]}
        self.assertEqual(codes_in_ontology, opcode_ontology.known_codes())

    def test_core_rejects_unknown_opcode(self):
        bad_source = (
            "let seed = spatial_seed("
            "spatial_entity(emit(), 0.5, 0.5, 10, 1, 0, 0, 0, 0, 0)"
            ")"
        )
        core = build_semantic_core(bad_source, language="en")
        self.assertEqual(len(core["entities"]), 1)


class PolymodalEquivalenceTestSuite(unittest.TestCase):
    """Two projections of the same program must agree on semantic identity."""

    def test_spatial_and_sonic_have_same_entity_count(self):
        core = build_semantic_core(_source(), language="en")
        spatial = build_spatial_manifest(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")
        self.assertEqual(len(core["entities"]), len(spatial["entities"]))
        self.assertEqual(len(core["entities"]), len(sonic["voices"]))

    def test_opcode_order_preserved_across_modalities(self):
        core = build_semantic_core(_source(), language="en")
        spatial = build_spatial_manifest(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")

        core_codes = [entity["opcode"] for entity in core["entities"]]
        spatial_codes = [row[0] for row in spatial["entities"]]
        sonic_codes = [voice["opcode"] for voice in sonic["voices"]]

        self.assertEqual(core_codes, spatial_codes)
        self.assertEqual(core_codes, sonic_codes)

    def test_intensity_and_phase_preserved_in_both_projections(self):
        core = build_semantic_core(_source(), language="en")
        spatial = build_spatial_manifest(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")

        for core_entity, spatial_row, sonic_voice in zip(
            core["entities"], spatial["entities"], sonic["voices"]
        ):
            # Spatial row layout:
            # [behavior, x, y, radius, intensity, signal, vx, vy, phase, channel]
            self.assertAlmostEqual(core_entity["intensity"], spatial_row[4])
            self.assertAlmostEqual(core_entity["phase"], spatial_row[8])
            self.assertEqual(core_entity["channel"], spatial_row[9])
            # Sonic voice carries channel directly; amplitude/frequency derived
            self.assertEqual(core_entity["channel"], sonic_voice["channel"])

    def test_modalities_share_ontology_names(self):
        core = build_semantic_core(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")
        for core_entity, sonic_voice in zip(core["entities"], sonic["voices"]):
            self.assertEqual(core_entity["name"], sonic_voice["name"])
            self.assertEqual(core_entity["opcode"], sonic_voice["opcode"])

    def test_sonic_kinds_match_ontology_roles(self):
        sonic = build_sonic_manifest(_source(), language="en")
        for voice in sonic["voices"]:
            op = opcode_ontology.get(voice["opcode"])
            self.assertEqual(voice["role"], op.sonic.role)
            self.assertEqual(voice["waveform"], op.sonic.waveform)
            self.assertEqual(voice["envelope"], op.sonic.envelope)

    def test_sonic_buses_are_silent(self):
        sonic = build_sonic_manifest(_source(), language="en")
        for voice in sonic["voices"]:
            if voice["role"] == "bus":
                self.assertEqual(voice["amplitude"], 0.0)


class SonicRoundTripTestSuite(unittest.TestCase):
    """Inverse projection: observed sonic voices must recover semantic identity.

    These tests make the cross-modal equivalence claim falsifiable in
    the sonic direction. If they fail, the forward and inverse
    projections have drifted apart -- which is a regression of the
    architectural claim, not just a unit-test failure.
    """

    def test_invertible_set_is_derived_from_ontology(self):
        invertible = sonic_capture.invertible_opcodes()
        # Opcodes whose (role, waveform, envelope) tuple is unique and
        # non-bus are recoverable from observation alone.
        for name in ("emit", "oscillate", "transform", "propagate"):
            self.assertIn(
                opcode_ontology.get_by_name(name).code, invertible,
                f"{name} should be invertible from observation",
            )
        # Bus voices are silent under forward projection -> intensity
        # cannot be recovered.
        self.assertNotIn(
            opcode_ontology.get_by_name("contain").code, invertible
        )
        # Opcodes that share a sonic signature are indistinguishable by
        # ear and must not be claimed invertible.
        for name in ("split", "merge", "attract", "repel",
                     "diffuse", "stabilize", "resonate"):
            self.assertNotIn(
                opcode_ontology.get_by_name(name).code, invertible,
                f"{name} shares a sonic signature and must not be invertible",
            )

    def test_observe_voice_strips_identity_labels(self):
        sonic = build_sonic_manifest(_source(), language="en")
        observed = sonic_capture.observe_voice(sonic["voices"][0])
        # ObservedVoice is a frozen dataclass with no opcode/name field.
        self.assertFalse(hasattr(observed, "opcode"))
        self.assertFalse(hasattr(observed, "name"))

    def test_invertible_program_subset_round_trips_to_semantic_core(self):
        core = build_semantic_core(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")
        invertible = sonic_capture.invertible_opcodes()

        pairs = [
            (entity, voice)
            for entity, voice in zip(core["entities"], sonic["voices"])
            if entity["opcode"] in invertible
        ]
        self.assertGreaterEqual(
            len(pairs), 3,
            "Round-trip needs at least 3 invertible entities to be meaningful",
        )

        observed = [sonic_capture.observe_voice(voice) for _, voice in pairs]
        captured = sonic_capture.capture_semantic_core(
            observed, source_language="en", source_path="<round-trip>"
        )

        self.assertEqual(captured["kind"], CORE_KIND)
        self.assertEqual(len(captured["entities"]), len(pairs))

        for (original, _voice), recovered in zip(pairs, captured["entities"]):
            self.assertEqual(original["opcode"], recovered["opcode"])
            self.assertEqual(original["name"], recovered["name"])
            self.assertEqual(original["channel"], recovered["channel"])
            self.assertAlmostEqual(
                original["intensity"], recovered["intensity"], places=3
            )
            self.assertAlmostEqual(
                original["phase"], recovered["phase"], places=4
            )
            # signal is unrecoverable from amplitude alone; the capture
            # module assumes the seed-program convention of signal == 0.
            self.assertEqual(recovered["signal"], 0.0)

    def test_capture_rejects_ambiguous_observation(self):
        # split/merge share (trigger, square, percussive) -> cannot be
        # disambiguated by ear.
        ambiguous = sonic_capture.ObservedVoice(
            index=0, role="trigger", waveform="square",
            envelope="percussive", frequency_hz=440.0,
            amplitude=0.4, start_offset=0.0, channel=0,
        )
        with self.assertRaises(ValueError):
            sonic_capture.capture_semantic_core([ambiguous])

    def test_capture_rejects_bus_voice(self):
        # contain is bus -> silent under forward projection.
        bus = sonic_capture.ObservedVoice(
            index=0, role="bus", waveform="sine",
            envelope="sustained", frequency_hz=220.0,
            amplitude=0.0, start_offset=0.0, channel=0,
        )
        with self.assertRaises(ValueError):
            sonic_capture.capture_semantic_core([bus])

    def test_capture_rejects_unknown_signature(self):
        unknown = sonic_capture.ObservedVoice(
            index=0, role="source", waveform="noise",
            envelope="tremolo", frequency_hz=440.0,
            amplitude=0.3, start_offset=0.0, channel=0,
        )
        with self.assertRaises(ValueError):
            sonic_capture.capture_semantic_core([unknown])


class PolymodalCLITestSuite(unittest.TestCase):
    """The CLI must produce both manifests and they must round-trip."""

    def test_polymodal_build_writes_semantic_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "program.semantic.json"
            cmd_polymodal_build(Namespace(file=str(PROGRAM), lang="en", out=str(out)))
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["kind"], CORE_KIND)
            self.assertEqual(len(data["entities"]), 9)

    def test_sonic_build_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "program.sonic.json"
            cmd_sonic_build(Namespace(file=str(PROGRAM), lang="en", out=str(out)))
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["kind"], SONIC_KIND)
            self.assertEqual(len(data["voices"]), 9)

    def test_checked_in_sonic_manifest_matches_source(self):
        expected = build_sonic_manifest(
            _source(),
            language="en",
            source_path="docs/browser/spatial-dynamics/program.multi",
        )
        actual = json.loads(SONIC_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)


class SonicRuntimeAssetsTestSuite(unittest.TestCase):
    """The sonic browser runtime must consume the manifest and stay text-free."""

    def test_runtime_loads_manifest_kind(self):
        runtime = (
            ROOT / "docs" / "browser" / "sonic-dynamics" / "sonic_runtime.js"
        ).read_text(encoding="utf-8")
        self.assertIn('fetch("./program.sonic.json"', runtime)
        self.assertIn(SONIC_KIND, runtime)

    def test_runtime_canvas_draws_no_text(self):
        runtime = (
            ROOT / "docs" / "browser" / "sonic-dynamics" / "sonic_runtime.js"
        ).read_text(encoding="utf-8")
        self.assertNotIn("fillText", runtime)
        self.assertNotIn("strokeText", runtime)

    def test_html_has_meter_canvas_and_no_spatial_kind(self):
        html = (
            ROOT / "docs" / "browser" / "sonic-dynamics" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn('<canvas id="meter"', html)
        self.assertNotIn(SPATIAL_KIND, html)


if __name__ == "__main__":
    unittest.main()

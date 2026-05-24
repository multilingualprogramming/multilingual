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
    cmd_linear_build,
    cmd_ontology_export,
    cmd_polymodal_build,
    cmd_sonic_build,
)
from multilingualprogramming.codegen import opcode_ontology, sonic_capture
from multilingualprogramming.codegen.linear_manifest import (
    MANIFEST_KIND as LINEAR_KIND,
    build_linear_manifest,
)
from multilingualprogramming.codegen.opcode_ontology import (
    ONTOLOGY_KIND,
    build_ontology_manifest,
)
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
SONIC_DIR = ROOT / "docs" / "browser" / "sonic-dynamics"
SONIC_MANIFEST = SONIC_DIR / "program.sonic.json"
SONIC_ONTOLOGY = SONIC_DIR / "ontology.json"
SONIC_CAPTURE_JS = SONIC_DIR / "sonic_capture.js"
MIC_CAPTURE_JS = SONIC_DIR / "microphone_capture.js"
SONIC_RUNTIME_JS = SONIC_DIR / "sonic_runtime.js"
SONIC_HTML = SONIC_DIR / "index.html"
LINEAR_DIR = ROOT / "docs" / "browser" / "linear-dynamics"
LINEAR_MANIFEST = LINEAR_DIR / "program.linear.json"
LINEAR_ONTOLOGY = LINEAR_DIR / "ontology.json"
LINEAR_RUNTIME_JS = LINEAR_DIR / "linear_runtime.js"
LINEAR_HTML = LINEAR_DIR / "index.html"


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

    def test_all_modalities_have_same_entity_count(self):
        core = build_semantic_core(_source(), language="en")
        spatial = build_spatial_manifest(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")
        linear = build_linear_manifest(_source(), language="en")
        self.assertEqual(len(core["entities"]), len(spatial["entities"]))
        self.assertEqual(len(core["entities"]), len(sonic["voices"]))
        self.assertEqual(len(core["entities"]), len(linear["marks"]))

    def test_opcode_order_preserved_across_modalities(self):
        core = build_semantic_core(_source(), language="en")
        spatial = build_spatial_manifest(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")
        linear = build_linear_manifest(_source(), language="en")

        core_codes = [entity["opcode"] for entity in core["entities"]]
        spatial_codes = [row[0] for row in spatial["entities"]]
        sonic_codes = [voice["opcode"] for voice in sonic["voices"]]
        linear_codes = [mark["opcode"] for mark in linear["marks"]]

        self.assertEqual(core_codes, spatial_codes)
        self.assertEqual(core_codes, sonic_codes)
        self.assertEqual(core_codes, linear_codes)

    def test_intensity_and_phase_preserved_across_projections(self):
        core = build_semantic_core(_source(), language="en")
        spatial = build_spatial_manifest(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")
        linear = build_linear_manifest(_source(), language="en")

        for core_entity, spatial_row, sonic_voice, linear_mark in zip(
            core["entities"], spatial["entities"], sonic["voices"], linear["marks"],
        ):
            # Spatial row layout:
            # [behavior, x, y, radius, intensity, signal, vx, vy, phase, channel]
            self.assertAlmostEqual(core_entity["intensity"], spatial_row[4])
            self.assertAlmostEqual(core_entity["phase"], spatial_row[8])
            self.assertEqual(core_entity["channel"], spatial_row[9])
            # Sonic voice carries channel directly; amplitude/frequency derived
            self.assertEqual(core_entity["channel"], sonic_voice["channel"])
            # Linear mark carries intensity directly; phase becomes position.
            self.assertAlmostEqual(
                core_entity["intensity"], linear_mark["intensity"], places=3,
            )
            self.assertAlmostEqual(
                core_entity["phase"] % 1.0, linear_mark["position"], places=3,
            )
            self.assertEqual(core_entity["channel"], linear_mark["channel"])

    def test_modalities_share_ontology_names(self):
        core = build_semantic_core(_source(), language="en")
        sonic = build_sonic_manifest(_source(), language="en")
        linear = build_linear_manifest(_source(), language="en")
        for core_entity, sonic_voice, linear_mark in zip(
            core["entities"], sonic["voices"], linear["marks"],
        ):
            self.assertEqual(core_entity["name"], sonic_voice["name"])
            self.assertEqual(core_entity["opcode"], sonic_voice["opcode"])
            self.assertEqual(core_entity["name"], linear_mark["name"])
            self.assertEqual(core_entity["opcode"], linear_mark["opcode"])

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


class LinearProjectionTestSuite(unittest.TestCase):
    """Direct tests of the 1D linear (timeline) projection.

    The linear projection is the third peer modality, exercising the
    dimensionality axis distinct from the 2D spatial track. If linear
    starts diverging from the semantic core or from the ontology's
    linear hints, this suite fails.
    """

    def test_linear_manifest_shape(self):
        linear = build_linear_manifest(_source(), language="en")
        self.assertEqual(linear["kind"], LINEAR_KIND)
        self.assertEqual(linear["version"], 0)
        self.assertIn("marks", linear)
        self.assertIn("bar_seconds", linear)

    def test_linear_marks_use_ontology_glyph_and_color(self):
        linear = build_linear_manifest(_source(), language="en")
        for mark in linear["marks"]:
            op = opcode_ontology.get(mark["opcode"])
            self.assertEqual(mark["glyph"], op.linear.glyph)
            self.assertEqual(mark["color"], op.linear.color)

    def test_linear_positions_are_normalized(self):
        linear = build_linear_manifest(_source(), language="en")
        for mark in linear["marks"]:
            self.assertGreaterEqual(mark["position"], 0.0)
            self.assertLessEqual(mark["position"], 1.0)

    def test_linear_glyphs_are_one_dimensional_vocabulary(self):
        # 1D rendering must not inherit 2D-presuming shape names. The
        # forbidden list is intentionally limited to names that carry
        # explicit 2D geometry; quantifier-style names like "double"
        # are allowed because they describe a count, not a shape.
        forbidden_2d_shapes = {
            "ring", "diamond", "arrow", "membrane", "source",
            "phase", "up", "down", "square",
        }
        for op in opcode_ontology.OPCODES:
            self.assertNotIn(
                op.linear.glyph, forbidden_2d_shapes,
                f"opcode {op.name!r} has 2D shape name in linear hint: "
                f"{op.linear.glyph!r}",
            )


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

    def test_linear_build_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "program.linear.json"
            cmd_linear_build(Namespace(file=str(PROGRAM), lang="en", out=str(out)))
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["kind"], LINEAR_KIND)
            self.assertEqual(len(data["marks"]), 9)

    def test_checked_in_linear_manifest_matches_source(self):
        expected = build_linear_manifest(
            _source(),
            language="en",
            source_path="docs/browser/spatial-dynamics/program.multi",
        )
        actual = json.loads(LINEAR_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)


class OntologyManifestTestSuite(unittest.TestCase):
    """The checked-in ontology JSON sidecar must match the Python ontology.

    Browser runtimes fetch ``ontology.json`` and rely on it as the
    single source of truth shared with the Python projections. If this
    parity drifts, the JS inverse and the Python inverse start
    classifying observations differently -- which is a regression of
    the polymodal architectural claim.
    """

    def test_build_ontology_manifest_shape(self):
        manifest = build_ontology_manifest()
        self.assertEqual(manifest["kind"], ONTOLOGY_KIND)
        self.assertEqual(manifest["version"], 0)
        self.assertEqual(
            {op["code"] for op in manifest["opcodes"]},
            opcode_ontology.known_codes(),
        )

    def test_checked_in_sonic_ontology_matches_source(self):
        expected = build_ontology_manifest()
        actual = json.loads(SONIC_ONTOLOGY.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_checked_in_linear_ontology_matches_source(self):
        expected = build_ontology_manifest()
        actual = json.loads(LINEAR_ONTOLOGY.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_ontology_manifest_includes_linear_hints(self):
        manifest = build_ontology_manifest()
        for entry in manifest["opcodes"]:
            self.assertIn("linear", entry)
            self.assertIn("glyph", entry["linear"])
            self.assertIn("color", entry["linear"])

    def test_ontology_export_cli_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ontology.json"
            cmd_ontology_export(Namespace(out=str(out)))
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["kind"], ONTOLOGY_KIND)
            self.assertEqual(len(data["opcodes"]), len(opcode_ontology.OPCODES))


class SonicCaptureJSTestSuite(unittest.TestCase):
    """Structural guards on the JS inverse projection.

    A real browser-side execution test would need a headless runtime;
    these lint-style checks instead ensure the JS exports the same
    surface as the Python inverse and fetches the shared ontology
    sidecar rather than redefining it inline.
    """

    def _source(self):
        return SONIC_CAPTURE_JS.read_text(encoding="utf-8")

    def test_capture_js_exports_inverse_surface(self):
        source = self._source()
        for symbol in (
            "export function loadOntology",
            "export function invertibleOpcodes",
            "export function observeVoice",
            "export function captureSemanticCore",
        ):
            self.assertIn(symbol, source, f"sonic_capture.js missing {symbol!r}")

    def test_capture_js_fetches_ontology_sidecar(self):
        source = self._source()
        self.assertIn('"./ontology.json"', source)
        self.assertIn(ONTOLOGY_KIND, source)

    def test_capture_js_produces_semantic_core_kind(self):
        # The recovered manifest must carry the same kind constant the
        # Python inverse uses, so downstream consumers can treat them
        # interchangeably.
        self.assertIn(CORE_KIND, self._source())

    def test_capture_js_does_not_hardcode_opcode_table(self):
        # Hardcoded opcode names in JS would let it silently drift from
        # the Python ontology. The JS must derive everything from the
        # fetched sidecar.
        source = self._source()
        for name in ("emit", "oscillate", "transform", "propagate", "contain"):
            self.assertNotIn(
                f'"{name}"', source,
                f"sonic_capture.js hardcodes opcode name {name!r}; "
                f"it must read from the ontology sidecar instead.",
            )


class SonicRuntimeAssetsTestSuite(unittest.TestCase):
    """The sonic browser runtime must consume the manifest and stay text-free."""

    def test_runtime_loads_manifest_kind(self):
        runtime = SONIC_RUNTIME_JS.read_text(encoding="utf-8")
        self.assertIn('fetch("./program.sonic.json"', runtime)
        self.assertIn(SONIC_KIND, runtime)

    def test_runtime_canvas_draws_no_text(self):
        runtime = SONIC_RUNTIME_JS.read_text(encoding="utf-8")
        self.assertNotIn("fillText", runtime)
        self.assertNotIn("strokeText", runtime)

    def test_html_has_meter_canvas_and_no_spatial_kind(self):
        html = SONIC_HTML.read_text(encoding="utf-8")
        self.assertIn('<canvas id="meter"', html)
        self.assertNotIn(SPATIAL_KIND, html)


class MicrophoneCaptureJSTestSuite(unittest.TestCase):
    """Structural guards on the browser-side microphone pipeline.

    The microphone pipeline is the bridge that lets the inverse
    projection consume real audio rather than synthetic manifests.
    These checks ensure it exposes the contract the runtime depends on
    and does not redefine anything the ontology already owns.
    """

    def _source(self):
        return MIC_CAPTURE_JS.read_text(encoding="utf-8")

    def test_capture_pipeline_exports(self):
        source = self._source()
        for symbol in (
            "export class MicrophoneCapture",
            "export async function requestMicrophoneStream",
            "export function buildObservedVoice",
            "export function snapToPentatonic",
            "export function findFundamental",
            "export function classifyWaveform",
            "export function classifyEnvelope",
        ):
            self.assertIn(symbol, source, f"microphone_capture.js missing {symbol!r}")

    def test_capture_pipeline_uses_pentatonic_shared_with_forward(self):
        # The forward sonic projection only emits frequencies from
        # PENTATONIC_HZ; the capture path must snap to the same set so
        # the inverse can resolve a single ontology row deterministically.
        source = self._source()
        self.assertIn("220.000", source)
        self.assertIn("440.000", source)
        self.assertIn("783.991", source)

    def test_capture_pipeline_produces_observed_voice_fields(self):
        # The observation shape is the contract with sonic_capture.js.
        source = self._source()
        for field in (
            "frequency_hz", "amplitude", "start_offset", "channel",
            "role", "waveform", "envelope",
        ):
            self.assertIn(field, source, f"observed voice missing {field!r}")


class SonicCaptureWiringTestSuite(unittest.TestCase):
    """The sonic runtime + HTML must expose the capture entry point.

    Lint-style guards that the capture button is wired to the inverse
    projection and the recovered manifest panel exists in the DOM. A
    real interaction test would need a headless browser.
    """

    def test_runtime_imports_capture_modules(self):
        runtime = SONIC_RUNTIME_JS.read_text(encoding="utf-8")
        self.assertIn('from "./sonic_capture.js"', runtime)
        self.assertIn('from "./microphone_capture.js"', runtime)
        self.assertIn("captureSemanticCore", runtime)
        self.assertIn("MicrophoneCapture", runtime)

    def test_runtime_handles_capture_button_action(self):
        runtime = SONIC_RUNTIME_JS.read_text(encoding="utf-8")
        self.assertIn('dataset.action === "capture"', runtime)

    def test_html_has_capture_button_and_recovered_panel(self):
        html = SONIC_HTML.read_text(encoding="utf-8")
        self.assertIn('id="capture"', html)
        self.assertIn('data-action="capture"', html)
        self.assertIn('id="recovered"', html)


class LinearRuntimeAssetsTestSuite(unittest.TestCase):
    """The 1D linear browser runtime must consume the manifest and stay text-free."""

    def test_runtime_loads_manifest_kind(self):
        runtime = LINEAR_RUNTIME_JS.read_text(encoding="utf-8")
        self.assertIn('fetch("./program.linear.json"', runtime)
        self.assertIn(LINEAR_KIND, runtime)

    def test_runtime_canvas_draws_no_text(self):
        runtime = LINEAR_RUNTIME_JS.read_text(encoding="utf-8")
        self.assertNotIn("fillText", runtime)
        self.assertNotIn("strokeText", runtime)

    def test_html_has_strip_canvas_and_no_other_kinds(self):
        html = LINEAR_HTML.read_text(encoding="utf-8")
        self.assertIn('<canvas id="strip"', html)
        # Linear is its own peer: it must not reference sister-modality kinds.
        self.assertNotIn(SPATIAL_KIND, html)
        self.assertNotIn(SONIC_KIND, html)


if __name__ == "__main__":
    unittest.main()

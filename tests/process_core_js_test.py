#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Python <-> JS agreement for the semantic-core-v1 stepper.

The polymodal dynamics layer rests on one rule: the stepper that advances
(State, Topology, Rule, Schedule) lives once and is shared by every
runtime, so two surfaces cannot evolve the same program differently. The
browser uses a JS port of ``process_core.py``; this test makes the
"faithful port" claim falsifiable by *executing* that port under Node on
the same manifest and asserting its trajectory is identical to Python's,
frame for frame.

If Node is unavailable the behavioural test is skipped (the structural
checks still run), matching how the repo treats optional toolchains.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from examples.game_of_life_polymodal import GLIDER, game_of_life, game_of_life_open
from multilingualprogramming.codegen import process_core
from multilingualprogramming.codegen import process_program

ROOT = Path(__file__).resolve().parents[1]
PROCESS_DIR = ROOT / "docs" / "browser" / "process-dynamics"
CORE_JS = PROCESS_DIR / "process_core.js"
RUNTIME_JS = PROCESS_DIR / "process_runtime.js"
MANIFEST = PROCESS_DIR / "program.v1.json"
OPEN_MANIFEST = PROCESS_DIR / "program.open.v1.json"
LSYSTEM_MANIFEST = PROCESS_DIR / "program.lsystem.v1.json"
# The relative source paths baked into the checked-in manifests, so
# regeneration is reproducible regardless of where the repo is cloned.
MANIFEST_SOURCE = "docs/browser/process-dynamics/program.v1.json"
OPEN_MANIFEST_SOURCE = "docs/browser/process-dynamics/program.open.v1.json"
LSYSTEM_MANIFEST_SOURCE = "docs/browser/process-dynamics/program.lsystem.v1.json"
INDEX_HTML = PROCESS_DIR / "index.html"
LSYSTEM_HTML = PROCESS_DIR / "lsystem.html"
ECOSYSTEM_HTML = PROCESS_DIR / "ecosystem.html"
SEQUENCE_RUNTIME_JS = PROCESS_DIR / "sequence_runtime.js"
ECOSYSTEM_RUNTIME_JS = PROCESS_DIR / "ecosystem_runtime.js"
PACKAGE_JSON = PROCESS_DIR / "package.json"
LSYSTEM_SOURCE = ROOT / "examples" / "lindenmayer.multi"
ECOSYSTEM_MANIFEST = PROCESS_DIR / "program.ecosystem.v1.json"
ECOSYSTEM_MANIFEST_SOURCE = "docs/browser/process-dynamics/program.ecosystem.v1.json"
ECOSYSTEM_SOURCE = ROOT / "examples" / "ecosystem.multi"
GRAPH_HTML = PROCESS_DIR / "graph.html"
GRAPH_RUNTIME_JS = PROCESS_DIR / "graph_runtime.js"
GRAPH_MANIFEST = PROCESS_DIR / "program.graph.v1.json"
GRAPH_MANIFEST_SOURCE = "docs/browser/process-dynamics/program.graph.v1.json"
GRAPH_SOURCE = ROOT / "examples" / "network_epidemic.multi"
DIFFUSION_HTML = PROCESS_DIR / "diffusion.html"
DIFFUSION_RUNTIME_JS = PROCESS_DIR / "diffusion_runtime.js"
DIFFUSION_MANIFEST = PROCESS_DIR / "program.diffusion.v1.json"
DIFFUSION_MANIFEST_SOURCE = "docs/browser/process-dynamics/program.diffusion.v1.json"
DIFFUSION_SOURCE = ROOT / "examples" / "diffusion.multi"

NODE = shutil.which("node")
STEPS = 16

_DRIVER = """\
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [, , corePath, manifestPath, steps] = process.argv;
const { run, activeCells } = await import(pathToFileURL(corePath).href);
const core = JSON.parse(readFileSync(manifestPath, 'utf-8'));
const trajectory = run(core, Number(steps));
process.stdout.write(JSON.stringify(trajectory.map((f) => activeCells(f))));
"""

# The generative path reads the produced word out of each frame instead of the
# active cells -- otherwise identical (the one shared `run` drives both).
_SEQUENCE_DRIVER = """\
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [, , corePath, manifestPath, steps] = process.argv;
const { run, sequenceSymbols } = await import(pathToFileURL(corePath).href);
const core = JSON.parse(readFileSync(manifestPath, 'utf-8'));
const trajectory = run(core, Number(steps));
process.stdout.write(JSON.stringify(trajectory.map((f) => sequenceSymbols(f).join(''))));
"""


# The asynchronous / multi-state-field path reads each locus's value out of
# every frame (via the shared fieldCells) instead of the active-cell mask --
# otherwise identical (the one shared `run` drives it too).
_FIELD_DRIVER = """\
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [, , corePath, manifestPath, steps] = process.argv;
const { run, fieldCells } = await import(pathToFileURL(corePath).href);
const core = JSON.parse(readFileSync(manifestPath, 'utf-8'));
const trajectory = run(core, Number(steps));
process.stdout.write(JSON.stringify(trajectory.map((f) => fieldCells(f, 'species'))));
"""


# The continuous path reads each cell's continuous value (field `u`) out of
# every frame via the shared fieldCells -- the same driver shape as the field
# path, on a float-valued field, so it doubles as a cross-runtime float check.
_DIFFUSION_DRIVER = """\
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [, , corePath, manifestPath, steps] = process.argv;
const { run, fieldCells } = await import(pathToFileURL(corePath).href);
const core = JSON.parse(readFileSync(manifestPath, 'utf-8'));
const trajectory = run(core, Number(steps));
process.stdout.write(JSON.stringify(trajectory.map((f) => fieldCells(f, 'u'))));
"""


# The graph path reads each node's value out of every frame (via the shared
# nodeCells) -- otherwise identical (the one shared `run` drives it too).
_NODE_DRIVER = """\
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [, , corePath, manifestPath, steps] = process.argv;
const { run, nodeCells } = await import(pathToFileURL(corePath).href);
const core = JSON.parse(readFileSync(manifestPath, 'utf-8'));
const trajectory = run(core, Number(steps));
process.stdout.write(JSON.stringify(trajectory.map((f) => nodeCells(f, 'state'))));
"""


def _run_driver(driver_src: str, manifest_path: Path, steps: int):
    with tempfile.TemporaryDirectory() as tmp:
        driver = Path(tmp) / "driver.mjs"
        driver.write_text(driver_src, encoding="utf-8")
        out = subprocess.run(
            [NODE, str(driver), str(CORE_JS), str(manifest_path), str(steps)],
            capture_output=True,
            text=True,
            check=True,
        )
    return json.loads(out.stdout)


def _js_trajectory(manifest_path: Path, steps: int) -> list[list[list[int]]]:
    return _run_driver(_DRIVER, manifest_path, steps)


def _js_words(manifest_path: Path, steps: int) -> list[str]:
    return _run_driver(_SEQUENCE_DRIVER, manifest_path, steps)


def _js_field(manifest_path: Path, steps: int):
    return _run_driver(_FIELD_DRIVER, manifest_path, steps)


def _js_nodes(manifest_path: Path, steps: int):
    return _run_driver(_NODE_DRIVER, manifest_path, steps)


def _js_diffusion(manifest_path: Path, steps: int):
    return _run_driver(_DIFFUSION_DRIVER, manifest_path, steps)


def _py_trajectory(core: dict, steps: int) -> list[list[list[int]]]:
    return [
        [list(cell) for cell in process_core.active_cells(frame)]
        for frame in process_core.run(core, steps)
    ]


class ManifestStabilityTestSuite(unittest.TestCase):
    """The checked-in manifest must match what the Python example emits."""

    def test_checked_in_manifest_matches_generator(self):
        regenerated = game_of_life(
            12, 12, GLIDER, wrap=True, source_path=MANIFEST_SOURCE
        )
        on_disk = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, regenerated)

    def test_manifest_is_v1(self):
        on_disk = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["kind"], "semantic-core-v1")
        self.assertEqual(on_disk["rule"]["kind"], "rewrite")

    def test_checked_in_open_manifest_matches_generator(self):
        regenerated = game_of_life_open(GLIDER, source_path=OPEN_MANIFEST_SOURCE)
        on_disk = json.loads(OPEN_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, regenerated)

    def test_open_manifest_is_open_and_unbounded(self):
        on_disk = json.loads(OPEN_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["state"]["population"], "open")
        self.assertEqual(on_disk["topology"]["extent"], "infinite")
        # Same rule data as the bounded program -- only State/Topology differ.
        bounded = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["rule"], bounded["rule"])

    def test_checked_in_lsystem_manifest_matches_multi_build(self):
        # The browser L-system manifest is the .multi program built to JSON;
        # it must not drift from examples/lindenmayer.multi.
        regenerated = process_program.execute_process(
            LSYSTEM_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=LSYSTEM_MANIFEST_SOURCE,
        )
        on_disk = json.loads(LSYSTEM_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, regenerated)

    def test_lsystem_manifest_is_sequence_generative(self):
        on_disk = json.loads(LSYSTEM_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["kind"], "semantic-core-v1")
        self.assertEqual(on_disk["topology"]["kind"], "sequence")
        self.assertEqual(on_disk["schedule"]["kind"], "generative")

    def test_checked_in_ecosystem_manifest_matches_multi_build(self):
        # The browser ecosystem manifest is the .multi program built to JSON;
        # it must not drift from examples/ecosystem.multi.
        regenerated = process_program.execute_process(
            ECOSYSTEM_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=ECOSYSTEM_MANIFEST_SOURCE,
        )
        on_disk = json.loads(ECOSYSTEM_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, regenerated)

    def test_ecosystem_manifest_is_lattice_asynchronous(self):
        on_disk = json.loads(ECOSYSTEM_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["kind"], "semantic-core-v1")
        self.assertEqual(on_disk["topology"]["kind"], "lattice")
        self.assertEqual(on_disk["schedule"]["kind"], "asynchronous")
        # Heterogeneous state: loci carry a multi-valued species, not a boolean.
        self.assertIn("species", on_disk["state"]["loci"][0])

    def test_checked_in_graph_manifest_matches_multi_build(self):
        # The browser graph manifest is the .multi program built to JSON; it
        # must not drift from examples/network_epidemic.multi.
        regenerated = process_program.execute_process(
            GRAPH_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=GRAPH_MANIFEST_SOURCE,
        )
        on_disk = json.loads(GRAPH_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, regenerated)

    def test_graph_manifest_is_graph_synchronous(self):
        on_disk = json.loads(GRAPH_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["kind"], "semantic-core-v1")
        self.assertEqual(on_disk["topology"]["kind"], "graph")
        self.assertEqual(on_disk["schedule"]["kind"], "synchronous")
        # Adjacency is the edge set; nodes carry an id (and a locus view hint).
        self.assertIn("edges", on_disk["topology"])
        self.assertIn("node", on_disk["state"]["loci"][0])

    def test_checked_in_diffusion_manifest_matches_multi_build(self):
        # The browser diffusion manifest is the .multi program built to JSON; it
        # must not drift from examples/diffusion.multi.
        regenerated = process_program.execute_process(
            DIFFUSION_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=DIFFUSION_MANIFEST_SOURCE,
        )
        on_disk = json.loads(DIFFUSION_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, regenerated)

    def test_diffusion_manifest_is_lattice_continuous(self):
        on_disk = json.loads(DIFFUSION_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["kind"], "semantic-core-v1")
        self.assertEqual(on_disk["topology"]["kind"], "lattice")
        self.assertEqual(on_disk["schedule"]["kind"], "continuous-dt")
        # A continuous rate rule (not a discrete rewrite), and a real dt.
        self.assertEqual(on_disk["rule"]["kind"], "rate")
        self.assertIn("dt", on_disk["schedule"])
        # Continuous per-cell value: loci carry a float field, not a boolean.
        self.assertIn("u", on_disk["state"]["loci"][0])


class JsStepperSourceTestSuite(unittest.TestCase):
    """Structural guards mirroring the repo's other JS peers."""

    def test_package_scopes_es_module(self):
        self.assertEqual(json.loads(PACKAGE_JSON.read_text())["type"], "module")

    def test_core_js_exports_the_stepper(self):
        source = CORE_JS.read_text(encoding="utf-8")
        for symbol in ("export function step", "export function run",
                       "export function neighbors", "export function activeCells"):
            self.assertIn(symbol, source, f"process_core.js missing {symbol!r}")

    def test_core_js_ports_the_generative_axis(self):
        # The generative (L-system) axis must exist in the browser engine too,
        # so the sequence runtime shares the one stepper rather than rolling
        # its own string rewriting.
        source = CORE_JS.read_text(encoding="utf-8")
        for symbol in ("SCHEDULE_GENERATIVE", "TOPOLOGY_SEQUENCE",
                       "export function sequenceSymbols"):
            self.assertIn(symbol, source, f"process_core.js missing {symbol!r}")

    def test_core_js_ports_the_asynchronous_axis(self):
        # The asynchronous (sequential-update) schedule and the multi-state
        # field readout must exist in the browser engine too, so the ecosystem
        # runtime shares the one stepper rather than rolling its own sweep.
        source = CORE_JS.read_text(encoding="utf-8")
        for symbol in ("SCHEDULE_ASYNCHRONOUS", "export function fieldCells"):
            self.assertIn(symbol, source, f"process_core.js missing {symbol!r}")

    def test_core_js_ports_the_graph_axis(self):
        # The graph topology and its node readout must exist in the browser
        # engine too, plus the shared tier classifier the status line uses, so
        # the graph runtime shares the one stepper rather than rolling its own.
        source = CORE_JS.read_text(encoding="utf-8")
        for symbol in ("TOPOLOGY_GRAPH", "export function nodeCells",
                       "export function tierOf", "export const TIER_NAMES"):
            self.assertIn(symbol, source, f"process_core.js missing {symbol!r}")

    def test_core_js_ports_the_continuous_axis(self):
        # The continuous-dt schedule and rate rule kind must exist in the
        # browser engine too, so the diffusion runtime shares the one stepper
        # rather than rolling its own integrator.
        source = CORE_JS.read_text(encoding="utf-8")
        for symbol in ("SCHEDULE_CONTINUOUS", "RULE_RATE"):
            self.assertIn(symbol, source, f"process_core.js missing {symbol!r}")

    def test_core_js_defines_no_specific_system(self):
        # The JS engine is the language too: it must not implement any
        # automaton. Comments may name systems to explain the principle, but
        # there must be no system-specific identifier or birth/survival
        # logic baked into the engine.
        source = CORE_JS.read_text(encoding="utf-8").lower()
        for token in ("gameoflife", "conway", "function life", "const life",
                      "birth", "survival"):
            self.assertNotIn(token, source,
                             f"process_core.js leaks system-specific token {token!r}")

    def test_runtime_uses_shared_stepper_and_fetches_manifest(self):
        source = RUNTIME_JS.read_text(encoding="utf-8")
        # The runtime must import motion from the shared core, not roll its own.
        self.assertIn('from "./process_core.js"', source)
        self.assertIn("./program.v1.json", source)
        self.assertIn("tierOf", source)  # the tier shown in the status line
        self.assertNotIn("function step", source)  # no private stepper

    def test_runtime_is_viewport_aware(self):
        source = RUNTIME_JS.read_text(encoding="utf-8")
        # The runtime must derive a finite window so it can render an
        # unbounded (infinite-topology) program, not assume topology extent.
        self.assertIn("LATTICE_EXTENT_INFINITE", source)
        self.assertIn("resolveViewport", source)
        self.assertIn("boundingBox", source)

    def test_index_loads_runtime_as_module(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn("./process_runtime.js", html)
        # The page can switch to the unbounded program.
        self.assertIn("program.open.v1.json", html)

    def test_sequence_runtime_uses_shared_stepper(self):
        source = SEQUENCE_RUNTIME_JS.read_text(encoding="utf-8")
        # The generative runtime must import motion from the one shared core --
        # the same engine as the lattice runtime, not its own string rewriter.
        self.assertIn('from "./process_core.js"', source)
        self.assertIn("sequenceSymbols", source)
        self.assertIn("./program.lsystem.v1.json", source)
        self.assertIn("tierOf", source)  # the tier shown in the status line
        self.assertNotIn("function step", source)  # no private stepper

    def test_lsystem_page_loads_sequence_runtime_as_module(self):
        html = LSYSTEM_HTML.read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn("./sequence_runtime.js", html)

    def test_ecosystem_runtime_uses_shared_stepper(self):
        source = ECOSYSTEM_RUNTIME_JS.read_text(encoding="utf-8")
        # The field runtime must import motion from the one shared core -- the
        # same engine as the lattice and sequence runtimes, not its own sweep.
        self.assertIn('from "./process_core.js"', source)
        self.assertIn("fieldCells", source)
        self.assertIn("SCHEDULE_ASYNCHRONOUS", source)
        self.assertIn("./program.ecosystem.v1.json", source)
        self.assertIn("tierOf", source)  # the tier shown in the status line
        self.assertNotIn("function step", source)  # no private stepper

    def test_ecosystem_page_loads_ecosystem_runtime_as_module(self):
        html = ECOSYSTEM_HTML.read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn("./ecosystem_runtime.js", html)

    def test_graph_runtime_uses_shared_stepper_and_classifier(self):
        source = GRAPH_RUNTIME_JS.read_text(encoding="utf-8")
        # The graph runtime must import motion and the tier classifier from the
        # one shared core -- the same engine as the other runtimes, not its own.
        self.assertIn('from "./process_core.js"', source)
        self.assertIn("nodeCells", source)
        self.assertIn("tierOf", source)  # the tier shown in the status line
        self.assertIn("./program.graph.v1.json", source)
        self.assertNotIn("function step", source)  # no private stepper

    def test_graph_page_loads_graph_runtime_as_module(self):
        html = GRAPH_HTML.read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn("./graph_runtime.js", html)

    def test_diffusion_runtime_uses_shared_stepper(self):
        source = DIFFUSION_RUNTIME_JS.read_text(encoding="utf-8")
        # The continuous runtime must import motion from the one shared core --
        # the same engine as the discrete runtimes, not its own integrator.
        self.assertIn('from "./process_core.js"', source)
        self.assertIn("fieldCells", source)
        self.assertIn("SCHEDULE_CONTINUOUS", source)
        self.assertIn("./program.diffusion.v1.json", source)
        self.assertIn("tierOf", source)  # the tier shown in the status line
        self.assertNotIn("function step", source)  # no private stepper

    def test_diffusion_page_loads_diffusion_runtime_as_module(self):
        html = DIFFUSION_HTML.read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn("./diffusion_runtime.js", html)


@unittest.skipUnless(NODE, "node is not installed")
class JsPythonAgreementTestSuite(unittest.TestCase):
    """Executing the JS stepper must reproduce Python's trajectory exactly."""

    def test_trajectories_are_identical_frame_for_frame(self):
        core = json.loads(MANIFEST.read_text(encoding="utf-8"))
        js = _js_trajectory(MANIFEST, STEPS)
        py = _py_trajectory(core, STEPS)
        self.assertEqual(len(js), STEPS + 1)
        self.assertEqual(js, py)

    def test_bounded_lattice_also_agrees(self):
        # A different topology (no wrap) and a still life exercise other
        # neighbourhood branches; write a temp manifest and compare.
        core = game_of_life(6, 6, [(1, 1), (2, 1), (1, 2), (2, 2)], wrap=False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bounded.v1.json"
            path.write_text(json.dumps(core), encoding="utf-8")
            js = _js_trajectory(path, 5)
        py = _py_trajectory(core, 5)
        self.assertEqual(js, py)

    def test_open_population_trajectory_agrees(self):
        # The Tier-3 path: birth/death on an unbounded lattice, including
        # negative coordinates, must step identically in JS and Python.
        core = game_of_life_open(GLIDER)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "open.v1.json"
            path.write_text(json.dumps(core), encoding="utf-8")
            js = _js_trajectory(path, 12)
        py = _py_trajectory(core, 12)
        self.assertEqual(js, py)
        # And it genuinely travelled past the initial bound.
        self.assertTrue(max(x for x, _ in js[-1]) >= 3)

    def test_generative_lsystem_trajectory_agrees(self):
        # The generative axis: a string-rewriting (L-system) core authored in
        # .multi must grow identically in JS and Python, word for word -- the
        # textual front door and the browser engine add no drift to each other.
        core = process_program.execute_process(
            LSYSTEM_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=str(LSYSTEM_SOURCE),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lsystem.v1.json"
            path.write_text(json.dumps(core), encoding="utf-8")
            js = _js_words(path, 5)
        py = [
            "".join(process_core.sequence_symbols(frame))
            for frame in process_core.run(core, 5)
        ]
        self.assertEqual(js, py)
        # Canonical algae generations, so the agreement is on real growth.
        self.assertEqual(js, ["A", "AB", "ABA", "ABAAB", "ABAABABA", "ABAABABAABAAB"])

    def test_asynchronous_field_trajectory_agrees(self):
        # The asynchronous axis: a heterogeneous-state field (cyclic-dominance
        # ecosystem) authored in .multi must step identically in JS and Python,
        # value for value, across the whole trajectory. Sequential in-place
        # update is order-sensitive, so this is a sharp anti-drift check: the
        # two runtimes must walk the loci in exactly the same order.
        core = process_program.execute_process(
            ECOSYSTEM_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=str(ECOSYSTEM_SOURCE),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ecosystem.v1.json"
            path.write_text(json.dumps(core), encoding="utf-8")
            js = _js_field(path, STEPS)
        py = [
            [list(cell) for cell in process_core.field_cells(frame, "species")]
            for frame in process_core.run(core, STEPS)
        ]
        self.assertEqual(len(js), STEPS + 1)
        self.assertEqual(js, py)
        # And the field genuinely evolved (async is not a no-op here).
        self.assertNotEqual(js[0], js[-1])

    def test_graph_node_trajectory_agrees(self):
        # The graph axis: a network contagion authored in .multi must step
        # identically in JS and Python, node-value for node-value, across the
        # whole trajectory. Adjacency is the edge set, so this also proves the
        # two runtimes build the same adjacency from the same edges.
        core = process_program.execute_process(
            GRAPH_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=str(GRAPH_SOURCE),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.v1.json"
            path.write_text(json.dumps(core), encoding="utf-8")
            js = _js_nodes(path, STEPS)
        py = [
            [list(cell) for cell in process_core.node_cells(frame, "state")]
            for frame in process_core.run(core, STEPS)
        ]
        self.assertEqual(len(js), STEPS + 1)
        self.assertEqual(js, py)
        # And the outbreak genuinely spread (not a no-op).
        self.assertNotEqual(js[0], js[-1])

    def test_continuous_diffusion_trajectory_agrees(self):
        # The continuous axis: a heat-diffusion field authored in .multi must
        # integrate identically in JS and Python, *float for float*, across the
        # whole trajectory. This is the sharpest cross-runtime check yet --
        # floating-point Euler steps must agree bit-for-bit, which only holds
        # because both ports sum neighbours in the same order with a naive
        # left-fold (CPython's compensated `sum` would diverge by ~1 ULP).
        core = process_program.execute_process(
            DIFFUSION_SOURCE.read_text(encoding="utf-8"),
            language="en",
            source_path=str(DIFFUSION_SOURCE),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diffusion.v1.json"
            path.write_text(json.dumps(core), encoding="utf-8")
            js = _js_diffusion(path, STEPS)
        py = [
            [list(cell) for cell in process_core.field_cells(frame, "u")]
            for frame in process_core.run(core, STEPS)
        ]
        self.assertEqual(len(js), STEPS + 1)
        self.assertEqual(js, py)
        # And the field genuinely diffused (the continuous step is not a no-op).
        self.assertNotEqual(js[0], js[-1])


if __name__ == "__main__":
    unittest.main()

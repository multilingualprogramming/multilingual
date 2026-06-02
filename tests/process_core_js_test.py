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

from examples.game_of_life_polymodal import GLIDER, game_of_life
from multilingualprogramming.codegen import process_core

ROOT = Path(__file__).resolve().parents[1]
PROCESS_DIR = ROOT / "docs" / "browser" / "process-dynamics"
CORE_JS = PROCESS_DIR / "process_core.js"
RUNTIME_JS = PROCESS_DIR / "process_runtime.js"
MANIFEST = PROCESS_DIR / "program.v1.json"
# The relative source path baked into the checked-in manifest, so
# regeneration is reproducible regardless of where the repo is cloned.
MANIFEST_SOURCE = "docs/browser/process-dynamics/program.v1.json"
INDEX_HTML = PROCESS_DIR / "index.html"
PACKAGE_JSON = PROCESS_DIR / "package.json"

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


def _js_trajectory(manifest_path: Path, steps: int) -> list[list[list[int]]]:
    with tempfile.TemporaryDirectory() as tmp:
        driver = Path(tmp) / "driver.mjs"
        driver.write_text(_DRIVER, encoding="utf-8")
        out = subprocess.run(
            [NODE, str(driver), str(CORE_JS), str(manifest_path), str(steps)],
            capture_output=True,
            text=True,
            check=True,
        )
    return json.loads(out.stdout)


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


class JsStepperSourceTestSuite(unittest.TestCase):
    """Structural guards mirroring the repo's other JS peers."""

    def test_package_scopes_es_module(self):
        self.assertEqual(json.loads(PACKAGE_JSON.read_text())["type"], "module")

    def test_core_js_exports_the_stepper(self):
        source = CORE_JS.read_text(encoding="utf-8")
        for symbol in ("export function step", "export function run",
                       "export function neighbors", "export function activeCells"):
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
        self.assertNotIn("function step", source)  # no private stepper

    def test_index_loads_runtime_as_module(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('type="module"', html)
        self.assertIn("./process_runtime.js", html)


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


if __name__ == "__main__":
    unittest.main()

#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for the Multilingual-authored spatial browser prototype."""

import json
from argparse import Namespace
from pathlib import Path
import tempfile
import unittest

from multilingualprogramming.__main__ import cmd_spatial_build
from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.codegen.runtime_builtins import RuntimeBuiltins
from multilingualprogramming.codegen.spatial_manifest import (
    MANIFEST_KIND,
    build_spatial_manifest,
)
from multilingualprogramming.lexer.lexer import Lexer
from multilingualprogramming.parser.ast_nodes import VariableDeclaration
from multilingualprogramming.parser.parser import Parser


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "browser" / "spatial-dynamics"
PROGRAM = DEMO / "program.multi"
MANIFEST = DEMO / "program.spatial.json"


class SpatialPipelineTestSuite(unittest.TestCase):
    """Keep the prototype centered on Multilingual source."""

    def test_multilingual_source_parses_and_executes(self):
        source = PROGRAM.read_text(encoding="utf-8")
        parser = Parser(Lexer(source, language="en").tokenize(), source_language="en")
        program = parser.parse()
        self.assertEqual(len(program.body), 2)
        self.assertIsInstance(program.body[0], VariableDeclaration)

        result = ProgramExecutor(language="en", check_semantics=False).execute(source)
        self.assertTrue(result.success, result.errors)
        self.assertEqual(result.output.strip(), "9")

    def test_multilingual_source_uses_spatial_primitives(self):
        source = PROGRAM.read_text(encoding="utf-8")
        self.assertIn("spatial_seed(", source)
        self.assertIn("spatial_entity(emit()", source)
        self.assertNotIn("def spatial_entity", source)
        self.assertNotIn("let EMIT", source)

    def test_runtime_namespace_has_spatial_primitives(self):
        ns = RuntimeBuiltins("en").namespace()
        entity = ns["spatial_entity"](ns["emit"](), 0.5, 0.5, 10)
        self.assertEqual(entity[0], 1)
        self.assertEqual(ns["spatial_seed"](entity), [entity])

    def test_checked_in_manifest_matches_source(self):
        expected = build_spatial_manifest(
            PROGRAM.read_text(encoding="utf-8"),
            language="en",
            source_path="docs/browser/spatial-dynamics/program.multi",
        )
        actual = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_cli_spatial_build_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "program.spatial.json"
            cmd_spatial_build(Namespace(file=str(PROGRAM), lang="en", out=str(out)))
            manifest = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], MANIFEST_KIND)
            self.assertEqual(len(manifest["entities"]), 9)

    def test_browser_runtime_loads_manifest_and_draws_no_text(self):
        runtime = (DEMO / "spatial_runtime.js").read_text(encoding="utf-8")
        html = (DEMO / "index.html").read_text(encoding="utf-8")
        self.assertIn('fetch("./program.spatial.json"', runtime)
        self.assertNotIn("parseSpatialProgram", runtime)
        self.assertNotIn("fillText", runtime)
        self.assertNotIn("strokeText", runtime)
        self.assertIn('<canvas id="world"', html)


if __name__ == "__main__":
    unittest.main()

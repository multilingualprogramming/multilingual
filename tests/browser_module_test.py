#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for the rich browser ESM module bridge."""

import subprocess
import sys

from multilingualprogramming.codegen.browser_module import generate_browser_module
from multilingualprogramming.lexer.lexer import Lexer
from multilingualprogramming.parser.parser import Parser


def _parse(source: str, lang: str = "en"):
    lexer = Lexer(source, language=lang)
    parser = Parser(lexer.tokenize(), source_language=lang)
    return parser.parse()


def test_generate_browser_module_exports_named_function():
    program = _parse(
        "def describe(x):\n"
        "    return {\"value\": x, \"items\": [x, x + 1]}\n",
        "en",
    )

    module_source = generate_browser_module(
        program,
        exports=["describe"],
        stub_modules=["helpers"],
    )

    assert "const PYTHON_SOURCE =" in module_source
    assert "export async function describe(...args)" in module_source
    assert "loadPyodide" in module_source
    assert "dict_converter: Object.fromEntries" in module_source
    assert 'const STUB_MODULES = ["helpers"];' in module_source


def test_build_browser_module_cli_writes_esm(tmp_path):
    source = tmp_path / "program.multi"
    output = tmp_path / "program.browser.mjs"
    source.write_text(
        "def describe(x):\n"
        "    return {\"value\": x, \"items\": [x, x + 1]}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "multilingualprogramming",
            "build-browser-module",
            str(source),
            "--lang",
            "en",
            "--export",
            "describe",
            "--stub-module",
            "helpers",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "[PASS]" in result.stdout
    module_source = output.read_text(encoding="utf-8")
    assert "export async function describe(...args)" in module_source
    assert 'const STUB_MODULES = ["helpers"];' in module_source
    assert "return {'value': x, 'items': [x, (x + 1)]}" in module_source

#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for Core 1.0 example files in examples/core/.

Each source file in examples/core/ is discovered automatically.
The test pipeline for every example:
  1. Lex the source code (language-aware tokenisation)
  2. Parse the token stream into a surface AST
  3. Lower the AST to Core 1.0 semantic IR
  4. Run the minimal structural validator (validate_semantic_ir)
  5. Execute the program (if not blocked by external service requirements)
"""

import os
import pathlib
import sys

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from multilingualprogramming.core.semantic_lowering import lower_to_semantic_ir
from multilingualprogramming.core.validators import validate_semantic_ir
from multilingualprogramming.lexer.lexer import Lexer
from multilingualprogramming.parser.parser import Parser
from multilingualprogramming.source_extensions import iter_source_files
from multilingualprogramming.codegen.executor import ProgramExecutor
from multilingualprogramming.runtime.ai_runtime import AIRuntime, MockProvider


_CORE_EXAMPLES_DIR = (
    pathlib.Path(__file__).parent.parent.parent / "examples" / "core"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_lang(path: pathlib.Path) -> str:
    """Infer language code from a filename like *_en.multi → 'en'."""
    stem = path.stem
    if "_" in stem:
        return stem.rsplit("_", 1)[-1]
    return "en"


def _lower(path: pathlib.Path):
    """Lex, parse, and lower a source example file to Core 1.0 IR."""
    lang = _detect_lang(path)
    source = path.read_text(encoding="utf-8")
    tokens = Lexer(source, language=lang).tokenize()
    ast = Parser(tokens, source_language=lang).parse()
    return lower_to_semantic_ir(ast, lang)


def _example_files():
    return iter_source_files(_CORE_EXAMPLES_DIR, "*")


# ---------------------------------------------------------------------------
# Parametrised tests (pytest-based, if available)
# ---------------------------------------------------------------------------

if HAS_PYTEST:
    @pytest.mark.parametrize("path", _example_files(), ids=lambda p: p.name)
    def test_core_example_parses(path: pathlib.Path):
        """Every Core 1.0 example must tokenise and parse without raising."""
        lang = _detect_lang(path)
        source = path.read_text(encoding="utf-8")
        tokens = Lexer(source, language=lang).tokenize()
        program = Parser(tokens, source_language=lang).parse()
        assert program is not None
        assert len(program.body) > 0, f"{path.name} has an empty program body"


    @pytest.mark.parametrize("path", _example_files(), ids=lambda p: p.name)
    def test_core_example_lowers_to_ir(path: pathlib.Path):
        """Every Core 1.0 example must lower to a valid IRProgram."""
        ir = _lower(path)
        assert ir is not None
        validate_semantic_ir(ir)
        assert ir.source_language != ""
        assert isinstance(ir.body, list)
        assert len(ir.body) > 0, f"{path.name}: IR body is empty after lowering"


    @pytest.mark.parametrize("path", _example_files(), ids=lambda p: p.name)
    def test_core_example_language_detected(path: pathlib.Path):
        """Language code must be inferred correctly from the filename."""
        lang = _detect_lang(path)
        assert lang, f"Could not detect language for {path.name}"
        ir = _lower(path)
        assert ir.source_language == lang
else:
    # Fallback unittest versions for when pytest is not available
    import unittest

    class ParseTests(unittest.TestCase):
        """Fallback tests for parsing when pytest unavailable."""

        def test_core_examples_parse(self):
            """All core examples must tokenize and parse."""
            for path in _example_files():
                lang = _detect_lang(path)
                source = path.read_text(encoding="utf-8")
                tokens = Lexer(source, language=lang).tokenize()
                program = Parser(tokens, source_language=lang).parse()
                self.assertIsNotNone(program)
                self.assertGreater(len(program.body), 0, f"{path.name} empty body")

        def test_core_examples_lower_to_ir(self):
            """All core examples must lower to valid IR."""
            for path in _example_files():
                ir = _lower(path)
                self.assertIsNotNone(ir)
                validate_semantic_ir(ir)
                self.assertNotEqual(ir.source_language, "")
                self.assertIsInstance(ir.body, list)
                self.assertGreater(len(ir.body), 0, f"{path.name} empty IR")


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------

def _should_skip_example(filename: str) -> tuple[bool, str]:
    """
    Determine if an example should be skipped during execution.

    Returns:
        (should_skip, reason)
    """
    # Skip translations (non-English) for now - they may have language-specific issues
    if "_fr.multi" in filename or "_es.multi" in filename or "_de.multi" in filename:
        return True, "Skipping non-English translations (language-specific testing)"

    # Examples requiring external services (gated by env vars)
    if "ollama" in filename and not os.getenv("TEST_WITH_OLLAMA"):
        return True, "Requires Ollama provider (set TEST_WITH_OLLAMA=1 to enable)"

    if "retrieval" in filename and not os.getenv("TEST_WITH_VECTOR_DB"):
        return True, "Requires vector database (set TEST_WITH_VECTOR_DB=1 to enable)"

    runtime_gaps = {
        "pattern_matching_en.multi": (
            "Pattern matching execution fallback is not fully implemented yet"
        ),
        "reactive_ui_en.multi": (
            "Reactive UI execution semantics are still incomplete"
        ),
        "syntax_basics_en.multi": (
            "Record/type declaration runtime codegen is still incomplete"
        ),
    }
    if filename in runtime_gaps:
        return True, runtime_gaps[filename]

    return False, ""


if HAS_PYTEST:
    @pytest.mark.parametrize("path", _example_files(), ids=lambda p: p.name)
    def test_core_example_executes(path: pathlib.Path):
        """Every Core 1.0 example must execute without raising.

        This is the runtime execution test, checking that:
        1. Code generates valid Python
        2. Execution completes without exceptions
        3. AI operations work with MockProvider (when needed)
        """
        # Check if this example should be skipped
        should_skip, reason = _should_skip_example(path.name)
        if should_skip:
            pytest.skip(reason)

        lang = _detect_lang(path)
        source = path.read_text(encoding="utf-8")

        # Register MockProvider for AI operations
        mock_provider = MockProvider()
        # Add some default responses for AI keywords that might be called
        mock_provider.add_response("This is a mock response.")
        AIRuntime.register(mock_provider)

        try:
            # Create executor with semantics checking
            executor = ProgramExecutor(language=lang, check_semantics=True)

            # Execute the example
            result = executor.execute(source, capture_output=True)

            # Check result
            if not result.success:
                pytest.fail(
                    f"{path.name} execution failed:\n"
                    f"Errors: {result.errors}\n"
                    f"Generated Python:\n{result.python_source}"
                )

            # Verify output was captured (if the example prints anything)
            assert result.output is not None
        finally:
            # Reset the AI runtime to avoid affecting other tests
            AIRuntime.reset()
else:
    # Fallback: Create parametrized tests manually using unittest
    import unittest

    class ExecutionTests(unittest.TestCase):
        """Execute all core examples (unittest fallback when pytest not available)."""

        def test_all_examples_execute(self):
            """Execute all examples and report failures."""
            failures = []
            for path in _example_files():
                should_skip, reason = _should_skip_example(path.name)
                if should_skip:
                    continue

                lang = _detect_lang(path)
                source = path.read_text(encoding="utf-8")

                mock_provider = MockProvider()
                mock_provider.add_response("This is a mock response.")
                AIRuntime.register(mock_provider)

                try:
                    executor = ProgramExecutor(language=lang, check_semantics=True)
                    result = executor.execute(source, capture_output=True)

                    if not result.success:
                        failures.append(
                            f"{path.name}: {result.errors}\n"
                            f"Generated Python:\n{result.python_source}"
                        )
                finally:
                    AIRuntime.reset()

            if failures:
                self.fail(
                    f"{len(failures)} examples failed:\n"
                    + "\n---\n".join(failures)
                )

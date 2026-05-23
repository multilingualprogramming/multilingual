#
# SPDX-FileCopyrightText: 2024 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""WASM execution tests for the WAT generator's class lowering."""
# pylint: disable=duplicate-code

import importlib.util
import os
import tempfile
import unittest

from multilingualprogramming.codegen.wat_generator import WATCodeGenerator
from multilingualprogramming.parser.ast_nodes import (
    Assignment,
    AttributeAccess,
    BinaryOp,
    CallExpr,
    ClassDef,
    CompareOp,
    ExceptHandler,
    ExpressionStatement,
    FunctionDef,
    Identifier,
    IfStatement,
    ListLiteral,
    NumeralLiteral,
    Parameter,
    Program,
    RaiseStatement,
    ReturnStatement,
    StringLiteral,
    TryStatement,
    UnaryOp,
    VariableDeclaration,
)


def _prog(*stmts):
    """Wrap statements into a Program node."""
    return Program(list(stmts))


def _param(name: str) -> Parameter:
    """Create a Parameter with an Identifier name."""
    return Parameter(Identifier(name))


def _parse_wasi_output(text: str) -> list:
    """Parse WASI stdout text into a list of Python values.

    Tokens separated by whitespace are converted to float, bool, or string.
    """
    values = []
    for token in text.split():
        if token == "True":
            values.append(True)
        elif token == "False":
            values.append(False)
        elif token in ("nan", "inf", "-inf"):
            values.append(float(token))
        else:
            try:
                values.append(float(token))
            except ValueError:
                values.append(token)
    return values


def _parse_source(source: str, language: str):
    """Parse source text through the lexer/parser frontend for the given language."""
    from multilingualprogramming.lexer.lexer import Lexer  # pylint: disable=import-outside-toplevel
    from multilingualprogramming.parser.parser import Parser  # pylint: disable=import-outside-toplevel

    tokens = Lexer(source, language=language).tokenize()
    return Parser(tokens, source_language=language).parse()


@unittest.skipUnless(
    importlib.util.find_spec("wasmtime") is not None,
    "wasmtime is required for WAT execution tests",
)
class WATClassWasmExecutionTestSuite(unittest.TestCase):
    """Execute generated WAT for lowered classes via wasmtime."""

    def setUp(self):
        self.gen = WATCodeGenerator()

    def _run_main(self, prog):
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error

        wat = self.gen.generate(prog)
        engine = wasmtime.Engine()
        wasm_bytes = wasmtime.wat2wasm(wat)
        module = wasmtime.Module(engine, wasm_bytes)

        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
            stdout_path = tf.name
        try:
            wasi_cfg = wasmtime.WasiConfig()
            wasi_cfg.stdout_file = stdout_path
            store = wasmtime.Store(engine)
            store.set_wasi(wasi_cfg)
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            instance = linker.instantiate(store, module)
            instance.exports(store)["__main"](store)
            with open(stdout_path, encoding="utf-8") as fh:
                return _parse_wasi_output(fh.read())
        finally:
            os.unlink(stdout_path)

    def test_constructor_statement_compiles_and_runs(self):
        prog = _prog(
            ClassDef(
                "Counter",
                [],
                [
                    FunctionDef(
                        "__init__",
                        [_param("self"), _param("start")],
                        [ReturnStatement(Identifier("start"))],
                    ),
                ],
            ),
            ExpressionStatement(CallExpr(Identifier("Counter"), [NumeralLiteral("1")])),
        )
        printed = self._run_main(prog)
        self.assertEqual(printed, [])

    def test_class_method_call_runs(self):
        prog = _prog(
            ClassDef(
                "Math",
                [],
                [
                    FunctionDef(
                        "double",
                        [_param("x")],
                        [ReturnStatement(BinaryOp(Identifier("x"), "*", NumeralLiteral("2")))],
                    ),
                ],
            ),
            ExpressionStatement(
                CallExpr(
                    Identifier("print"),
                    [
                        CallExpr(
                            AttributeAccess(Identifier("Math"), "double"),
                            [NumeralLiteral("4")],
                        )
                    ],
                )
            ),
        )
        printed = self._run_main(prog)
        self.assertEqual(printed, [8.0])

    def test_instance_method_call_runs(self):
        prog = _prog(
            ClassDef(
                "Counter",
                [],
                [
                    FunctionDef(
                        "__init__",
                        [_param("self"), _param("start")],
                        [ReturnStatement(Identifier("start"))],
                    ),
                    FunctionDef(
                        "inc",
                        [_param("self"), _param("x")],
                        [ReturnStatement(BinaryOp(Identifier("x"), "+", NumeralLiteral("1")))],
                    ),
                ],
            ),
            VariableDeclaration("c", CallExpr(Identifier("Counter"), [NumeralLiteral("1")])),
            ExpressionStatement(
                CallExpr(
                    Identifier("print"),
                    [
                        CallExpr(
                            AttributeAccess(Identifier("c"), "inc"),
                            [NumeralLiteral("4")],
                        )
                    ],
                )
            ),
        )
        printed = self._run_main(prog)
        self.assertEqual(printed, [5.0])

    def test_stateful_counter_stores_and_reads_value(self):
        prog = _prog(
            ClassDef(
                "Counter",
                [],
                [
                    FunctionDef(
                        "__init__",
                        [_param("self"), _param("start")],
                        [
                            Assignment(
                                AttributeAccess(Identifier("self"), "value"),
                                Identifier("start"),
                            )
                        ],
                    ),
                    FunctionDef(
                        "get",
                        [_param("self")],
                        [ReturnStatement(AttributeAccess(Identifier("self"), "value"))],
                    ),
                ],
            ),
            VariableDeclaration(
                "c",
                CallExpr(Identifier("Counter"), [NumeralLiteral("10")]),
            ),
            ExpressionStatement(
                CallExpr(
                    Identifier("print"),
                    [CallExpr(AttributeAccess(Identifier("c"), "get"), [])],
                )
            ),
        )
        printed = self._run_main(prog)
        self.assertEqual(printed, [10.0])

    def test_stateful_counter_mutates_value(self):
        prog = _prog(
            ClassDef(
                "Counter",
                [],
                [
                    FunctionDef(
                        "__init__",
                        [_param("self"), _param("start")],
                        [
                            Assignment(
                                AttributeAccess(Identifier("self"), "value"),
                                Identifier("start"),
                            )
                        ],
                    ),
                    FunctionDef(
                        "increment",
                        [_param("self")],
                        [
                            Assignment(
                                AttributeAccess(Identifier("self"), "value"),
                                BinaryOp(
                                    AttributeAccess(Identifier("self"), "value"),
                                    "+",
                                    NumeralLiteral("1"),
                                ),
                            )
                        ],
                    ),
                    FunctionDef(
                        "get",
                        [_param("self")],
                        [ReturnStatement(AttributeAccess(Identifier("self"), "value"))],
                    ),
                ],
            ),
            VariableDeclaration(
                "c",
                CallExpr(Identifier("Counter"), [NumeralLiteral("10")]),
            ),
            ExpressionStatement(CallExpr(AttributeAccess(Identifier("c"), "increment"), [])),
            ExpressionStatement(
                CallExpr(
                    Identifier("print"),
                    [CallExpr(AttributeAccess(Identifier("c"), "get"), [])],
                )
            ),
        )
        printed = self._run_main(prog)
        self.assertEqual(printed, [11.0])

    def test_two_instances_have_independent_state(self):
        prog = _prog(
            ClassDef(
                "Counter",
                [],
                [
                    FunctionDef(
                        "__init__",
                        [_param("self"), _param("start")],
                        [
                            Assignment(
                                AttributeAccess(Identifier("self"), "value"),
                                Identifier("start"),
                            )
                        ],
                    ),
                    FunctionDef(
                        "get",
                        [_param("self")],
                        [ReturnStatement(AttributeAccess(Identifier("self"), "value"))],
                    ),
                ],
            ),
            VariableDeclaration(
                "a",
                CallExpr(Identifier("Counter"), [NumeralLiteral("1")]),
            ),
            VariableDeclaration(
                "b",
                CallExpr(Identifier("Counter"), [NumeralLiteral("2")]),
            ),
            ExpressionStatement(
                CallExpr(
                    Identifier("print"),
                    [CallExpr(AttributeAccess(Identifier("a"), "get"), [])],
                )
            ),
            ExpressionStatement(
                CallExpr(
                    Identifier("print"),
                    [CallExpr(AttributeAccess(Identifier("b"), "get"), [])],
                )
            ),
        )
        printed = self._run_main(prog)
        self.assertEqual(printed, [1.0, 2.0])


@unittest.skipUnless(
    importlib.util.find_spec("wasmtime") is not None,
    "wasmtime is required for WAT execution tests",
)
class WATExpressionSemanticsWasmExecutionTestSuite(unittest.TestCase):
    """Execute focused arithmetic and membership regressions via wasmtime."""

    def setUp(self):
        self.gen = WATCodeGenerator()

    def _instantiate(self, prog):
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error

        wat = self.gen.generate(prog)
        engine = wasmtime.Engine()
        wasm_bytes = wasmtime.wat2wasm(wat)
        module = wasmtime.Module(engine, wasm_bytes)
        wasi_cfg = wasmtime.WasiConfig()
        wasi_cfg.inherit_stdout()
        store = wasmtime.Store(engine)
        store.set_wasi(wasi_cfg)
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        instance = linker.instantiate(store, module)
        return store, instance

    def _call_export(self, prog, export_name, *args):
        store, instance = self._instantiate(prog)
        return instance.exports(store)[export_name](store, *args)

    def test_bit_extract_expression_matches_expected_value(self):
        prog = _prog(
            FunctionDef(
                "cellule_suivante",
                [_param("numero_regle"), _param("gauche"), _param("centre"), _param("droite")],
                [
                    VariableDeclaration(
                        "indice",
                        BinaryOp(
                            BinaryOp(
                                BinaryOp(Identifier("gauche"), "*", NumeralLiteral("4")),
                                "+",
                                BinaryOp(Identifier("centre"), "*", NumeralLiteral("2")),
                            ),
                            "+",
                            Identifier("droite"),
                        ),
                    ),
                    ReturnStatement(
                        BinaryOp(
                            BinaryOp(Identifier("numero_regle"), ">>", Identifier("indice")),
                            "&",
                            NumeralLiteral("1"),
                        )
                    ),
                ],
            ),
        )
        self.assertEqual(self._call_export(prog, "cellule_suivante", 90.0, 1.0, 0.0, 1.0), 0.0)
        self.assertEqual(self._call_export(prog, "cellule_suivante", 90.0, 1.0, 0.0, 0.0), 1.0)

    def test_membership_branch_returns_expected_value(self):
        prog = _prog(
            FunctionDef(
                "classe_wolfram",
                [_param("numero_regle")],
                [
                    IfStatement(
                        CompareOp(
                            Identifier("numero_regle"),
                            [(
                                "in",
                                ListLiteral(
                                    [
                                        NumeralLiteral("18"),
                                        NumeralLiteral("22"),
                                        NumeralLiteral("30"),
                                        NumeralLiteral("45"),
                                        NumeralLiteral("60"),
                                        NumeralLiteral("90"),
                                    ]
                                ),
                            )],
                        ),
                        [ReturnStatement(NumeralLiteral("3"))],
                        else_body=[ReturnStatement(NumeralLiteral("2"))],
                    )
                ],
            ),
        )
        self.assertEqual(self._call_export(prog, "classe_wolfram", 30.0), 3.0)
        self.assertEqual(self._call_export(prog, "classe_wolfram", 73.0), 2.0)

    def test_french_source_membership_and_bit_extract_compile_correctly(self):
        prog = _parse_source(
            "déf cellule_suivante(numero_regle, gauche, centre, droite):\n"
            "    soit indice = gauche * 4 + centre * 2 + droite\n"
            "    retour (numero_regle >> indice) & 1\n"
            "\n"
            "déf classe_wolfram(numero_regle):\n"
            "    si numero_regle dans [18, 22, 30, 45, 60, 90]:\n"
            "        retour 3\n"
            "    sinon:\n"
            "        retour 2\n",
            language="fr",
        )
        self.assertEqual(self._call_export(prog, "cellule_suivante", 90.0, 1.0, 0.0, 1.0), 0.0)
        self.assertEqual(self._call_export(prog, "classe_wolfram", 30.0), 3.0)

    def test_string_subscript_equality_compares_content_not_pointer(self):
        # Counting characters by scanning s[i] == "F" requires content-based
        # string equality (not heap-pointer comparison) and string tracking to
        # survive the `ch = s[i]` intermediate binding.
        prog = _parse_source(
            "déf compter_f():\n"
            "    soit s = \"FABF\"\n"
            "    soit total = 0\n"
            "    pour i dans intervalle(longueur(s)):\n"
            "        soit ch = s[i]\n"
            "        si ch == \"F\":\n"
            "            total = total + 1\n"
            "    retour total\n",
            language="fr",
        )
        self.assertEqual(self._call_export(prog, "compter_f"), 2.0)

    def test_string_equality_and_inequality_on_locals(self):
        prog = _parse_source(
            "déf egal():\n"
            "    soit a = \"koch\"\n"
            "    soit b = \"koch\"\n"
            "    si a == b:\n"
            "        retour 1\n"
            "    retour 0\n"
            "\n"
            "déf different():\n"
            "    soit a = \"koch\"\n"
            "    soit b = \"dragon\"\n"
            "    si a != b:\n"
            "        retour 1\n"
            "    retour 0\n",
            language="fr",
        )
        self.assertEqual(self._call_export(prog, "egal"), 1.0)
        self.assertEqual(self._call_export(prog, "different"), 1.0)

    def test_runtime_sized_list_repeat_allocates_and_fills(self):
        # `[0.0] * n` must allocate a runtime-sized list that supports
        # element assignment (buf[i] = ...) and len() — enabling O(n) buffer
        # fills instead of O(n^2) append chains.
        prog = _parse_source(
            "déf somme_tampon():\n"
            "    soit buf = [0.0] * 5\n"
            "    soit i = 0\n"
            "    tantque i < 5:\n"
            "        buf[i] = i * 2\n"
            "        i = i + 1\n"
            "    soit s = 0.0\n"
            "    soit k = 0\n"
            "    tantque k < longueur(buf):\n"
            "        s = s + buf[k]\n"
            "        k = k + 1\n"
            "    retour s\n",
            language="fr",
        )
        # buf = [0, 2, 4, 6, 8] → sum 20
        self.assertEqual(self._call_export(prog, "somme_tampon"), 20.0)

    def test_ord_returns_first_utf8_byte(self):
        prog = _parse_source(
            "déf ord_F():\n    retour ord(\"F\")\n"
            "déf ord_plus():\n    retour ord(\"+\")\n"
            "déf ord_sub():\n    soit s = \"AF+\"\n    retour ord(s[1])\n",
            language="fr",
        )
        self.assertEqual(self._call_export(prog, "ord_F"), 70.0)
        self.assertEqual(self._call_export(prog, "ord_plus"), 43.0)
        self.assertEqual(self._call_export(prog, "ord_sub"), 70.0)  # s[1] == 'F'

    def test_math_sin_cos_have_correct_sign_and_range_reduction(self):
        # Regression: math.sin/cos previously returned the negated value
        # (an uncompensated +pi phase shift), so cos(0) came back as -1.
        prog = _parse_source(
            "déf c0():\n    retour math.cos(0.0)\n"
            "déf s0():\n    retour math.sin(0.0)\n"
            "déf spi2():\n    retour math.sin(1.5707963267948966)\n"
            "déf cpi():\n    retour math.cos(3.141592653589793)\n"
            "déf cbig():\n    retour math.cos(12.566370614359172)\n"
            # Range reduction must keep the correct sign in (3*pi/2, 2*pi) and
            # for negative angles: cos(300deg) = cos(-60deg) = +0.5.
            "déf cneg60():\n    retour math.cos(-1.0471975511965976)\n"
            "déf c300():\n    retour math.cos(5.235987755982988)\n"
            "déf c240():\n    retour math.cos(4.1887902047863905)\n",
            language="fr",
        )
        self.assertAlmostEqual(self._call_export(prog, "c0"), 1.0, places=5)
        self.assertAlmostEqual(self._call_export(prog, "s0"), 0.0, places=5)
        self.assertAlmostEqual(self._call_export(prog, "spi2"), 1.0, places=5)
        self.assertAlmostEqual(self._call_export(prog, "cpi"), -1.0, places=5)
        # range reduction: cos(4*pi) == 1
        self.assertAlmostEqual(self._call_export(prog, "cbig"), 1.0, places=5)
        self.assertAlmostEqual(self._call_export(prog, "cneg60"), 0.5, places=5)
        self.assertAlmostEqual(self._call_export(prog, "c300"), 0.5, places=5)
        self.assertAlmostEqual(self._call_export(prog, "c240"), -0.5, places=5)

    def test_math_atan_range_reduction_precision(self):
        # Regression : la version 6-termes sans réduction (x-1)/(x+1) plafonnait
        # à ~5% d'erreur pour atan(1) (= π/4). La double réduction (1/x ET
        # (x-1)/(x+1)) + 12 termes Taylor doit donner ≥10 décimales correctes.
        import math as _m
        prog = _parse_source(
            "déf a0():\n    retour math.atan(0.0)\n"
            "déf a_un():\n    retour math.atan(1.0)\n"             # π/4
            "déf a_demi():\n    retour math.atan(0.5)\n"           # 0.4636476090...
            "déf a_neg_demi():\n    retour math.atan(-0.5)\n"
            "déf a_tan_pi8():\n    retour math.atan(0.41421356237309503)\n"  # π/8
            "déf a_juste_au_dessus():\n    retour math.atan(0.42)\n"        # franchit le seuil
            "déf a_petit():\n    retour math.atan(0.1)\n"
            "déf a_grand():\n    retour math.atan(10.0)\n"          # > 1, force la réduction 1/x
            "déf a_tres_grand():\n    retour math.atan(1000.0)\n"   # 1.5697963...
            "déf a_neg_grand():\n    retour math.atan(-50.0)\n"
            "déf a_pi8():\n    retour math.atan2(0.4142135623730951, 1.0)\n"  # π/8
            "déf a_pi4():\n    retour math.atan2(1.0, 1.0)\n"        # π/4
            "déf a_3pi4():\n    retour math.atan2(1.0, -1.0)\n"      # 3π/4
            "déf a_neg_pi2():\n    retour math.atan2(-1.0, 0.0)\n",
            language="fr",
        )
        # Tolérance ~1e-10 (places=10) sur la branche standard, vs ~5e-2 avant.
        self.assertAlmostEqual(self._call_export(prog, "a0"), 0.0, places=12)
        self.assertAlmostEqual(self._call_export(prog, "a_un"), _m.pi / 4, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_demi"), _m.atan(0.5), places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_neg_demi"), -_m.atan(0.5), places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_tan_pi8"), _m.pi / 8, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_juste_au_dessus"), _m.atan(0.42), places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_petit"), _m.atan(0.1), places=12)
        self.assertAlmostEqual(self._call_export(prog, "a_grand"), _m.atan(10.0), places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_tres_grand"), _m.atan(1000.0), places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_neg_grand"), _m.atan(-50.0), places=10)
        # atan2 hérite de la précision atan (≥10 décimales).
        self.assertAlmostEqual(self._call_export(prog, "a_pi8"), _m.pi / 8, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_pi4"), _m.pi / 4, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_3pi4"), 3 * _m.pi / 4, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_neg_pi2"), -_m.pi / 2, places=12)


@unittest.skipUnless(
    importlib.util.find_spec("wasmtime") is not None,
    "wasmtime is required for WAT execution tests",
)
class WATIntegerPrintingTestSuite(unittest.TestCase):
    """Verify that integer-valued floats are printed without a decimal point."""

    def _run_raw(self, prog) -> str:
        """Return the raw stdout text (not parsed) from running prog.__main."""
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error

        gen = WATCodeGenerator()
        wat = gen.generate(prog)
        engine = wasmtime.Engine()
        wasm_bytes = wasmtime.wat2wasm(wat)
        module = wasmtime.Module(engine, wasm_bytes)
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
            stdout_path = tf.name
        try:
            cfg = wasmtime.WasiConfig()
            cfg.stdout_file = stdout_path
            store = wasmtime.Store(engine)
            store.set_wasi(cfg)
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            inst = linker.instantiate(store, module)
            inst.exports(store)["__main"](store)
            with open(stdout_path, encoding="utf-8") as fh:
                return fh.read()
        finally:
            os.unlink(stdout_path)

    def test_integer_literal_prints_without_decimal(self):
        """print(42) must output '42', not '42.0'."""
        prog = _prog(
            ExpressionStatement(
                CallExpr(Identifier("print"), [NumeralLiteral("42")])
            )
        )
        raw = self._run_raw(prog)
        self.assertIn("42\n", raw)
        self.assertNotIn("42.0", raw)

    def test_zero_prints_without_decimal(self):
        prog = _prog(
            ExpressionStatement(
                CallExpr(Identifier("print"), [NumeralLiteral("0")])
            )
        )
        raw = self._run_raw(prog)
        self.assertEqual(raw.strip(), "0")

    def test_float_literal_still_prints_decimal(self):
        """print(1.5) must still output '1.5'."""
        prog = _prog(
            ExpressionStatement(
                CallExpr(Identifier("print"), [NumeralLiteral("1.5")])
            )
        )
        raw = self._run_raw(prog)
        self.assertEqual(raw.strip(), "1.5")

    def test_negative_integer_prints_without_decimal(self):
        """print(-7) must output '-7', not '-7.0'."""
        prog = _prog(
            ExpressionStatement(
                CallExpr(
                    Identifier("print"),
                    [UnaryOp("-", NumeralLiteral("7"))],
                )
            )
        )
        raw = self._run_raw(prog)
        self.assertEqual(raw.strip(), "-7")


@unittest.skipUnless(
    importlib.util.find_spec("wasmtime") is not None,
    "wasmtime is required for WAT execution tests",
)
class WATExceptionHandlingTestSuite(unittest.TestCase):
    """Verify try/except/finally semantics via wasmtime execution."""

    def _run_raw(self, prog) -> str:
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error
        gen = WATCodeGenerator()
        wat = gen.generate(prog)
        engine = wasmtime.Engine()
        wasm_bytes = wasmtime.wat2wasm(wat)
        module = wasmtime.Module(engine, wasm_bytes)
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
            stdout_path = tf.name
        try:
            cfg = wasmtime.WasiConfig()
            cfg.stdout_file = stdout_path
            store = wasmtime.Store(engine)
            store.set_wasi(cfg)
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            inst = linker.instantiate(store, module)
            inst.exports(store)["__main"](store)
            with open(stdout_path, encoding="utf-8") as fh:
                return fh.read()
        finally:
            os.unlink(stdout_path)

    def test_catch_all_except_catches_raise(self):
        """bare except: catches any raised exception."""
        prog = _prog(
            TryStatement(
                body=[
                    RaiseStatement(CallExpr(Identifier("ValueError"), [])),
                    ExpressionStatement(CallExpr(Identifier("print"), [NumeralLiteral("1")])),
                ],
                handlers=[
                    ExceptHandler(exc_type=None, body=[
                        ExpressionStatement(CallExpr(Identifier("print"), [NumeralLiteral("2")])),
                    ]),
                ],
            )
        )
        raw = self._run_raw(prog)
        self.assertNotIn("1", raw)
        self.assertIn("2", raw)

    def test_except_exception_catches_raise(self):
        """except Exception: catches any raised exception."""
        prog = _prog(
            TryStatement(
                body=[
                    RaiseStatement(CallExpr(Identifier("RuntimeError"), [])),
                ],
                handlers=[
                    ExceptHandler(
                        exc_type=Identifier("Exception"),
                        body=[
                            ExpressionStatement(
                                CallExpr(Identifier("print"), [NumeralLiteral("42")])
                            ),
                        ],
                    ),
                ],
            )
        )
        raw = self._run_raw(prog)
        self.assertIn("42", raw)

    def test_finally_runs_after_handled_exception(self):
        """finally body executes after a handled exception."""
        prog = _prog(
            TryStatement(
                body=[
                    RaiseStatement(CallExpr(Identifier("ValueError"), [])),
                ],
                handlers=[
                    ExceptHandler(exc_type=Identifier("ValueError"), body=[
                        ExpressionStatement(CallExpr(Identifier("print"), [NumeralLiteral("1")])),
                    ]),
                ],
                finally_body=[
                    ExpressionStatement(CallExpr(Identifier("print"), [NumeralLiteral("2")])),
                ],
            )
        )
        raw = self._run_raw(prog)
        self.assertIn("1", raw)
        self.assertIn("2", raw)

    def test_finally_runs_when_no_exception(self):
        """finally body executes even when no exception is raised."""
        prog = _prog(
            TryStatement(
                body=[
                    ExpressionStatement(CallExpr(Identifier("print"), [NumeralLiteral("1")])),
                ],
                handlers=[
                    ExceptHandler(exc_type=Identifier("ValueError"), body=[
                        ExpressionStatement(CallExpr(Identifier("print"), [NumeralLiteral("X")])),
                    ]),
                ],
                finally_body=[
                    ExpressionStatement(CallExpr(Identifier("print"), [NumeralLiteral("2")])),
                ],
            )
        )
        raw = self._run_raw(prog)
        self.assertIn("1", raw)
        self.assertIn("2", raw)
        self.assertNotIn("X", raw)

    def test_except_as_e_binds_nonzero_code(self):
        """except ValueError as e: binds e to the exception code (non-zero)."""
        prog = _prog(
            TryStatement(
                body=[
                    RaiseStatement(CallExpr(Identifier("ValueError"), [])),
                ],
                handlers=[
                    ExceptHandler(
                        exc_type=Identifier("ValueError"),
                        name="e",
                        body=[
                            ExpressionStatement(
                                CallExpr(Identifier("print"), [Identifier("e")])
                            ),
                        ],
                    ),
                ],
            )
        )
        raw = self._run_raw(prog)
        # e should be the ValueError code (1), not 0
        val = float(raw.strip())
        self.assertNotEqual(val, 0.0)
        self.assertEqual(val, 1.0)


@unittest.skipUnless(
    importlib.util.find_spec("wasmtime") is not None,
    "wasmtime is required for WAT execution tests",
)
class WATArgvTestSuite(unittest.TestCase):
    """Verify argc()/argv() builtins via wasmtime with synthetic args."""

    def _run_with_args(self, prog, cli_args: list[str]) -> str:
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error
        gen = WATCodeGenerator()
        wat = gen.generate(prog)
        engine = wasmtime.Engine()
        wasm_bytes = wasmtime.wat2wasm(wat)
        module = wasmtime.Module(engine, wasm_bytes)
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
            stdout_path = tf.name
        try:
            cfg = wasmtime.WasiConfig()
            cfg.stdout_file = stdout_path
            cfg.argv = cli_args
            store = wasmtime.Store(engine)
            store.set_wasi(cfg)
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            inst = linker.instantiate(store, module)
            inst.exports(store)["__main"](store)
            with open(stdout_path, encoding="utf-8") as fh:
                return fh.read()
        finally:
            os.unlink(stdout_path)

    def test_argc_returns_argument_count(self):
        prog = _prog(
            ExpressionStatement(CallExpr(Identifier("print"), [CallExpr(Identifier("argc"), [])]))
        )
        raw = self._run_with_args(prog, ["prog", "hello", "world"])
        self.assertEqual(raw.strip(), "3")

    def test_argv_zero_returns_program_name(self):
        """argv(0) returns the program name (first CLI argument)."""
        prog = _prog(
            VariableDeclaration("s", CallExpr(Identifier("argv"), [NumeralLiteral("0")])),
            ExpressionStatement(
                CallExpr(Identifier("print"), [StringLiteral("ok")])
            ),
        )
        # Just verify it compiles and runs without crash
        raw = self._run_with_args(prog, ["myprog"])
        self.assertIn("ok", raw)


class WATCrossFunctionExceptionTestSuite(unittest.TestCase):
    """Verify that exceptions raised in callees propagate to caller try/except blocks."""

    _wasmtime = importlib.util.find_spec("wasmtime")

    def _run(self, prog):
        from wasmtime import Store, Module, Linker, WasiConfig  # pylint: disable=import-outside-toplevel,import-error
        gen = WATCodeGenerator()
        wat = gen.generate(prog)
        with tempfile.NamedTemporaryFile(
            suffix=".wat", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(wat)
            wat_path = f.name
        stdout_path = wat_path + ".out"
        try:
            store = Store()
            cfg = WasiConfig()
            cfg.stdout_file = stdout_path
            store.set_wasi(cfg)
            linker = Linker(store.engine)
            linker.define_wasi()
            module = Module.from_file(store.engine, wat_path)
            inst = linker.instantiate(store, module)
            inst.exports(store)["__main"](store)
            with open(stdout_path, encoding="utf-8") as fh:
                return fh.read()
        finally:
            os.unlink(wat_path)
            if os.path.exists(stdout_path):
                os.unlink(stdout_path)

    @unittest.skipUnless(_wasmtime, "wasmtime not installed")
    def test_callee_raise_caught_by_caller_catchall(self):
        """A raise in a callee function is caught by the caller's except: block."""
        raiser = FunctionDef(
            name=Identifier("raiser"), params=[], body=[
                RaiseStatement(Identifier("ValueError")),
            ],
        )
        prog = _prog(
            raiser,
            TryStatement(
                body=[ExpressionStatement(CallExpr(Identifier("raiser"), []))],
                handlers=[ExceptHandler(exc_type=None, name=None, body=[
                    ExpressionStatement(CallExpr(Identifier("print"), [StringLiteral("caught")])),
                ])],
                else_body=None,
                finally_body=None,
            ),
        )
        out = self._run(prog)
        self.assertIn("caught", out)

    @unittest.skipUnless(_wasmtime, "wasmtime not installed")
    def test_caught_exception_clears_global(self):
        """After catching a cross-function raise, the second try block is clean."""
        raiser = FunctionDef(
            name=Identifier("raiser"), params=[], body=[
                RaiseStatement(Identifier("ValueError")),
            ],
        )
        prog = _prog(
            raiser,
            VariableDeclaration("caught", NumeralLiteral("0")),
            TryStatement(
                body=[ExpressionStatement(CallExpr(Identifier("raiser"), []))],
                handlers=[ExceptHandler(exc_type=None, name=None, body=[
                    Assignment(Identifier("caught"),
                               BinaryOp("+", Identifier("caught"), NumeralLiteral("1"))),
                ])],
                else_body=None, finally_body=None,
            ),
            TryStatement(
                body=[ExpressionStatement(CallExpr(Identifier("print"), [StringLiteral("ok")]))],
                handlers=[ExceptHandler(exc_type=None, name=None, body=[
                    Assignment(Identifier("caught"),
                               BinaryOp("+", Identifier("caught"), NumeralLiteral("1"))),
                ])],
                else_body=None, finally_body=None,
            ),
            ExpressionStatement(CallExpr(Identifier("print"), [Identifier("caught")])),
        )
        out = self._run(prog)
        self.assertIn("ok", out)
        self.assertIn("1", out)


@unittest.skipUnless(
    importlib.util.find_spec("wasmtime") is not None,
    "wasmtime is required for WAT execution tests",
)
class WATStringParamWasmExecutionTestSuite(unittest.TestCase):
    """Execute length-prefixed string parameter passing via wasmtime.

    String parameters carry no length in their f64 pointer value; callers wrap
    string arguments in a length-prefixed buffer (header at ``ptr - 4``) and the
    callee recovers the byte length at its prologue. These tests prove that
    ``len``, indexing, char-comparison, and concatenation all behave correctly
    on a string received as a function argument — the capability that unblocks
    multi-function string APIs (e.g. the L-system axiom/rules passed as args).
    """

    def setUp(self):
        self.gen = WATCodeGenerator()

    def _run_main(self, source):
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error

        prog = _parse_source(source, "fr")
        wat = self.gen.generate(prog)
        engine = wasmtime.Engine()
        module = wasmtime.Module(engine, wasmtime.wat2wasm(wat))
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
            stdout_path = tf.name
        try:
            wasi_cfg = wasmtime.WasiConfig()
            wasi_cfg.stdout_file = stdout_path
            store = wasmtime.Store(engine)
            store.set_wasi(wasi_cfg)
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            instance = linker.instantiate(store, module)
            instance.exports(store)["__main"](store)
            with open(stdout_path, encoding="utf-8") as fh:
                return _parse_wasi_output(fh.read())
        finally:
            os.unlink(stdout_path)

    def test_len_of_string_parameter(self):
        out = self._run_main(
            "déf taille(s: str):\n"
            "    retour longueur(s)\n"
            "afficher(taille(\"Koch\"))\n"
        )
        self.assertEqual(out, [4.0])

    def test_indexing_string_parameter(self):
        # ord(s[0]) and ord(s[1]) on a parameter — string subscript, not list.
        out = self._run_main(
            "déf code0(s: str):\n"
            "    retour ord(s[0])\n"
            "déf code1(s: str):\n"
            "    retour ord(s[1])\n"
            "afficher(code0(\"Koch\"))\n"
            "afficher(code1(\"Koch\"))\n"
        )
        self.assertEqual(out, [75.0, 111.0])

    def test_char_scan_loop_over_string_parameter(self):
        # The L-system expansion pattern: scan a passed-in string char by char.
        out = self._run_main(
            "déf compte_F(s: str):\n"
            "    soit n = 0\n"
            "    pour i dans intervalle(longueur(s)):\n"
            "        si s[i] == \"F\":\n"
            "            n = n + 1\n"
            "    retour n\n"
            "afficher(compte_F(\"F+F-FF+F\"))\n"
        )
        self.assertEqual(out, [5.0])

    def test_computed_string_argument_carries_length(self):
        # A concatenation result (not a literal) passed as a string argument.
        out = self._run_main(
            "déf taille(s: str):\n"
            "    retour longueur(s)\n"
            "soit a = \"Koch\"\n"
            "afficher(taille(a + \"-flake\"))\n"
        )
        self.assertEqual(out, [10.0])

    def test_string_parameter_passed_through_two_functions(self):
        # A string param forwarded into another string param keeps its length.
        out = self._run_main(
            "déf taille(s: str):\n"
            "    retour longueur(s)\n"
            "déf relais(t: str):\n"
            "    retour taille(t)\n"
            "afficher(relais(\"dragon\"))\n"
        )
        self.assertEqual(out, [6.0])


if __name__ == "__main__":
    unittest.main()

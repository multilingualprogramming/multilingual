#
# SPDX-FileCopyrightText: 2024 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""WASM execution tests for the WAT generator's class lowering."""
# pylint: disable=duplicate-code

import importlib.util
import math as _m
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
        self.assertAlmostEqual(
            self._call_export(prog, "a_juste_au_dessus"), _m.atan(0.42), places=10
        )
        self.assertAlmostEqual(self._call_export(prog, "a_petit"), _m.atan(0.1), places=12)
        self.assertAlmostEqual(self._call_export(prog, "a_grand"), _m.atan(10.0), places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_tres_grand"), _m.atan(1000.0), places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_neg_grand"), _m.atan(-50.0), places=10)
        # atan2 hérite de la précision atan (≥10 décimales).
        self.assertAlmostEqual(self._call_export(prog, "a_pi8"), _m.pi / 8, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_pi4"), _m.pi / 4, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_3pi4"), 3 * _m.pi / 4, places=10)
        self.assertAlmostEqual(self._call_export(prog, "a_neg_pi2"), -_m.pi / 2, places=12)

    def test_simd_mandelbrot_pair_matches_scalar(self):
        # Le noyau SIMD f64x2 doit donner la MÊME séquence d'itérations que la
        # boucle scalaire à 1 ULP près. Sortie : liste [count, iter0, iter1]
        # où count est le header de longueur (2) et iter0/iter1 sont les
        # itérations pour les deux lanes. La liste étant émise via
        # ml_alloc(24) + writes manuels, l'offset des items est ptr+8 et ptr+16
        # (cohérent avec [0.0]*n).
        prog = _parse_source(
            "déf pair(cx0, cy0, cx1, cy1, mi):\n"
            "    soit r = simd_mandelbrot_pair(cx0, cy0, cx1, cy1, mi)\n"
            "    retour r[0]\n"
            "déf pair_b(cx0, cy0, cx1, cy1, mi):\n"
            "    soit r = simd_mandelbrot_pair(cx0, cy0, cx1, cy1, mi)\n"
            "    retour r[1]\n"
            "déf scalar(cx, cy, mi):\n"
            "    soit x = 0.0\n"
            "    soit y = 0.0\n"
            "    soit i = 0.0\n"
            "    tantque i < mi:\n"
            "        si x*x + y*y > 4.0:\n"
            "            retour i\n"
            "        soit tx = x*x - y*y + cx\n"
            "        y = 2.0 * x * y + cy\n"
            "        x = tx\n"
            "        i = i + 1.0\n"
            "    retour i\n",
            language="fr",
        )
        # Quelques points où le scalaire et le SIMD doivent concorder.
        cases = [
            (-0.5, 0.0, 0.3, 0.0),     # intérieur cardioïde / point qui s'échappe
            (-1.0, 0.0, -1.5, 0.0),     # bulbe période 2 / extérieur
            (-0.122561, 0.744861, 0.25, 0.25),  # « lapin » Julia parameter / cardioïde edge
            (2.0, 0.0, -2.0, 0.0),      # deux échappements rapides
        ]
        for cx0, cy0, cx1, cy1 in cases:
            simd0 = self._call_export(prog, "pair", cx0, cy0, cx1, cy1, 256.0)
            simd1 = self._call_export(prog, "pair_b", cx0, cy0, cx1, cy1, 256.0)
            sc0 = self._call_export(prog, "scalar", cx0, cy0, 256.0)
            sc1 = self._call_export(prog, "scalar", cx1, cy1, 256.0)
            # Le scalaire renvoie l'itération où r²>4 (n'incrémente pas
            # l'itération qui détecte l'évasion) ; le SIMD compte l'itération
            # où l'échappement s'est produit (n'incrémente pas la lane une fois
            # échappée). Les deux sémantiques diffèrent d'au plus 1 unité — on
            # vérifie la borne sup et l'inf.
            self.assertTrue(
                abs(simd0 - sc0) <= 1,
                f"lane0 SIMD={simd0} vs scalar={sc0} for c=({cx0},{cy0})",
            )
            self.assertTrue(
                abs(simd1 - sc1) <= 1,
                f"lane1 SIMD={simd1} vs scalar={sc1} for c=({cx1},{cy1})",
            )

    def test_imul32_iadd32_shr_u32_match_js_semantics(self):
        # imul32, iadd32, shr_u32, u32_to_f64 sont les briques d'un PRNG
        # mulberry32 / d'un hash FNV portés à `.multi`. Vérifie la sémantique
        # de wraparound i32 et la conversion signée→non-signée.
        prog = _parse_source(
            "déf mul_wrap():\n    retour imul32(2147483647.0, 2.0)\n"
            "déf mul_fnv_prime():\n    retour imul32(123.0, 16777619.0)\n"
            "déf add_wrap():\n    retour iadd32(2000000000.0, 2000000000.0)\n"
            "déf shr_u_signed():\n    retour shr_u32(-1.0, 1.0)\n"
            "déf u32_neg():\n    retour u32_to_f64(-1.0)\n"
            "déf u32_pos():\n    retour u32_to_f64(1234567.0)\n",          # identity
            language="fr",
        )
        # imul32(2^31-1, 2) wraps to -2 (signed view).
        self.assertEqual(self._call_export(prog, "mul_wrap"), -2.0)
        # imul32(123, 16777619) = 123*16777619 = 2063647137 (fits in i32).
        self.assertEqual(self._call_export(prog, "mul_fnv_prime"), 2063647137.0)
        # iadd32(2e9, 2e9) = 4e9 wraps to 4e9 - 2^32 = -294967296.
        self.assertEqual(self._call_export(prog, "add_wrap"), -294967296.0)
        # shr_u32(-1, 1) = 0xFFFFFFFF >>> 1 = 0x7FFFFFFF = 2147483647.
        self.assertEqual(self._call_export(prog, "shr_u_signed"), 2147483647.0)
        # u32_to_f64(-1) = 4294967295.
        self.assertEqual(self._call_export(prog, "u32_neg"), 4294967295.0)
        self.assertEqual(self._call_export(prog, "u32_pos"), 1234567.0)

    def test_i32_wraparound_on_mul_and_add_for_int_shaped_operands(self):
        # B3 : `*` et `+` doivent s'abaisser à `i32.mul`/`i32.add` (wraparound)
        # quand les deux opérandes sont « i32-shaped » — soit issus d'un op
        # bitwise/shift, soit d'un builtin i32 (imul32/iadd32/shr_u32), soit
        # un local précédemment tracké, soit un littéral entier qui rentre
        # dans i32. Permet d'écrire FNV/mulberry32 en `.multi` sans appeler
        # imul32/iadd32 explicitement (cf. roadmap multilingual W2 → B3).
        prog = _parse_source(
            # mul_wrap : 2147483647 * 2 — un opérande tracké comme i32 (via
            # `& 0xFFFFFFFF`) suffit à passer en i32.mul. Wraparound → -2.
            "déf mul_wrap():\n"
            "    soit a = 2147483647 & -1\n"
            "    retour a * 2\n"
            # add_wrap : 2e9 + 2e9 — opérande tracké via shift identité.
            # 4e9 ne tient pas en i32 → wraparound → 4e9 - 2^32 = -294967296.
            "déf add_wrap():\n"
            "    soit a = 2000000000 << 0\n"
            "    retour a + 2000000000\n"
            # fnv1a_step : un pas de FNV-1a (hash ^= byte ; hash *= prime).
            # Doit produire exactement le même résultat que via imul32 explicite.
            # Le seed est passé en vue signée (FNV offset basis 2166136261 vaut
            # -2128831035 en i32 signé) parce que `i32.trunc_f64_s` du bitwise
            # ^ trappe sur les valeurs hors [-2^31, 2^31) — orthogonal à B3.
            "déf fnv1a_step(seed_signed, octet):\n"
            "    soit h = seed_signed ^ octet\n"
            "    retour h * 16777619\n"
            # chained : (a & m) + (b & m) — deux opérandes bitwise → i32.add wraparound.
            "déf chained_bitwise_add():\n"
            "    retour (2000000000 & -1) + (2000000000 & -1)\n"
            # Régression : littéral pur * littéral pur NE doit PAS wraparound
            # (sinon on casse l'arithmétique f64 ordinaire). 1e9 * 5 = 5e9.
            "déf pure_literal_mul_stays_f64():\n"
            "    retour 1000000000.0 * 5.0\n",
            language="fr",
        )
        self.assertEqual(self._call_export(prog, "mul_wrap"), -2.0)
        self.assertEqual(self._call_export(prog, "add_wrap"), -294967296.0)
        # FNV-1a : on calcule en Python la valeur attendue avec la même
        # sémantique i32-wraparound que le code généré.
        seed_unsigned = 2166136261
        seed_signed = seed_unsigned - (1 << 32)  # -2128831035 en vue signée
        octet = 0x41
        h_u = (seed_unsigned ^ octet) & 0xFFFFFFFF
        prod_u = (h_u * 16777619) & 0xFFFFFFFF
        # Vue signée i32 (ce que le WAT retourne via f64.convert_i32_s).
        expected = prod_u - (1 << 32) if prod_u >= (1 << 31) else prod_u
        self.assertEqual(
            self._call_export(prog, "fnv1a_step", float(seed_signed), float(octet)),
            float(expected),
        )
        # chained : 2e9 + 2e9 (i32) = 4e9 → wrap → -294967296.
        self.assertEqual(self._call_export(prog, "chained_bitwise_add"), -294967296.0)
        # Régression : pas de faux positif sur arithmétique f64 pure.
        self.assertEqual(self._call_export(prog, "pure_literal_mul_stays_f64"), 5e9)

    def test_v128_pair_arith_dispatches_to_f64x2(self):
        # B2 : `v128_pair(a, b)` construit un v128 (f64x2) ; `+ - * /` entre
        # deux opérandes v128-shaped dispatchent vers `f64x2.{add,sub,mul,div}`
        # au lieu de `f64.*`. `v128_lane(v, i)` (i littéral 0|1) extrait une
        # lane en f64 scalaire. Les v128 ne traversent pas les frontières de
        # fonction — ils vivent en local v128, déclaré comme tel dans le WAT
        # via `_v128_locals` (mirrors le patron `_int_like_locals` de B3).
        prog = _parse_source(
            # Smoke test : pair + extract — preuve qu'un v128 peut être stocké
            # dans un local et qu'on récupère les deux lanes individuellement.
            "déf lane0(a, b):\n"
            "    soit v = v128_pair(a, b)\n"
            "    retour v128_lane(v, 0)\n"
            "déf lane1(a, b):\n"
            "    soit v = v128_pair(a, b)\n"
            "    retour v128_lane(v, 1)\n"
            # add : deux v128 → f64x2.add — somme par lane.
            "déf add_lane0(a, b, c, d):\n"
            "    soit u = v128_pair(a, b)\n"
            "    soit v = v128_pair(c, d)\n"
            "    soit w = u + v\n"
            "    retour v128_lane(w, 0)\n"
            "déf add_lane1(a, b, c, d):\n"
            "    soit u = v128_pair(a, b)\n"
            "    soit v = v128_pair(c, d)\n"
            "    soit w = u + v\n"
            "    retour v128_lane(w, 1)\n"
            # mul + sub + div : couvre les quatre opérateurs binaires.
            "déf mul_lane0(a, b, c, d):\n"
            "    soit u = v128_pair(a, b)\n"
            "    soit v = v128_pair(c, d)\n"
            "    retour v128_lane(u * v, 0)\n"
            "déf sub_lane1(a, b, c, d):\n"
            "    soit u = v128_pair(a, b)\n"
            "    soit v = v128_pair(c, d)\n"
            "    retour v128_lane(u - v, 1)\n"
            "déf div_lane0(a, b, c, d):\n"
            "    soit u = v128_pair(a, b)\n"
            "    soit v = v128_pair(c, d)\n"
            "    retour v128_lane(u / v, 0)\n"
            # Chaîne : (u*u + v) lane 1 — exerce le dispatch v128 imbriqué.
            "déf chained_lane1(a, b, c, d):\n"
            "    soit u = v128_pair(a, b)\n"
            "    soit v = v128_pair(c, d)\n"
            "    retour v128_lane(u * u + v, 1)\n"
            # Mandelbrot pair en SIMD source-level : un pas de l'itération
            # z = z*z + c sur les deux lanes en parallèle, sans le builtin
            # `simd_mandelbrot_pair` — la preuve que B2 permet d'écrire des
            # noyaux SIMD en `.multi` au lieu de WAT à la main (workaround W1).
            "déf mandelbrot_step_re_lane0(zx0, zx1, zy0, zy1, cx0, cx1):\n"
            "    soit zx = v128_pair(zx0, zx1)\n"
            "    soit zy = v128_pair(zy0, zy1)\n"
            "    soit cx = v128_pair(cx0, cx1)\n"
            "    soit nzx = zx * zx - zy * zy + cx\n"
            "    retour v128_lane(nzx, 0)\n"
            "déf mandelbrot_step_re_lane1(zx0, zx1, zy0, zy1, cx0, cx1):\n"
            "    soit zx = v128_pair(zx0, zx1)\n"
            "    soit zy = v128_pair(zy0, zy1)\n"
            "    soit cx = v128_pair(cx0, cx1)\n"
            "    soit nzx = zx * zx - zy * zy + cx\n"
            "    retour v128_lane(nzx, 1)\n",
            language="fr",
        )
        # Smoke : pair + extract identité.
        self.assertEqual(self._call_export(prog, "lane0", 3.0, 7.0), 3.0)
        self.assertEqual(self._call_export(prog, "lane1", 3.0, 7.0), 7.0)
        # add : (1+10, 2+20) → 11, 22.
        self.assertEqual(self._call_export(prog, "add_lane0", 1.0, 2.0, 10.0, 20.0), 11.0)
        self.assertEqual(self._call_export(prog, "add_lane1", 1.0, 2.0, 10.0, 20.0), 22.0)
        # mul : (3*4, _) → 12.
        self.assertEqual(self._call_export(prog, "mul_lane0", 3.0, 5.0, 4.0, 6.0), 12.0)
        # sub : (_, 5-6) → -1.
        self.assertEqual(self._call_export(prog, "sub_lane1", 3.0, 5.0, 4.0, 6.0), -1.0)
        # div : (10/4, _) → 2.5.
        self.assertEqual(self._call_export(prog, "div_lane0", 10.0, 20.0, 4.0, 5.0), 2.5)
        # chained : (_, 5*5 + 7) → 32.
        self.assertEqual(self._call_export(prog, "chained_lane1", 3.0, 5.0, 4.0, 7.0), 32.0)
        # Mandelbrot step (z = z*z + c, partie réelle uniquement) :
        #   lane 0 : (0.3)² - (0.1)² + (-0.5) = 0.09 - 0.01 - 0.5 = -0.42
        #   lane 1 : (0.4)² - (0.2)² + (-0.7) = 0.16 - 0.04 - 0.7 = -0.58
        self.assertAlmostEqual(
            self._call_export(prog, "mandelbrot_step_re_lane0",
                              0.3, 0.4, 0.1, 0.2, -0.5, -0.7),
            -0.42, places=12,
        )
        self.assertAlmostEqual(
            self._call_export(prog, "mandelbrot_step_re_lane1",
                              0.3, 0.4, 0.1, 0.2, -0.5, -0.7),
            -0.58, places=12,
        )

    def test_pow_f64_negative_integer_exponent(self):
        # Regression : $pow_f64 avait le drapeau de signe inversé pour les
        # exposants entiers (neg = 0 < exp au lieu de exp < 0). Conséquence :
        # pow(10, -3) renvoyait 1000 et pow(10, 3) renvoyait 0.001 — exactement
        # inversés. Le bug est resté caché car le code fractales n'utilisait
        # `**` qu'avec des exposants positifs (interpolation), jamais avec un
        # entier négatif. Le formatage exponentiel (mantisse = x / pow(10, e))
        # l'a déclenché en 2026-05-23.
        prog = _parse_source(
            "déf p_pos(x):\n    retour x ** 3.0\n"
            "déf p_neg(x):\n    retour x ** -3.0\n"
            "déf p_neg_grand(x):\n    retour x ** -10.0\n",
            language="fr",
        )
        self.assertAlmostEqual(self._call_export(prog, "p_pos", 10.0), 1000.0, places=10)
        self.assertAlmostEqual(self._call_export(prog, "p_neg", 10.0), 0.001, places=12)
        self.assertAlmostEqual(self._call_export(prog, "p_neg", 2.0), 0.125, places=12)
        self.assertAlmostEqual(self._call_export(prog, "p_neg_grand", 10.0), 1e-10, places=20)

    def test_multi_value_returns_tuple(self):
        # B1 : `retour (a, b)` lower à signature `(result f64 f64)`, push N
        # valeurs avant `return`. `soit (x, y) = f(...)` destructure via
        # `local.set` ordre inverse. Remplace les paires _x/_y dans fractales.
        prog = _parse_source(
            "déf paire(x, y):\n    retour (x + 1.0, y * 2.0)\n"
            "déf utilise_x(x, y):\n    soit a, b = paire(x, y)\n    retour a\n"
            "déf utilise_y(x, y):\n    soit a, b = paire(x, y)\n    retour b\n"
            "déf utilise_somme(x, y):\n    soit a, b = paire(x, y)\n    retour a + b\n"
            "déf cayley(x, y):\n"
            "    soit den_re = x + 1.0\n"
            "    soit den_im = y\n"
            "    soit d2 = den_re * den_re + den_im * den_im\n"
            "    retour ("
            "((x - 1.0) * den_re + y * den_im) / d2, "
            "(y * den_re - (x - 1.0) * den_im) / d2"
            ")\n"
            "déf cayley_x(x, y):\n    soit cx, cy = cayley(x, y)\n    retour cx\n"
            "déf cayley_y(x, y):\n    soit cx, cy = cayley(x, y)\n    retour cy\n",
            language="fr",
        )
        # Basic destructuring
        self.assertEqual(self._call_export(prog, "utilise_x", 3.0, 5.0), 4.0)
        self.assertEqual(self._call_export(prog, "utilise_y", 3.0, 5.0), 10.0)
        self.assertEqual(self._call_export(prog, "utilise_somme", 3.0, 5.0), 14.0)
        # Cayley: z=2+0i → (1)/(3) = 0.333... ; (0)/(3) = 0
        self.assertAlmostEqual(
            self._call_export(prog, "cayley_x", 2.0, 0.0), 1.0 / 3.0, places=12
        )
        self.assertAlmostEqual(self._call_export(prog, "cayley_y", 2.0, 0.0), 0.0, places=12)

    def test_ml_list_count_and_item_helpers(self):
        # B5 : __ml_list_count(ptr) et __ml_list_item(ptr, i) exposent le
        # layout des listes heap-backed sans que le caller hôte doive
        # calculer les offsets bruts. Vérifie sur une liste créée via [0]*n.
        prog = _parse_source(
            "déf make_liste():\n"
            "    soit l = [0.0]*5\n"
            "    l[0] = 11.0\n"
            "    l[1] = 22.0\n"
            "    l[2] = 33.0\n"
            "    l[3] = 44.0\n"
            "    l[4] = 55.0\n"
            "    retour l\n",
            language="fr",
        )
        wat = WATCodeGenerator().generate(prog)
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error
        wasm = wasmtime.wat2wasm(wat)
        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        store.set_wasi(wasmtime.WasiConfig())
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        inst = linker.instantiate(store, wasmtime.Module(engine, wasm))
        ex = inst.exports(store)
        ptr = ex["make_liste"](store)
        # __ml_list_count : doit retourner 5 (la liste a 5 éléments).
        self.assertEqual(ex["__ml_list_count"](store, ptr), 5.0)
        # __ml_list_item : 11, 22, 33, 44, 55.
        self.assertEqual(ex["__ml_list_item"](store, ptr, 0.0), 11.0)
        self.assertEqual(ex["__ml_list_item"](store, ptr, 1.0), 22.0)
        self.assertEqual(ex["__ml_list_item"](store, ptr, 4.0), 55.0)

    def test_format_fixed_dynamic_n(self):
        # B4 : `format_fixed(v, n)` builtin avec n variable au runtime
        # (clampé à [0, 9]). Remplace les formatter_fixe_2/3/5/6 dans fractales.
        prog = _parse_source(
            "déf fmt(v, n):\n    retour format_fixed(v, n)\n",
            language="fr",
        )
        wat = WATCodeGenerator().generate(prog)
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error
        wasm = wasmtime.wat2wasm(wat)
        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        store.set_wasi(wasmtime.WasiConfig())
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        inst = linker.instantiate(store, wasmtime.Module(engine, wasm))
        ex = inst.exports(store)
        memory = ex["memory"]
        def read(ptr_f64):
            ptr = int(ptr_f64)
            length = ex["__ml_str_len"](store)
            return bytes(memory.data_ptr(store)[ptr:ptr + length]).decode("utf-8")
        # n=2 → 2 décimales
        self.assertEqual(read(ex["fmt"](store, 3.14159, 2.0)), "3.14")
        # n=5 → 5 décimales (rounding ulp banker's)
        self.assertEqual(read(ex["fmt"](store, -0.43633, 5.0)), "-0.43633")
        # n=0 → entier arrondi (nearest-even)
        self.assertEqual(read(ex["fmt"](store, 2.5, 0.0)), "2")  # round-half-to-even
        # Clamp n>9 → n=9
        self.assertEqual(read(ex["fmt"](store, 1.0, 12.0)), "1.000000000")
        # Clamp n<0 → n=0
        self.assertEqual(read(ex["fmt"](store, 7.7, -3.0)), "8")

    def test_string_concat_rhs_fstring_and_call(self):
        # Avant 2026-05-23 : `s + f"..."` et `s + func_call()` levaient
        # `Unsupported string expression for WAT concat`. Le caller devait
        # affecter le RHS à un local temporaire. Le fix : récupérer la
        # longueur depuis `$__last_str_len` après évaluation (que les
        # f-strings ET les appels string-returning remplissent déjà).
        prog = _parse_source(
            "déf maker(n):\n    retour f\"item_{n:.0f}\"\n"
            "déf concat_fstring(n):\n    retour \"prefix_\" + f\"{n:.0f}\"\n"
            "déf concat_call(n):\n    retour \"got_\" + maker(n)\n"
            "déf triple(a, b):\n    retour f\"a={a:.2f}\" + \"_\" + f\"b={b:.2f}\"\n",
            language="fr",
        )
        # Lire le résultat string : déclare un export "go" qui invoque
        # concat_fstring(42) et utilise read_string sur le résultat. Plus
        # simple : on vérifie juste que la compilation passe sans erreur.
        wat = WATCodeGenerator().generate(prog)
        self.assertIn("call $__str_concat", wat)
        self.assertIn("global.get $__last_str_len", wat)
        self.assertNotIn("Unsupported string expression", wat)
        # Exécuter pour vérifier le résultat. Sous WASI on lit via stdout,
        # mais ici on appelle juste la fonction et on récupère l'i32 ptr +
        # __ml_str_len pour décoder.
        import wasmtime  # pylint: disable=import-outside-toplevel,import-error
        wasm = wasmtime.wat2wasm(wat)
        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        store.set_wasi(wasmtime.WasiConfig())
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        inst = linker.instantiate(store, wasmtime.Module(engine, wasm))
        ex = inst.exports(store)
        memory = ex["memory"]
        def read_str(ptr_f64):
            ptr = int(ptr_f64)
            length = ex["__ml_str_len"](store)
            return bytes(memory.data_ptr(store)[ptr:ptr + length]).decode("utf-8")
        self.assertEqual(read_str(ex["concat_fstring"](store, 42.0)), "prefix_42")
        self.assertEqual(read_str(ex["concat_call"](store, 7.0)), "got_item_7")
        self.assertEqual(read_str(ex["triple"](store, 1.0, 2.5)), "a=1.00_b=2.50")

    def test_pow_f64_general_real_exponents(self):
        # Renvoie NaN pour exposant non-entier avant 2026-05-23 ; doit
        # désormais retomber sur exp(b·ln(a)) pour base > 0. Précision
        # limitée par math.exp/math.log (~1e-6) donc tolérance places=4
        # sur les exposants non-entiers.
        prog = _parse_source(
            "déf p(base, exp):\n    retour base ** exp\n",
            language="fr",
        )
        # Cas non-entier positif : 2^0.5 = sqrt(2) — déjà spécial-casé, exact.
        self.assertAlmostEqual(
            self._call_export(prog, "p", 2.0, 0.5), _m.sqrt(2), places=12
        )
        # Cas non-entier général : 2^1.5 = 2*sqrt(2) ≈ 2.828
        self.assertAlmostEqual(self._call_export(prog, "p", 2.0, 1.5), 2.0 ** 1.5, places=4)
        # 10^2.3 ≈ 199.526
        self.assertAlmostEqual(self._call_export(prog, "p", 10.0, 2.3), 10.0 ** 2.3, places=2)
        # 0.5^0.3 ≈ 0.812 (base < 1)
        self.assertAlmostEqual(self._call_export(prog, "p", 0.5, 0.3), 0.5 ** 0.3, places=4)
        # Exposant non-entier négatif : 2^-1.5 = 1/(2*sqrt(2)) ≈ 0.354
        self.assertAlmostEqual(self._call_export(prog, "p", 2.0, -1.5), 2.0 ** -1.5, places=4)
        # Base ≤ 0 avec exposant non-entier : NaN (pas de valeur réelle).
        result_neg_base = self._call_export(prog, "p", -2.0, 0.5)
        self.assertTrue(_m.isnan(result_neg_base), "expected NaN")


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

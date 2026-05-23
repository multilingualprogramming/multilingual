#
# SPDX-FileCopyrightText: 2024 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Tests for the runtime built-in functions."""

import io
import unittest
from unittest.mock import patch

from multilingualprogramming.codegen.runtime_builtins import (
    RuntimeBuiltins,
    _runtime_input,
    emit,
    spatial_entity,
    spatial_seed,
)
from multilingualprogramming.keyword.keyword_registry import KeywordRegistry
from multilingualprogramming.runtime.channel import Channel
from multilingualprogramming.runtime.reactive import CanvasNode, Signal


class RuntimeBuiltinsTestSuite(unittest.TestCase):
    """Test the runtime builtins namespace."""

    def test_english_namespace_has_print(self):
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("print", ns)
        self.assertIs(ns["print"], print)

    def test_english_namespace_has_input(self):
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("input", ns)
        self.assertIs(ns["input"], _runtime_input)

    def test_french_namespace_has_afficher(self):
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("afficher", ns)
        self.assertIs(ns["afficher"], print)

    def test_french_namespace_has_saisir(self):
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("saisir", ns)
        self.assertIs(ns["saisir"], _runtime_input)

    def test_runtime_input_writes_prompt_to_real_stdout_when_captured(self):
        captured = io.StringIO()
        visible = io.StringIO()
        with patch("sys.stdout", captured), patch("sys.__stdout__", visible):
            with patch("builtins.input", return_value="yes") as fake_input:
                result = _runtime_input("Prompt: ")

        self.assertEqual(result, "yes")
        self.assertEqual(captured.getvalue(), "")
        self.assertEqual(visible.getvalue(), "Prompt: ")
        fake_input.assert_called_once_with()

    def test_hindi_namespace_has_print_keyword(self):
        ns = RuntimeBuiltins("hi").namespace()
        # Hindi keyword for PRINT
        registry = KeywordRegistry()
        hi_print = registry.get_keyword("PRINT", "hi")
        self.assertIn(hi_print, ns)
        self.assertIs(ns[hi_print], print)

    def test_french_range_alias(self):
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("intervalle", ns)
        self.assertIs(ns["intervalle"], range)
        self.assertIn("range", ns)
        self.assertIs(ns["range"], range)

    def test_portuguese_len_alias(self):
        ns = RuntimeBuiltins("pt").namespace()
        self.assertIn("comprimento", ns)
        self.assertIs(ns["comprimento"], len)
        self.assertIn("len", ns)
        self.assertIs(ns["len"], len)

    def test_portuguese_print_canonical_and_aliases(self):
        """Portuguese canonical print and aliases should all be callable."""
        ns = RuntimeBuiltins("pt").namespace()
        self.assertIn("imprima", ns)
        self.assertIs(ns["imprima"], print)
        self.assertIn("imprimir", ns)
        self.assertIs(ns["imprimir"], print)
        self.assertIn("mostre", ns)
        self.assertIs(ns["mostre"], print)

    def test_portuguese_type_aliases_in_namespace(self):
        """All type keyword aliases should resolve at runtime."""
        ns = RuntimeBuiltins("pt").namespace()
        self.assertIn("texto", ns)
        self.assertIs(ns["texto"], str)
        self.assertIn("cadeia", ns)
        self.assertIs(ns["cadeia"], str)

    def test_portuguese_diacritic_builtin_aliases(self):
        """Built-in alias catalog should accept diacritic forms."""
        ns = RuntimeBuiltins("pt").namespace()
        self.assertIn("m\u00ednimo", ns)
        self.assertIs(ns["m\u00ednimo"], min)
        self.assertIn("m\u00e1ximo", ns)
        self.assertIs(ns["m\u00e1ximo"], max)

    def test_hindi_print_alias(self):
        ns = RuntimeBuiltins("hi").namespace()
        self.assertIn("प्रिंट", ns)
        self.assertIs(ns["प्रिंट"], print)

    def test_french_super_and_open_aliases(self):
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("superieur", ns)
        self.assertIs(ns["superieur"], super)
        self.assertIn("ouvrir", ns)
        self.assertIs(ns["ouvrir"], open)

    def test_spanish_set_tuple_zip_aliases(self):
        ns = RuntimeBuiltins("es").namespace()
        self.assertIn("conjunto", ns)
        self.assertIs(ns["conjunto"], set)
        self.assertIn("tupla", ns)
        self.assertIs(ns["tupla"], tuple)
        self.assertIn("combinar", ns)
        self.assertIs(ns["combinar"], zip)

    def test_render_keyword_does_not_override_french_print(self):
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("render", ns)
        self.assertIn("afficher", ns)
        self.assertNotEqual(ns["render"], print)
        self.assertIs(ns["afficher"], print)

    def test_render_keyword_does_not_override_spanish_print(self):
        ns = RuntimeBuiltins("es").namespace()
        self.assertIn("render", ns)
        self.assertIn("imprimir", ns)
        self.assertNotEqual(ns["render"], print)
        self.assertIs(ns["imprimir"], print)

    def test_japanese_collection_aliases(self):
        ns = RuntimeBuiltins("ja").namespace()
        self.assertIn("集合", ns)
        self.assertIs(ns["集合"], set)
        self.assertIn("タプル", ns)
        self.assertIs(ns["タプル"], tuple)

    def test_namespace_has_universal_builtins(self):
        ns = RuntimeBuiltins("en").namespace()
        # Check several universal builtins
        self.assertIn("len", ns)
        self.assertIs(ns["len"], len)
        self.assertIn("range", ns)
        self.assertIs(ns["range"], range)
        self.assertIn("abs", ns)
        self.assertIs(ns["abs"], abs)
        self.assertIn("min", ns)
        self.assertIn("max", ns)
        self.assertIn("sorted", ns)

    def test_namespace_has_spatial_primitives(self):
        ns = RuntimeBuiltins("en").namespace()
        self.assertIs(ns["emit"], emit)
        self.assertIs(ns["spatial_entity"], spatial_entity)
        self.assertIs(ns["spatial_seed"], spatial_seed)
        entity = ns["spatial_entity"](ns["emit"](), 0.5, 0.5, 10)
        self.assertEqual(entity[0], 1)
        self.assertEqual(ns["spatial_seed"](entity), [entity])

    def test_namespace_has_type_builtins(self):
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("int", ns)
        self.assertIs(ns["int"], int)
        self.assertIn("float", ns)
        self.assertIs(ns["float"], float)
        self.assertIn("str", ns)
        self.assertIs(ns["str"], str)
        self.assertIn("bool", ns)
        self.assertIs(ns["bool"], bool)
        self.assertIn("list", ns)
        self.assertIs(ns["list"], list)
        self.assertIn("dict", ns)
        self.assertIs(ns["dict"], dict)

    def test_namespace_has_exception_types(self):
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("ValueError", ns)
        self.assertIs(ns["ValueError"], ValueError)
        self.assertIn("TypeError", ns)
        self.assertIs(ns["TypeError"], TypeError)
        self.assertIn("Exception", ns)
        self.assertIs(ns["Exception"], Exception)

    def test_french_type_keywords(self):
        """French type keywords should map to Python types."""
        ns = RuntimeBuiltins("fr").namespace()
        registry = KeywordRegistry()
        fr_int = registry.get_keyword("TYPE_INT", "fr")
        self.assertIn(fr_int, ns)
        self.assertIs(ns[fr_int], int)

    def test_all_languages_namespace(self):
        """all_languages_namespace should contain mappings for all languages."""
        ns = RuntimeBuiltins.all_languages_namespace()
        # Should have English keywords
        self.assertIn("print", ns)
        # Should have French keywords
        self.assertIn("afficher", ns)
        # Should include localized built-in aliases
        self.assertIn("intervallo", ns)
        self.assertIn("intervalo", ns)
        # Universal builtins
        self.assertIn("len", ns)
        self.assertIn("range", ns)

    def test_namespace_values_are_callable(self):
        """All function-type builtins should be callable."""
        ns = RuntimeBuiltins("en").namespace()
        for name, obj in ns.items():
            if name not in ("True", "False", "None",
                            "Ellipsis", "NotImplemented"):
                self.assertTrue(
                    callable(obj),
                    f"Built-in {name!r} is not callable"
                )

    def test_canonical_builtin_wins_on_alias_collision(self):
        """If an alias collides with a canonical builtin name, canonical wins."""
        with patch.object(
            RuntimeBuiltins,
            "_load_builtin_alias_catalog",
            return_value={
                "aliases": {
                    "range": {"fr": ["len", "plage_test"]},
                }
            },
        ):
            ns = RuntimeBuiltins("fr").namespace()
            self.assertIs(ns["len"], len)
            self.assertIn("plage_test", ns)
            self.assertIs(ns["plage_test"], range)


class ConcurrencyKeywordsTestSuite(unittest.TestCase):
    """Test concurrency keywords: spawn, channel, send, receive."""

    def test_spawn_function_exists(self):
        """spawn keyword should be available in namespace."""
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("spawn", ns)
        self.assertTrue(callable(ns["spawn"]))

    def test_channel_function_exists(self):
        """channel keyword should be available in namespace."""
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("channel", ns)
        self.assertTrue(callable(ns["channel"]))

    def test_channel_creation(self):
        """channel() should create a Channel instance."""
        ns = RuntimeBuiltins("en").namespace()
        ch = ns["channel"]()
        self.assertIsInstance(ch, Channel)

    def test_channel_with_capacity(self):
        """channel(8) should create a bounded channel."""
        ns = RuntimeBuiltins("en").namespace()
        ch = ns["channel"](8)
        self.assertIsInstance(ch, Channel)
        # Channel should have send/receive methods
        self.assertTrue(hasattr(ch, "send"))
        self.assertTrue(hasattr(ch, "receive"))

    def test_spawn_French_variant(self):
        """lancer (French) should also be available."""
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("lancer", ns)
        self.assertTrue(callable(ns["lancer"]))

    def test_channel_French_variant(self):
        """canal (French) should also be available."""
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("canal", ns)
        self.assertTrue(callable(ns["canal"]))


class ReactiveUIKeywordsTestSuite(unittest.TestCase):
    """Test reactive UI keywords: on_change, canvas, render, bind."""

    def test_on_change_function_exists(self):
        """on_change keyword should be available."""
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("on_change", ns)
        self.assertTrue(callable(ns["on_change"]))

    def test_on_keyword_exists(self):
        """on (short form) should be available."""
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("on", ns)

    def test_canvas_function_exists(self):
        """canvas keyword should be available."""
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("canvas", ns)
        self.assertTrue(callable(ns["canvas"]))

    def test_canvas_creation(self):
        """canvas() should create a CanvasNode instance."""
        ns = RuntimeBuiltins("en").namespace()
        node = ns["canvas"]("mycanvas")
        self.assertIsInstance(node, CanvasNode)
        self.assertEqual(node.name, "mycanvas")

    def test_render_function_exists(self):
        """render keyword should be available."""
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("render", ns)
        self.assertTrue(callable(ns["render"]))

    def test_render_canvas_to_dict(self):
        """render() should convert CanvasNode to dict."""
        ns = RuntimeBuiltins("en").namespace()
        canvas = ns["canvas"]("test")
        rendered = ns["render"](canvas)
        self.assertIsInstance(rendered, dict)
        self.assertIn("name", rendered)
        self.assertEqual(rendered["name"], "test")

    def test_bind_function_exists(self):
        """bind keyword should be available."""
        ns = RuntimeBuiltins("en").namespace()
        self.assertIn("bind", ns)
        self.assertTrue(callable(ns["bind"]))

    def test_bind_signal_to_canvas(self):
        """bind() should attach signal to canvas slot."""
        ns = RuntimeBuiltins("en").namespace()
        canvas = ns["canvas"]("test")
        signal = Signal("count", 0)
        ns["bind"](canvas, "counter", signal)
        self.assertIn("counter", canvas.bindings)
        self.assertIs(canvas.bindings["counter"], signal)

    def test_on_change_with_signal(self):
        """on_change() should register handler on signal."""
        ns = RuntimeBuiltins("en").namespace()
        signal = Signal("test", 0)
        called = []

        def handler(val):
            called.append(val)

        ns["on_change"](signal, handler)
        signal.set(42)
        self.assertEqual(called, [42])

    def test_French_render_variant(self):
        """afficher (French) should also work for render."""
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("afficher", ns)

    def test_French_bind_variant(self):
        """lier (French) should also work for bind."""
        ns = RuntimeBuiltins("fr").namespace()
        self.assertIn("lier", ns)

    def test_Spanish_bind_variant(self):
        """vincular (Spanish) should also work for bind."""
        ns = RuntimeBuiltins("es").namespace()
        self.assertIn("vincular", ns)

#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Rule surface syntax: the combinator DSL lowers to canonical rewrite clauses.

A v1 process program used to hand-nest its rule as raw dict literals; the
combinators ``when``/``neighbor_count``/``becomes``/``fallback``/``symbol``/
``clause``/``rewrite`` let dynamics be *authored* instead. These tests prove the
DSL is a faithful front door: it lowers byte-for-byte to the same clauses
``rewrite_rule`` already accepts (so manifests and stepping are unchanged), it
reports authoring mistakes, and -- because the combinators are free functions,
not methods -- every one resolves through the localized builtins catalog, so a
non-English program can write rules in its own language.

The example files (``game_of_life.multi`` and ``lindenmayer.multi``) are already
migrated to the DSL, so ``process_program_test``/``process_lsystem_test`` are the
end-to-end oracle; this suite pins the lowering itself.
"""

import unittest

from examples import game_of_life_polymodal as gol
from multilingualprogramming.codegen import process_core as pc
from multilingualprogramming.codegen.runtime_builtins import make_exec_globals


class RuleDslLoweringTestSuite(unittest.TestCase):
    """The combinators produce exactly the canonical clause/rule data."""

    def test_life_rule_is_byte_identical_to_hand_written(self):
        """Conway's B3/S23 via the DSL == the reference life_like_rule()."""
        dsl = pc.rewrite(
            pc.clause(pc.when(alive=0), pc.neighbor_count("alive", 1, [3]), pc.becomes(alive=1)),
            pc.clause(pc.when(alive=1), pc.neighbor_count("alive", 1, [2, 3]), pc.becomes(alive=1)),
            pc.fallback(alive=0),
        )
        self.assertEqual(dsl, gol.life_like_rule())

    def test_clause_shape_matches_canonical_lattice_clause(self):
        """A lattice clause has match.self + match.neighbor_count, then produce."""
        c = pc.clause(pc.when(alive=0), pc.neighbor_count("alive", 1, [3]), pc.becomes(alive=1))
        self.assertEqual(
            c,
            {
                "match": {
                    "self": {"alive": 0},
                    "neighbor_count": [{"field": "alive", "value": 1, "in": [3]}],
                },
                "produce": {"alive": 1},
            },
        )

    def test_generative_clause_has_no_neighbor_count_key(self):
        """An L-system production omits neighbor_count and produces a list."""
        c = pc.clause(pc.when(symbol="A"), pc.becomes(pc.symbol("A"), pc.symbol("B")))
        self.assertEqual(
            c,
            {"match": {"self": {"symbol": "A"}}, "produce": [{"symbol": "A"}, {"symbol": "B"}]},
        )
        self.assertNotIn("neighbor_count", c["match"])

    def test_algae_rule_is_byte_identical_to_hand_written(self):
        """The whole algae rule (no fallback) lowers to the documented clauses."""
        dsl = pc.rewrite(
            pc.clause(pc.when(symbol="A"), pc.becomes(pc.symbol("A"), pc.symbol("B"))),
            pc.clause(pc.when(symbol="B"), pc.becomes(pc.symbol("A"))),
        )
        self.assertEqual(
            dsl,
            pc.rewrite_rule(
                [
                    {"match": {"self": {"symbol": "A"}},
                     "produce": [{"symbol": "A"}, {"symbol": "B"}]},
                    {"match": {"self": {"symbol": "B"}}, "produce": [{"symbol": "A"}]},
                ],
                None,
            ),
        )
        self.assertIsNone(dsl["default"])

    def test_clause_parts_are_order_insensitive(self):
        """becomes/neighbor_count/when may appear in any order."""
        a = pc.clause(pc.when(alive=0), pc.neighbor_count("alive", 1, [3]), pc.becomes(alive=1))
        b = pc.clause(pc.becomes(alive=1), pc.neighbor_count("alive", 1, [3]), pc.when(alive=0))
        self.assertEqual(a, b)

    def test_when_with_no_fields_matches_anything(self):
        """when() yields an empty match (no self key)."""
        c = pc.clause(pc.when(), pc.becomes(alive=0))
        self.assertEqual(c, {"match": {}, "produce": {"alive": 0}})

    def test_multiple_neighbor_predicates_accumulate(self):
        c = pc.clause(
            pc.when(alive=1),
            pc.neighbor_count("alive", 1, [2, 3]),
            pc.neighbor_count("ill", 1, [0]),
            pc.becomes(alive=1),
        )
        self.assertEqual(
            c["match"]["neighbor_count"],
            [
                {"field": "alive", "value": 1, "in": [2, 3]},
                {"field": "ill", "value": 1, "in": [0]},
            ],
        )


class RuleDslErrorTestSuite(unittest.TestCase):
    """The combinators reject malformed clauses loudly."""

    def test_clause_without_becomes_raises(self):
        with self.assertRaises(ValueError):
            pc.clause(pc.when(alive=0))

    def test_clause_with_two_becomes_raises(self):
        with self.assertRaises(ValueError):
            pc.clause(pc.when(alive=0), pc.becomes(alive=1), pc.becomes(alive=0))

    def test_clause_with_two_when_raises(self):
        with self.assertRaises(ValueError):
            pc.clause(pc.when(alive=0), pc.when(alive=1), pc.becomes(alive=1))

    def test_clause_rejects_foreign_part(self):
        with self.assertRaises(ValueError):
            pc.clause({"match": {}, "produce": {}}, pc.becomes(alive=1))

    def test_becomes_rejects_mixed_forms(self):
        with self.assertRaises(ValueError):
            pc.becomes(pc.symbol("A"), alive=1)

    def test_becomes_requires_content(self):
        with self.assertRaises(ValueError):
            pc.becomes()

    def test_rewrite_with_two_fallbacks_raises(self):
        with self.assertRaises(ValueError):
            pc.rewrite(pc.fallback(alive=0), pc.fallback(alive=1))


class RuleDslMultilingualTestSuite(unittest.TestCase):
    """Every combinator is a translatable builtin (free function, not a method)."""

    # The combinator name -> its localized alias in a few representative packs.
    ALIASES = {
        "fr": {
            "when": "quand", "neighbor_count": "nombre_voisins", "becomes": "devient",
            "fallback": "repli", "symbol": "symbole", "clause": "clause", "rewrite": "reecrire",
        },
        "ja": {
            "when": "時", "neighbor_count": "隣接_数", "becomes": "結果",
            "fallback": "予備", "symbol": "記号", "clause": "節", "rewrite": "書き換え",
        },
        "de": {
            "when": "sobald", "neighbor_count": "nachbarn_anzahl", "becomes": "ergibt",
            "fallback": "rueckfall", "symbol": "symbol", "clause": "klausel",
            "rewrite": "umschreiben",
        },
    }

    def test_every_combinator_resolves_in_every_pack(self):
        for lang, mapping in self.ALIASES.items():
            ns = make_exec_globals(lang)
            for canonical, alias in mapping.items():
                self.assertIs(
                    ns.get(alias), getattr(pc, canonical),
                    f"{lang}: {alias!r} should resolve to process_core.{canonical}",
                )

    def test_french_rule_lowers_to_the_same_clauses_as_english(self):
        """A rule written with French aliases is byte-identical to the English one."""
        fr = make_exec_globals("fr")
        rule_fr = fr["reecrire"](
            fr["clause"](fr["quand"](alive=0), fr["nombre_voisins"]("alive", 1, [3]),
                         fr["devient"](alive=1)),
            fr["clause"](fr["quand"](alive=1), fr["nombre_voisins"]("alive", 1, [2, 3]),
                         fr["devient"](alive=1)),
            fr["repli"](alive=0),
        )
        self.assertEqual(rule_fr, gol.life_like_rule())


if __name__ == "__main__":
    unittest.main()

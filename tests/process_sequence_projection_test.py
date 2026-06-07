#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Cross-modal equivalence of an animated L-system (generative process).

``process_projection_test`` proves the lattice axis is polymodal across a
whole trajectory. These tests do the same for the generative axis: for every
generation of an L-system the spatial and sonic projections must recover the
*same* word the core reports, so the equivalence is not hollow on a single
frame -- it holds as the string grows. A partial alphabet must be honestly
lossy, never inventing the symbols it omits.
"""

import unittest

from multilingualprogramming.codegen import process_core as pc
from multilingualprogramming.codegen import process_sequence_projection as proj

# Lindenmayer's 1968 algae system: axiom A, A->AB, B->A.
ALGAE = ["A", "AB", "ABA", "ABAAB", "ABAABABA", "ABAABABAABAAB"]


def _algae_core():
    rule = pc.rewrite_rule(
        [
            {"match": {"self": {"symbol": "A"}},
             "produce": [{"symbol": "A"}, {"symbol": "B"}]},
            {"match": {"self": {"symbol": "B"}},
             "produce": [{"symbol": "A"}]},
        ],
        None,
    )
    return pc.build_process_core(
        state={"sequence": [{"symbol": "A"}]},
        topology=pc.sequence_topology(),
        rule=rule,
        schedule=pc.generative_schedule(),
    )


def _word(symbols):
    return "".join(symbols)


class GenerativeEquivalenceTestSuite(unittest.TestCase):
    """Spatial == sonic == core word, for every generation."""

    def test_one_source_of_motion(self):
        # animate must just be the shared stepper -- no private stepping.
        core = _algae_core()
        self.assertEqual(proj.animate(core, 3), pc.run(core, 3))

    def test_alphabet_is_stable_distinct_symbols(self):
        trajectory = proj.animate(_algae_core(), 5)
        self.assertEqual(proj.sequence_alphabet(trajectory), ["A", "B"])

    def test_spatial_and_sonic_recover_the_same_word_per_frame(self):
        trajectory = proj.animate(_algae_core(), 5)
        alphabet = proj.sequence_alphabet(trajectory)
        for index, frame in enumerate(trajectory):
            core_word = pc.sequence_symbols(frame)
            spatial = proj.to_spatial_frame(frame, index, alphabet)
            sonic = proj.to_sonic_frame(frame, index, alphabet)
            recovered_spatial = proj.symbols_from_spatial_frame(spatial)
            recovered_sonic = proj.symbols_from_sonic_frame(sonic)
            self.assertEqual(recovered_spatial, core_word)
            self.assertEqual(recovered_sonic, core_word)
            self.assertEqual(recovered_spatial, recovered_sonic)

    def test_word_actually_grows_to_canonical_generations(self):
        # Equivalence is not hollow on a frozen frame: the projected word
        # follows the canonical algae generations as the structure grows.
        spatial = proj.to_spatial_animation(proj.animate(_algae_core(), 5))
        words = [_word(proj.symbols_from_spatial_frame(f)) for f in spatial]
        self.assertEqual(words, ALGAE)

    def test_default_alphabet_resolves_per_call(self):
        # Without an explicit alphabet a single frame still round-trips
        # (its own symbols form the alphabet).
        frame = proj.animate(_algae_core(), 4)[-1]
        spatial = proj.to_spatial_frame(frame, 0)
        self.assertEqual(
            proj.symbols_from_spatial_frame(spatial), pc.sequence_symbols(frame)
        )


class PartialAlphabetIsLossyTestSuite(unittest.TestCase):
    """A window on the symbol set is honest, contract-declared loss."""

    def test_clipping_drops_only_omitted_symbols(self):
        trajectory = proj.animate(_algae_core(), 4)
        frame = trajectory[-1]
        # Project against an alphabet missing 'B': only 'A's survive.
        spatial = proj.to_spatial_frame(frame, 0, alphabet=["A"])
        recovered = proj.symbols_from_spatial_frame(spatial)
        expected = [s for s in pc.sequence_symbols(frame) if s == "A"]
        self.assertEqual(recovered, expected)
        self.assertTrue(all(s == "A" for s in recovered))

    def test_full_alphabet_declares_exact(self):
        trajectory = proj.animate(_algae_core(), 5)
        caps = proj.projection_capabilities(proj.SEQ_SPATIAL_ANIM_KIND, trajectory)
        self.assertEqual(caps["inverse"], "exact")
        self.assertEqual(caps["lossy"], [])
        self.assertEqual(caps["alphabet"], ["A", "B"])
        # Tier 3: generative is open-ended output.
        self.assertEqual(caps["tier"]["tier"], 3)

    def test_partial_alphabet_declares_partial_and_lossy(self):
        trajectory = proj.animate(_algae_core(), 5)
        caps = proj.projection_capabilities(
            proj.SEQ_SONIC_ANIM_KIND, trajectory, alphabet=["A"]
        )
        self.assertEqual(caps["inverse"], "partial")
        self.assertEqual(caps["lossy"], ["symbols-outside-alphabet"])


class AnimationManifestTestSuite(unittest.TestCase):
    """The bundled manifests carry capabilities, alphabet, and frames."""

    def test_spatial_manifest_shape(self):
        manifest = proj.spatial_animation_manifest(proj.animate(_algae_core(), 5))
        self.assertEqual(manifest["kind"], proj.SEQ_SPATIAL_ANIM_KIND)
        self.assertEqual(manifest["alphabet"], ["A", "B"])
        self.assertEqual(len(manifest["frames"]), 6)
        self.assertEqual(manifest["capabilities"]["inverse"], "exact")

    def test_sonic_manifest_shape(self):
        manifest = proj.sonic_animation_manifest(proj.animate(_algae_core(), 5))
        self.assertEqual(manifest["kind"], proj.SEQ_SONIC_ANIM_KIND)
        self.assertEqual(len(manifest["frames"]), 6)


if __name__ == "__main__":
    unittest.main()

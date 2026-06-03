#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Explicit migration from semantic-core-v0 to semantic-core-v1.

The versioning rule the whole architecture rests on: a ``semantic-core-v0``
manifest must always mean what it meant when emitted, and a future version
may only *enrich* it through an explicit migration that never silently
reinterprets old fields. This module is that migration for v0 -> v1.

The doc states the relationship exactly: "a v0 program is simply a v1
program with an empty rule set and a single-step schedule." So the
migration is a faithful re-housing, not a translation:

- every v0 entity is carried into ``state.loci`` *verbatim* -- same id,
  index, opcode, name, intensity, signal, phase, channel; no coordinates
  are invented and no field is reinterpreted (phase does not become a
  position, intensity does not become an amplitude -- those are projection
  concerns, not core ones);
- the v0 ``relations`` are carried through unchanged;
- the rule set is empty and the schedule is static, so the program is
  classified Tier 0 (a static structure, invertible everywhere) and
  stepping it is a verified no-op;
- a ``migrated_from`` marker records provenance.

Because the rewrite engine short-circuits a static schedule to identity
*before* it touches topology or locus coordinates, a migrated core needs no
lattice and no positions: it steps cleanly as the snapshot it is.
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_core, semantic_core

V0_KIND = semantic_core.CORE_KIND  # "semantic-core-v0"

# A migrated v0 core has no spatial adjacency: its only structure is the v0
# relations, carried through unchanged. The topology is declared inert and
# is never queried, since the static schedule makes stepping identity.
TOPOLOGY_DISCRETE = "discrete"


def migrate_v0_to_v1(core_v0: dict[str, Any]) -> dict[str, Any]:
    """Wrap a ``semantic-core-v0`` manifest as a Tier-0 ``semantic-core-v1``.

    Raises ``ValueError`` if the input is not a v0 manifest. The result is a
    faithful container: every v0 field survives unchanged and stepping it is
    identity. No silent reinterpretation occurs.
    """
    if not isinstance(core_v0, dict) or core_v0.get("kind") != V0_KIND:
        raise ValueError(f"expected a {V0_KIND} manifest to migrate")

    return {
        "kind": process_core.CORE_KIND,
        "version": process_core.CORE_VERSION,
        "source": core_v0.get("source", ""),
        "migrated_from": V0_KIND,
        "state": {
            # v0 entities become loci verbatim -- no coordinates invented.
            "loci": [dict(entity) for entity in core_v0.get("entities", [])],
        },
        "topology": {"kind": TOPOLOGY_DISCRETE},
        "rule": process_core.rewrite_rule(clauses=[], default={}),
        "schedule": process_core.static_schedule(),
        # v0 relations are structural facts; carry them through unchanged.
        "relations": [dict(relation) for relation in core_v0.get("relations", [])],
    }


def is_migrated_v0(core_v1: dict[str, Any]) -> bool:
    """Whether a v1 core was produced by migrating a v0 manifest."""
    return core_v1.get("migrated_from") == V0_KIND


def recover_v0_entities(core_v1: dict[str, Any]) -> list[dict[str, Any]]:
    """Recover the original v0 entities from a migrated core (fidelity check).

    Because migration re-houses entities without reinterpreting them, this
    returns the v0 entity list exactly as it went in -- the basis for the
    round-trip test that proves the migration loses nothing.
    """
    return core_v1["state"]["loci"]

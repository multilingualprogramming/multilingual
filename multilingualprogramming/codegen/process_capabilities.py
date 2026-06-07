#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Expressiveness tiers and capability contracts for semantic-core-v1.

``projection_capabilities`` (v0) lets a *static* projection declare which
fields it preserves or loses. A *process* (v1) adds a second, orthogonal
axis of honesty the research doc calls the **expressiveness frontier**: a
Turing-complete rewrite rule can express systems with no natural sound or
shape, so universality at the representation level coexists with a marked
boundary beyond which perceptual *authoring* degrades. The doc stratifies
this into tiers, each adding power and possibly shrinking the set of
modalities that can invert it:

    Tier 0  static structure                     invertible everywhere (this is v0)
    Tier 1  fixed-population continuous dynamics  fully projectable; per-modality inverse
    Tier 2  synchronous lattice / field rules     projectable; inverse per contract
    Tier 3  generative / open-population rewriting projects as output;
            inverse only in some modalities
    Tier 4  full graph / hypergraph rewriting      mostly view-only / non-invertible

This module makes that ladder machine-checkable: it classifies a v1 core
onto a tier from its axes (not a hand-set label), and builds projection
contracts that carry the tier alongside the v0-style preserves/lossy/inverse
declaration. The classification is descriptive metadata; the equivalence
tests remain the enforcement layer (they now drive expectations off these
declarations -- "this projection claims exact, so the round-trip must be
exact; it claims lossy outside the viewport, so those cells must drop").
"""

from __future__ import annotations

from typing import Any

from multilingualprogramming.codegen import process_core
from multilingualprogramming.codegen.projection_capabilities import capability_contract

# (name, invertibility note) per tier on the doc's ladder.
TIERS: dict[int, tuple[str, str]] = {
    0: ("static structure", "invertible everywhere"),
    1: ("fixed-population continuous dynamics", "fully projectable; per-modality inverse"),
    2: ("synchronous lattice / field rules", "projectable; inverse per contract"),
    3: ("generative / open-population rewriting",
        "projects as output; authoring-invertible only in some modalities"),
    4: ("full graph / hypergraph rewriting", "mostly view-only / non-invertible"),
}


def expressiveness_tier(core: dict[str, Any]) -> int:
    """Classify a v1 core onto the expressiveness ladder from its axes.

    The classification reads the four axes rather than trusting a label:

    - An empty rule set rewrites nothing, so the program is a static
      structure (Tier 0) -- this is exactly "a v0 program is a v1 program
      with an empty rule set and a single-step schedule."
    - A generative schedule (parallel string rewriting, productions longer
      than their match) is generative rewriting (Tier 3) -- an L-system,
      whatever its topology.
    - A non-lattice (graph/hypergraph) topology is general rewriting (Tier 4).
    - Open population means rules create and destroy loci: generative /
      open-population rewriting (Tier 3).
    - A synchronous lattice rule is Tier 2; a fixed-population lattice rule
      under a non-synchronous (continuous) schedule is Tier 1.
    """
    # A static (single-step) schedule never advances, and an empty rule set
    # rewrites nothing: either way the program is a static structure (Tier 0)
    # -- exactly "a v0 program is a v1 program with an empty rule set and a
    # single-step schedule." This is checked first so a migrated v0 core,
    # whose topology is not a lattice, is not misread as Tier 4.
    if core["schedule"].get("kind") == process_core.SCHEDULE_STATIC:
        return 0

    rule = core["rule"]
    if not rule.get("clauses"):
        return 0

    # A generative schedule is the generativity signal (productions may be
    # longer than their match), so an L-system is Tier 3 regardless of its
    # (sequence) topology -- checked before the non-lattice -> Tier 4 rule so
    # it is not misread as arbitrary graph rewriting.
    if core["schedule"].get("kind") == process_core.SCHEDULE_GENERATIVE:
        return 3

    topology = core["topology"]
    if topology.get("kind") != process_core.TOPOLOGY_LATTICE:
        return 4

    population = core["state"].get("population", process_core.POPULATION_FIXED)
    if population == process_core.POPULATION_OPEN:
        return 3

    if core["schedule"].get("kind") == process_core.SCHEDULE_SYNCHRONOUS:
        return 2
    return 1


def tier_contract(core: dict[str, Any]) -> dict[str, Any]:
    """Describe a core's expressiveness tier: number, name, invertibility."""
    tier = expressiveness_tier(core)
    name, invertibility = TIERS[tier]
    return {"tier": tier, "name": name, "invertibility": invertibility}


def projection_contract(
    *,
    projection: str,
    core: dict[str, Any],
    preserves: list[str],
    derived: list[str] | None = None,
    lossy: list[str] | None = None,
    ambiguous: list[str] | None = None,
    inverse: str,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """A v1 projection contract: the v0 declaration plus the program's tier.

    Reuses the v0 ``capability_contract`` shape so v1 contracts validate the
    same way, then annotates the expressiveness tier of the program being
    projected and (optionally) the viewport the contract is scoped to.
    """
    contract = capability_contract(
        projection=projection,
        preserves=preserves,
        derived=derived,
        lossy=lossy,
        ambiguous=ambiguous,
        inverse=inverse,
    )
    contract["tier"] = tier_contract(core)
    if viewport is not None:
        contract["viewport"] = dict(viewport)
    return contract

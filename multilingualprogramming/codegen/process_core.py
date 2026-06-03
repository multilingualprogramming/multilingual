#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Modality-free process core for polymodal computation (semantic-core-v1).

Where ``semantic_core`` (v0) describes a *static structure* -- a flat set
of entities with fixed scalar fields plus derived containment -- this
module describes a *process*: a rule unfolding over time. It is the first
implementation of the ``semantic-core-v1`` direction recorded in
``docs/research/polymodal_computation.md`` ("From structure to process").

Every dynamical / rewriting system decomposes into four orthogonal,
modality-free axes:

- **State**     -- what each locus carries (a per-locus record).
- **Topology**  -- what interacts with what, via one query
  ``neighbors(locus) -> set``.
- **Rule**      -- how a locus changes: a **rewrite** ``match -> produce``,
  expressed as *data* so it projects to every modality just like an
  entity does.
- **Schedule**  -- when rules fire (synchronous / asynchronous / ...).

This module is the **language**, not a program. It deliberately knows
nothing about Game of Life, cellular automata, fractals, or any other
specific system. The one universal primitive it implements is the
**rewrite rule**: a list of ``match -> produce`` clauses evaluated against
each locus and its neighbourhood. Particular systems -- Conway's Life,
Seeds, reaction-diffusion, L-systems, the twelve v0 opcodes -- are
*standard-library rules expressed in this calculus* (see
``examples/game_of_life_polymodal.py``), not branches baked into the core.
That separation is the whole point: a bag of built-in behaviours is never
universal, but a single rewrite primitive plus a library of rule data is.

The single load-bearing requirement (see the research doc and the project
memory) is that the **stepper that advances the tuple lives once, here, in
the modality-free core** and is never re-implemented per modality.
Otherwise two runtimes would evolve the same program differently and
cross-modal equivalence would die the instant the program animates.
Modality runtimes must call this stepper (or a faithful port of it driven
by the same rule data), never hand-write their own ``step()``.

This first step implements the cheapest falsifiable slice of each axis --
``Topology = lattice``, ``Rule = rewrite`` with totalistic neighbour-count
matching, ``Schedule = synchronous`` -- enough to run any outer-totalistic
program (Game of Life among them) through one engine. Each axis dispatches
on a ``kind`` tag, so further kinds (graph topology, positional match
clauses, asynchronous schedules, generative/open-population rewriting)
land as new interpreters without disturbing the ones below.

A ``semantic-core-v0`` program is, in this framing, just a v1 program with
an empty rule set and a single-step schedule; that migration is left for a
later step. Nothing here reinterprets a v0 manifest.
"""

from __future__ import annotations

from typing import Any

CORE_KIND = "semantic-core-v1"
CORE_VERSION = 1

# Topology kinds
TOPOLOGY_LATTICE = "lattice"
# A sequence is a linear order of loci (a string / list of symbols). Its one
# neighbour query returns the immediate predecessor and successor positions.
# Context-free productions ignore neighbours; the query exists so that
# context-sensitive rewriting can land later without a new topology kind.
TOPOLOGY_SEQUENCE = "sequence"

# A lattice may be finite (declared width/height, optionally wrapping) or
# infinite (no extent: every coordinate is a potential locus). Infinite
# lattices are what make open-population programs unbounded -- a glider can
# travel past any pre-declared edge because there is no edge.
LATTICE_EXTENT_INFINITE = "infinite"

# Neighborhood vocabularies for the lattice topology.
NEIGHBORHOOD_MOORE8 = "moore8"  # the 8 surrounding cells
NEIGHBORHOOD_VONNEUMANN4 = "von-neumann4"  # the 4 orthogonal cells

# Population modes (a property of State): is the set of loci fixed for all
# time, or may rules create and destroy loci? Fixed is the default so every
# existing v1 manifest keeps its meaning.
POPULATION_FIXED = "fixed"
POPULATION_OPEN = "open"

_MOORE8_OFFSETS = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0), (1, 0),
    (-1, 1), (0, 1), (1, 1),
)
_VONNEUMANN4_OFFSETS = ((0, -1), (-1, 0), (1, 0), (0, 1))

# Rule kinds
RULE_REWRITE = "rewrite"

# Schedule kinds
SCHEDULE_SYNCHRONOUS = "synchronous"
# A static (single-step) schedule does not advance: stepping is identity.
# This is the schedule a migrated v0 snapshot carries -- "a v0 program is a
# v1 program with an empty rule set and a single-step schedule."
SCHEDULE_STATIC = "static"
# A generative schedule rewrites every locus in parallel and concatenates the
# productions in order. Because a production may be *longer* than the symbol it
# matches, the structure grows -- this is the schedule that makes L-systems,
# fractal strings, and other recursive/generative programs fall out of the one
# rewrite primitive (see the research doc, "generativity/recursion for free").
SCHEDULE_GENERATIVE = "generative"


# --------------------------------------------------------------------------
# Axis constructors -- each returns plain JSON-serializable data, never a
# Python callable, so the whole tuple projects and round-trips through
# modalities exactly as v0 entities do.
# --------------------------------------------------------------------------

def lattice_topology(
    width: int,
    height: int,
    wrap: bool = True,
    neighborhood: str = NEIGHBORHOOD_MOORE8,
) -> dict[str, Any]:
    """Declare a 2D lattice topology.

    ``wrap`` selects a toroidal lattice (edges connect) versus a bounded
    one (out-of-range neighbors simply do not exist). ``neighborhood``
    chooses which loci count as adjacent.
    """
    if width <= 0 or height <= 0:
        raise ValueError("lattice dimensions must be positive")
    if neighborhood not in (NEIGHBORHOOD_MOORE8, NEIGHBORHOOD_VONNEUMANN4):
        raise ValueError(f"unknown neighborhood {neighborhood!r}")
    return {
        "kind": TOPOLOGY_LATTICE,
        "width": int(width),
        "height": int(height),
        "wrap": bool(wrap),
        "neighborhood": neighborhood,
    }


def infinite_lattice_topology(
    neighborhood: str = NEIGHBORHOOD_MOORE8,
) -> dict[str, Any]:
    """Declare an unbounded 2D lattice (every coordinate is reachable).

    There is no width, height, or wrap: ``neighbors`` returns all adjacent
    coordinates unconditionally. Only meaningful with open population --
    the state stores the loci that actually exist, and rules grow or shrink
    that set without ever hitting a wall.
    """
    if neighborhood not in (NEIGHBORHOOD_MOORE8, NEIGHBORHOOD_VONNEUMANN4):
        raise ValueError(f"unknown neighborhood {neighborhood!r}")
    return {
        "kind": TOPOLOGY_LATTICE,
        "extent": LATTICE_EXTENT_INFINITE,
        "neighborhood": neighborhood,
    }


def sequence_topology() -> dict[str, Any]:
    """Declare a linear sequence topology (a string / list of symbols).

    Loci are ordered positions; :func:`neighbors` returns the immediate
    predecessor and successor index. Used with a generative schedule and a
    rewrite rule whose productions replace one symbol with a sequence of
    symbols -- the L-system / string-rewriting shape.
    """
    return {"kind": TOPOLOGY_SEQUENCE}


def rewrite_rule(
    clauses: list[dict[str, Any]],
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Declare a rewrite rule as ordered ``match -> produce`` clauses.

    This is the single universal primitive. Each clause is::

        {
          "match": {
            "self": {<field>: <value>, ...},          # optional
            "neighbor_count": [                         # optional, all must hold
              {"field": <name>, "value": <v>, "in": [<allowed counts>]}
            ]
          },
          "produce": {<field>: <value>, ...}           # partial state update
        }

    For each locus, clauses are tried in order; the first whose ``match``
    holds applies its ``produce`` (merged onto the locus's current record);
    if none match, ``default`` applies. ``self`` constraints test the
    locus's own field values; each ``neighbor_count`` predicate counts how
    many neighbours carry ``field == value`` and requires that tally to be
    in the ``in`` set (totalistic matching).

    The rule is pure data: no automaton-specific logic lives in the core.
    Conway's Life, Seeds, HighLife, and any other outer-totalistic system
    are just different ``clauses`` -- see
    ``examples/game_of_life_polymodal.py`` for how a program is assembled.

    Under a **generative** schedule the same clause shape expresses a
    *production*: ``match`` tests the locus's own ``symbol`` and ``produce``
    is a *list* of records that replaces it (a replacement longer than the
    match grows the structure -- an L-system). A locus that matches no clause
    maps to itself. There ``default`` is unused, so it may be ``None``.

    Richer match predicates (positional neighbours, neighbourhood
    multisets, replacement that creates or destroys loci) are future clause
    shapes that extend this same primitive.
    """
    if not isinstance(clauses, list):
        raise ValueError("clauses must be a list")
    return {
        "kind": RULE_REWRITE,
        "clauses": clauses,
        "default": dict(default) if default is not None else None,
    }


def synchronous_schedule() -> dict[str, Any]:
    """Declare a synchronous schedule.

    Every locus updates at once, reading only the *previous* state. No
    locus observes a half-updated neighbor within a step.
    """
    return {"kind": SCHEDULE_SYNCHRONOUS}


def static_schedule() -> dict[str, Any]:
    """Declare a static (single-step) schedule: the program never advances.

    Stepping a static program is identity -- it is a snapshot, not a
    process. This is what a migrated ``semantic-core-v0`` manifest carries,
    so that "step" on a v0-as-v1 program is a faithful no-op rather than an
    error or a reinterpretation.
    """
    return {"kind": SCHEDULE_STATIC}


def generative_schedule() -> dict[str, Any]:
    """Declare a generative schedule (parallel string rewriting).

    Every locus in the sequence is rewritten at once and the productions are
    concatenated in order, so the sequence may grow without bound. This is
    the schedule an L-system runs under: it pairs with
    :func:`sequence_topology` and a rewrite rule of symbol productions.
    """
    return {"kind": SCHEDULE_GENERATIVE}


def build_process_core(
    state: dict[str, Any],
    topology: dict[str, Any],
    rule: dict[str, Any],
    schedule: dict[str, Any],
    source_path: str = "",
) -> dict[str, Any]:
    """Assemble a modality-free ``semantic-core-v1`` manifest."""
    return {
        "kind": CORE_KIND,
        "version": CORE_VERSION,
        "source": source_path,
        "state": state,
        "topology": topology,
        "rule": rule,
        "schedule": schedule,
    }


# --------------------------------------------------------------------------
# Topology interpreter -- the one query the rest of the core asks of any
# topology: which loci are adjacent to this one?
# --------------------------------------------------------------------------

def neighbors(topology: dict[str, Any], locus: tuple[int, int]) -> list[tuple[int, int]]:
    """Return the loci adjacent to ``locus`` under ``topology``."""
    kind = topology.get("kind")
    if kind == TOPOLOGY_SEQUENCE:
        # A sequence locus is an integer position; its neighbours are the
        # adjacent positions. Context-free productions never ask, but
        # context-sensitive ones will.
        return [locus - 1, locus + 1]
    if kind != TOPOLOGY_LATTICE:
        raise NotImplementedError(f"topology kind {kind!r} not yet supported")
    offsets = (
        _MOORE8_OFFSETS
        if topology.get("neighborhood", NEIGHBORHOOD_MOORE8) == NEIGHBORHOOD_MOORE8
        else _VONNEUMANN4_OFFSETS
    )
    x, y = locus
    if topology.get("extent") == LATTICE_EXTENT_INFINITE:
        # No walls: every adjacent coordinate is a neighbour.
        return [(x + dx, y + dy) for dx, dy in offsets]
    width = topology["width"]
    height = topology["height"]
    wrap = topology.get("wrap", True)
    result: list[tuple[int, int]] = []
    for dx, dy in offsets:
        nx, ny = x + dx, y + dy
        if wrap:
            result.append((nx % width, ny % height))
        elif 0 <= nx < width and 0 <= ny < height:
            result.append((nx, ny))
    return result


# --------------------------------------------------------------------------
# The stepper -- the single, modality-free engine that advances the tuple.
# This is the load-bearing artifact: no modality may re-implement it, and
# it contains no knowledge of any particular system.
# --------------------------------------------------------------------------

def _grid(core: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    """Index the state's loci by coordinate for neighbor lookups."""
    return {
        (rec["locus"][0], rec["locus"][1]): rec
        for rec in core["state"]["loci"]
    }


def _clause_matches(
    rec: dict[str, Any],
    nbs: list[tuple[int, int]],
    grid: dict[tuple[int, int], dict[str, Any]],
    match: dict[str, Any],
) -> bool:
    """Test one clause's ``match`` against a locus and its neighbours."""
    for field, value in match.get("self", {}).items():
        if rec.get(field) != value:
            return False
    for predicate in match.get("neighbor_count", []):
        field = predicate["field"]
        value = predicate["value"]
        allowed = predicate["in"]
        tally = sum(
            1 for nb in nbs if nb in grid and grid[nb].get(field) == value
        )
        if tally not in allowed:
            return False
    return True


def _produce_for(
    rec: dict[str, Any],
    nbs: list[tuple[int, int]],
    grid: dict[tuple[int, int], dict[str, Any]],
    clauses: list[dict[str, Any]],
    default: dict[str, Any],
) -> dict[str, Any]:
    """Return the produce dict for a locus: first matching clause, else default."""
    for clause in clauses:
        if _clause_matches(rec, nbs, grid, clause.get("match", {})):
            return clause["produce"]
    return default


def _is_empty(rec: dict[str, Any], empty: dict[str, Any]) -> bool:
    """Whether a locus carries the empty state (so it does not exist)."""
    return all(rec.get(field) == value for field, value in empty.items())


def _step_fixed(
    core: dict[str, Any],
    topology: dict[str, Any],
    clauses: list[dict[str, Any]],
    default: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fixed population: every declared locus persists, only its state moves."""
    grid = _grid(core)
    next_loci: list[dict[str, Any]] = []
    for rec in core["state"]["loci"]:
        locus = (rec["locus"][0], rec["locus"][1])
        nbs = neighbors(topology, locus)
        next_rec = dict(rec)
        next_rec.update(_produce_for(rec, nbs, grid, clauses, default))
        next_rec["locus"] = [locus[0], locus[1]]
        next_loci.append(next_rec)
    return next_loci


def _step_open(
    core: dict[str, Any],
    topology: dict[str, Any],
    clauses: list[dict[str, Any]],
    default: dict[str, Any],
) -> list[dict[str, Any]]:
    """Open population: rules may create and destroy loci.

    Only non-empty loci are stored. Each step considers the *frontier* --
    every existing locus plus every neighbour of one -- because for a local
    rule those are the only positions whose state can change. A position
    that produces a non-empty state exists next step (a birth if it was
    absent); one that produces the empty state is dropped (a death). This is
    how the same totalistic rule that merely flips ``alive`` under fixed
    population instead grows and prunes the locus set here.
    """
    empty = core["state"]["empty"]
    grid = _grid(core)

    candidates: set[tuple[int, int]] = set(grid)
    for locus in grid:
        candidates.update(neighbors(topology, locus))

    next_loci: list[dict[str, Any]] = []
    for locus in sorted(candidates):
        rec = grid.get(locus, {"locus": [locus[0], locus[1]], **empty})
        nbs = neighbors(topology, locus)
        produced = dict(rec)
        produced.update(_produce_for(rec, nbs, grid, clauses, default))
        produced["locus"] = [locus[0], locus[1]]
        if not _is_empty(produced, empty):
            next_loci.append(produced)
    return next_loci


def _step_generative(core: dict[str, Any]) -> list[dict[str, Any]]:
    """Generative rewriting: rewrite every symbol in parallel, concatenated.

    Each locus is matched against the rule's clauses (``self`` constraints
    only -- context-free); the first matching clause's ``produce`` is a list
    of records that replaces the locus, so a production longer than one
    symbol grows the sequence. A locus matching no clause maps to itself.
    This is the same rewrite primitive as the lattice path; only the
    schedule's reading of ``produce`` (a sequence, not a single state) and of
    population (the sequence length is free) differ.
    """
    rule = core["rule"]
    if rule.get("kind") != RULE_REWRITE:
        raise NotImplementedError(f"rule kind {rule.get('kind')!r} not yet supported")
    clauses = rule["clauses"]
    next_sequence: list[dict[str, Any]] = []
    for rec in core["state"]["sequence"]:
        production: list[dict[str, Any]] | None = None
        for clause in clauses:
            if _clause_matches(rec, [], {}, clause.get("match", {})):
                production = clause["produce"]
                break
        if production is None:
            next_sequence.append(dict(rec))
        else:
            next_sequence.extend(dict(symbol) for symbol in production)
    return next_sequence


def step(core: dict[str, Any]) -> dict[str, Any]:
    """Advance the process core by one step, returning a new core.

    Dispatches on the schedule, rule ``kind``, and population mode. The
    input core is never mutated; the topology, rule, and schedule pass
    through unchanged and only the state advances -- so a trajectory is a
    sequence of full, independently projectable manifests.
    """
    schedule_kind = core["schedule"].get("kind")
    if schedule_kind == SCHEDULE_GENERATIVE:
        next_sequence = _step_generative(core)
        return {**core, "state": {**core["state"], "sequence": next_sequence}}
    if schedule_kind == SCHEDULE_STATIC:
        # A static snapshot does not evolve; stepping is identity. Return a
        # fresh top-level shell so callers never alias the input. Crucially
        # this path touches neither topology nor loci shape, so a migrated v0
        # core (no coordinates, no lattice) steps cleanly as a no-op.
        return {**core, "state": {**core["state"]}}
    if schedule_kind != SCHEDULE_SYNCHRONOUS:
        raise NotImplementedError(f"schedule kind {schedule_kind!r} not yet supported")

    rule = core["rule"]
    if rule.get("kind") != RULE_REWRITE:
        raise NotImplementedError(f"rule kind {rule.get('kind')!r} not yet supported")

    topology = core["topology"]
    clauses = rule["clauses"]
    default = rule["default"]
    population = core["state"].get("population", POPULATION_FIXED)

    if population == POPULATION_FIXED:
        next_loci = _step_fixed(core, topology, clauses, default)
    elif population == POPULATION_OPEN:
        next_loci = _step_open(core, topology, clauses, default)
    else:
        raise NotImplementedError(f"population mode {population!r} not yet supported")

    return {**core, "state": {**core["state"], "loci": next_loci}}


def run(core: dict[str, Any], steps: int) -> list[dict[str, Any]]:
    """Run the stepper ``steps`` times, returning the trajectory.

    The returned list has ``steps + 1`` entries: the initial core followed
    by each successive state. Each entry is a complete ``semantic-core-v1``
    manifest, ready to project to any modality frame-by-frame.
    """
    if steps < 0:
        raise ValueError("steps must be nonnegative")
    trajectory = [core]
    current = core
    for _ in range(steps):
        current = step(current)
        trajectory.append(current)
    return trajectory


def active_cells(core: dict[str, Any], field: str = "alive") -> list[tuple[int, int]]:
    """Return the sorted ``(x, y)`` coordinates whose ``field`` is truthy.

    A generic inspection helper for the simplest modality projections (an
    active cell is a spatial mark / a sounding voice). It names no specific
    system -- the caller chooses which state field counts as "active."
    """
    return sorted(
        (rec["locus"][0], rec["locus"][1])
        for rec in core["state"]["loci"]
        if rec.get(field)
    )


def sequence_symbols(core: dict[str, Any], field: str = "symbol") -> list[Any]:
    """Return the ordered ``field`` values of a sequence-topology core.

    The generic readout for a string-rewriting program: the produced word as
    a list of symbols. Like :func:`active_cells` it names no specific system
    -- the caller chooses which record field carries the symbol.
    """
    return [rec.get(field) for rec in core["state"]["sequence"]]

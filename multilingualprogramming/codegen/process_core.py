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

This started from the cheapest falsifiable slice of each axis --
``Topology = lattice``, ``Rule = rewrite`` with totalistic neighbour-count
matching, ``Schedule = synchronous`` -- enough to run any outer-totalistic
program (Game of Life among them) through one engine. Each axis dispatches
on a ``kind`` tag, so further kinds land as new interpreters without
disturbing the ones below: generative/open-population rewriting (L-systems,
unbounded automata), a sequence topology, an **asynchronous** schedule
(sequential in-place update -- ecological / excitable-media models), and a
**graph** topology (arbitrary adjacency -- networks, contagion, circuits)
have since joined; positional/continuous-time kinds remain open. The lattice
``Rule`` is unchanged across schedules -- only the schedule's reading of it
(parallel vs. sequential vs. generative) differs, and the same rewrite
primitive that flips a lattice cell drives a graph node, the topology alone
deciding what counts as a neighbour.

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
# A graph is an arbitrary adjacency: loci are nodes and an explicit edge set
# answers ``neighbors``. Unlike a lattice, adjacency is not derived from
# position -- a node's neighbours are whoever it is wired to, however far away
# they sit in any spatial embedding -- which is exactly what makes networks
# (social graphs, transport maps, circuits) expressible. A node may still carry
# coordinates, but only as a view hint for projection; the engine reads only
# ``node`` and the edges.
TOPOLOGY_GRAPH = "graph"

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
# A rate rule describes a *continuous* dynamics: instead of a discrete
# match -> produce replacement, it gives each field's rate of change as data.
# The continuous-dt schedule integrates it one explicit-Euler step. This is the
# second general rule kind (it names no system, just as ``rewrite`` does): every
# system is a particular set of coefficients, not an engine branch. A field's
# rate sums four optional contributions -- linear ``self`` coefficients, linear
# ``neighbor_mean`` coefficients, a ``constant`` source/sink, and nonlinear
# ``products`` (monomials over the locus's own fields). Diffusion and linear
# reaction-diffusion use only the first two; the products term reaches the
# nonlinear continuous systems (Gray-Scott, predator-prey, FitzHugh-Nagumo).
RULE_RATE = "rate"

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
# An asynchronous schedule updates loci one at a time in a deterministic scan
# order, each locus reading the *already-updated* state of earlier loci in the
# same sweep (in-place sequential update). This is a genuinely different
# dynamics from synchronous -- sequential and parallel updates of the same rule
# diverge -- so it is the schedule that lets ecological / excitable-media models
# (predators reacting to neighbours that already moved this tick) be expressed.
# The order is fixed (sorted loci) so the result is reproducible and identical
# in every runtime: a different order is a different schedule, not randomness.
SCHEDULE_ASYNCHRONOUS = "asynchronous"
# A continuous-dt schedule advances continuous-time dynamics by one explicit
# (forward) Euler step of size ``dt``: every locus integrates ``next = current +
# dt * rate`` from the *previous* frame (synchronous reading, like a Jacobi
# sweep), where the rate comes from a :data:`RULE_RATE` rule. Where the
# asynchronous schedule is the *discrete* sequential update, this is the genuine
# continuous-time axis -- the schedule under which fields diffuse and relax
# (Tier 1, fixed-population continuous dynamics). The step size is part of the
# schedule (a different ``dt`` is a different schedule, not randomness), and
# forward Euler is the cheapest falsifiable integrator -- higher-order
# integrators (RK4, ...) are future schedule kinds, not engine branches here.
SCHEDULE_CONTINUOUS = "continuous-dt"


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


def graph_topology(
    edges: list[list[Any]],
    directed: bool = False,
) -> dict[str, Any]:
    """Declare a graph topology from an explicit edge set.

    Loci are nodes; each is identified by a ``node`` value in its state record
    (any hashable -- an int or a string). ``edges`` is a list of ``[a, b]``
    pairs; :func:`neighbors` answers adjacency from them. By default the graph
    is undirected (an edge ``[a, b]`` makes ``a`` and ``b`` mutual neighbours);
    set ``directed`` to treat ``[a, b]`` as ``a -> b`` only.

    This is the topology that decouples *interaction* from *position*: a node's
    neighbours are whoever it is wired to, not whoever sits nearby, so a rule
    spreads along the wiring (a contagion across a social graph, a signal across
    a circuit) rather than across a grid. Nodes may still carry a ``locus``
    coordinate, but only as a hint for spatial projection -- the engine reads
    only ``node`` and these edges.
    """
    return {
        "kind": TOPOLOGY_GRAPH,
        "edges": [[a, b] for a, b in edges],
        "directed": bool(directed),
    }


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


def rate_rule(rates: dict[str, Any]) -> dict[str, Any]:
    """Declare a continuous rate rule: each field's time-derivative as data.

    The continuous counterpart of :func:`rewrite_rule`. ``rates`` maps a state
    field to a description of its rate of change, a sum of four optional terms::

        {
          "u": {
            "self": {"u": -0.2},               # linear, on the locus's own fields
            "neighbor_mean": {"u": 0.2},        # linear, on the mean over neighbours
            "constant": 0.04,                   # a scalar source/sink (optional)
            "products": [                       # nonlinear monomials (optional)
              {"coeff": -1.0, "factors": ["u", "v", "v"]}  # -u*v*v
            ]
          }
        }

    For each locus the rate of a field is the sum of ``self`` coefficients times
    the locus's own field values, plus ``neighbor_mean`` coefficients times the
    mean of that field over the locus's existing neighbours, plus the
    ``constant`` source/sink, plus each ``products`` monomial (its ``coeff``
    times the product of the locus's own ``factors`` values, factors repeating
    to raise a power). The :data:`SCHEDULE_CONTINUOUS` schedule integrates one
    explicit-Euler step, ``next[field] = field + dt * rate``.

    The first two terms give diffusion (``du/dt = D*(mean_nbr(u) - u)`` is
    ``self={"u": -D}, neighbor_mean={"u": D}``), linear decay, and linear
    reaction-diffusion. ``constant`` and ``products`` reach the nonlinear
    continuous systems -- Gray-Scott, Lotka-Volterra predator-prey,
    FitzHugh-Nagumo -- all as pure data, no system named in the engine. A rule
    that omits ``constant`` and ``products`` integrates exactly as before they
    were added.
    """
    if not isinstance(rates, dict):
        raise ValueError("rates must be a dict of field -> contributions")
    return {
        "kind": RULE_RATE,
        "rates": {field: dict(terms) for field, terms in rates.items()},
    }


# --------------------------------------------------------------------------
# Rule surface syntax -- a small set of combinators that *assemble* the
# canonical clause shape above, so a program can author its dynamics
# declaratively instead of hand-nesting raw dicts. These are pure data
# builders: ``rewrite`` ultimately delegates to :func:`rewrite_rule`, so a
# rule written with the combinators is byte-identical to the same rule
# written as literals. They live here, beside the primitive they lower to,
# but -- like ``rewrite_rule`` itself -- they name no specific system; a
# program still supplies its own fields, counts, and symbols.
#
# They are deliberately *free functions* rather than fluent methods so that
# every one is a plain identifier the multilingual builtins catalog can
# translate (method names would stay English). A clause reads:
#
#     clause(when(alive=0), neighbor_count("alive", 1, [3]), becomes(alive=1))
#
# The combinator names deliberately avoid control-flow vocabulary: the natural
# translation of "produce" is "yield" and of an "otherwise"/"default" branch is
# "else" in most languages, which are reserved keywords -- so the replacement is
# ``becomes`` and the default is ``fallback`` (the totalistic predicate is
# ``neighbor_count``, which also sidesteps the internal ``neighbors`` topology
# query). A tiny private ``_dsl`` tag distinguishes the intermediate parts; the
# finished ``clause``/``rewrite`` output carries no such tag -- it is the same
# plain data ``rewrite_rule`` already accepts.
# --------------------------------------------------------------------------

_DSL_TAG = "_dsl"


def when(**fields: Any) -> dict[str, Any]:
    """A clause's ``match.self`` constraints (the locus's own field values).

    ``when(alive=0)`` matches a locus whose ``alive`` field is ``0``;
    ``when()`` (no fields) matches any locus. Pass it to :func:`clause`.
    """
    return {_DSL_TAG: "self", "fields": dict(fields)}


def neighbor_count(field: str, value: Any, counts: list[int]) -> dict[str, Any]:
    """One totalistic neighbour predicate for a clause's ``match``.

    Requires that the number of neighbours whose ``field == value`` is one
    of ``counts``. For example ``neighbor_count("alive", 1, [3])`` holds when
    exactly three neighbours are alive. A clause may carry several.
    """
    return {
        _DSL_TAG: "neighbor_count",
        "predicate": {"field": field, "value": value, "in": list(counts)},
    }


def becomes(*records: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """A clause's replacement: what the matched locus becomes.

    Two mutually exclusive forms:

    - keyword fields -- ``becomes(alive=1)`` -- a partial-state update,
      merged onto the locus (the lattice / totalistic form);
    - positional records -- ``becomes(symbol("A"), symbol("B"))`` -- a
      *sequence* of records that replaces the matched locus (the generative
      / L-system form, where a longer replacement grows the structure).

    Exactly one form must be given.
    """
    if records and fields:
        raise ValueError("becomes takes either record positions or keyword fields, not both")
    if records:
        return {_DSL_TAG: "produce", "value": [dict(record) for record in records]}
    if fields:
        return {_DSL_TAG: "produce", "value": dict(fields)}
    raise ValueError("becomes needs a state update (keywords) or records (positions)")


def symbol(name: Any) -> dict[str, Any]:
    """A sequence record carrying a single ``symbol`` -- e.g. ``symbol("A")``.

    The atom of generative rewriting: axioms and productions are built from
    these. ``becomes(symbol("A"), symbol("B"))`` is the production ``-> A B``.
    """
    return {"symbol": name}


def fallback(**fields: Any) -> dict[str, Any]:
    """The rule's default replacement, used when no clause matches a locus.

    ``fallback(alive=0)`` is the dead-by-default of Conway's Life. Pass it
    among the clauses of :func:`rewrite`; omit it (e.g. for a generative
    L-system) to leave unmatched loci unchanged. It is a combinator rather
    than a keyword argument so that, like every other part, it is a plain
    identifier the multilingual builtins catalog can translate.
    """
    return {_DSL_TAG: "default", "value": dict(fields)}


def chance(probability: float, salt: int = 0) -> dict[str, Any]:
    """A clause predicate that fires only with a given probability.

    ``chance(0.1)`` makes a clause match a tenth of the time -- the stochastic
    counterpart of the deterministic ``when``/``neighbor_count`` predicates. The
    randomness is a *deterministic* function of the locus coordinate, the step
    index, and ``salt`` (so two clauses in one rule can roll independently): see
    :func:`_hash01`. It is therefore reproducible and byte-identical across the
    Python and JS runtimes -- no PRNG state, no seed plumbing. This is what
    lets a rule express stochastic growth (Eden clusters, percolation, noisy
    cellular automata) while the engine stays pure and the trajectory stays a
    deterministic function of the manifest. Pass it to :func:`clause`.
    """
    return {_DSL_TAG: "chance", "probability": probability, "salt": salt}


def clause(*parts: dict[str, Any]) -> dict[str, Any]:
    """Assemble one canonical ``match -> produce`` clause from its parts.

    Accepts, in any order, at most one :func:`when`, zero or more
    :func:`neighbor_count`, and exactly one :func:`becomes`. The resulting
    dict is exactly what :func:`rewrite_rule` expects -- ``self`` and
    ``neighbor_count`` keys are omitted when empty, so the output matches a
    hand-written clause byte-for-byte.
    """
    self_fields: dict[str, Any] | None = None
    predicates: list[dict[str, Any]] = []
    chance_spec: dict[str, Any] | None = None
    produce_value: Any = None
    have_produce = False
    for part in parts:
        tag = part.get(_DSL_TAG) if isinstance(part, dict) else None
        if tag == "self":
            if self_fields is not None:
                raise ValueError("clause takes at most one when(...)")
            self_fields = part["fields"]
        elif tag == "neighbor_count":
            predicates.append(part["predicate"])
        elif tag == "chance":
            if chance_spec is not None:
                raise ValueError("clause takes at most one chance(...)")
            chance_spec = {"p": part["probability"], "salt": part["salt"]}
        elif tag == "produce":
            if have_produce:
                raise ValueError("clause takes exactly one becomes(...)")
            produce_value = part["value"]
            have_produce = True
        else:
            raise ValueError(f"clause parts must be when/neighbor_count/chance/becomes, got {part!r}")
    if not have_produce:
        raise ValueError("clause needs a becomes(...)")
    match: dict[str, Any] = {}
    if self_fields:
        match["self"] = self_fields
    if predicates:
        match["neighbor_count"] = predicates
    if chance_spec is not None:
        match["chance"] = chance_spec
    return {"match": match, "produce": produce_value}


def rewrite(*parts: dict[str, Any]) -> dict[str, Any]:
    """Build a rewrite rule from :func:`clause` and :func:`fallback` parts.

    ``rewrite(clause(...), clause(...), fallback(alive=0))`` is exactly
    ``rewrite_rule([clause(...), clause(...)], default={"alive": 0})`` -- a
    thin, readable front door onto the one universal primitive. The single
    optional :func:`fallback` part, in any position, supplies the default;
    every other part is a clause. Omit ``fallback`` for rules (such as
    L-systems) whose unmatched loci are left unchanged.
    """
    clauses: list[dict[str, Any]] = []
    default: dict[str, Any] | None = None
    for part in parts:
        if isinstance(part, dict) and part.get(_DSL_TAG) == "default":
            if default is not None:
                raise ValueError("rewrite takes at most one fallback(...)")
            default = part["value"]
        else:
            clauses.append(part)
    return rewrite_rule(clauses, default)


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


def asynchronous_schedule() -> dict[str, Any]:
    """Declare an asynchronous schedule (sequential in-place update).

    Loci are visited one at a time in a deterministic scan order, and each
    sees the *already-updated* state of the loci visited before it this
    sweep. Unlike :func:`synchronous_schedule` -- where every locus reads the
    previous frame -- here an update propagates within a single step, so the
    same rule produces a different trajectory. This is the schedule for
    sequential ecological models (an organism reacts to neighbours that have
    already acted this tick). The scan order is fixed, so the result is
    reproducible and identical across runtimes.
    """
    return {"kind": SCHEDULE_ASYNCHRONOUS}


def continuous_schedule(dt: float = 1.0) -> dict[str, Any]:
    """Declare a continuous-dt schedule with explicit-Euler step size ``dt``.

    Advances continuous-time dynamics by one forward-Euler step: every locus
    integrates ``next = current + dt * rate`` from the previous frame, with the
    rate supplied by a :func:`rate_rule`. The step size is part of the schedule,
    so two cores differing only in ``dt`` are different programs. Pairs with a
    lattice topology and a fixed population (continuous open-population dynamics
    are not yet specified).
    """
    if dt <= 0:
        raise ValueError("dt must be positive")
    return {"kind": SCHEDULE_CONTINUOUS, "dt": float(dt)}


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

def _graph_adjacency(topology: dict[str, Any]) -> dict[Any, list[Any]]:
    """Build an adjacency map from a graph topology's edge set.

    Undirected edges contribute both directions; insertion order is preserved
    and duplicates dropped, so the neighbour list is deterministic. (Counting
    is totalistic, so neighbour *order* never affects a rule -- determinism here
    is only so two runtimes agree on the set.)
    """
    adjacency: dict[Any, list[Any]] = {}
    directed = topology.get("directed", False)

    def link(a: Any, b: Any) -> None:
        bucket = adjacency.setdefault(a, [])
        if b not in bucket:
            bucket.append(b)

    for source, target in topology["edges"]:
        link(source, target)
        if not directed:
            link(target, source)
    return adjacency


def neighbors(topology: dict[str, Any], locus: Any) -> list[Any]:
    """Return the loci adjacent to ``locus`` under ``topology``.

    ``locus`` is whatever identifies a locus for the topology: an ``(x, y)``
    coordinate for a lattice, an integer position for a sequence, a ``node``
    value for a graph. The returned neighbours are of the same kind, so the
    stepper can look each up in its grid.
    """
    kind = topology.get("kind")
    if kind == TOPOLOGY_SEQUENCE:
        # A sequence locus is an integer position; its neighbours are the
        # adjacent positions. Context-free productions never ask, but
        # context-sensitive ones will.
        return [locus - 1, locus + 1]
    if kind == TOPOLOGY_GRAPH:
        # A graph locus is a node id; its neighbours are whoever the edges wire
        # it to. Adjacency is rebuilt per call to keep the topology pure data
        # (no cached object on the dict); graphs here are small.
        return _graph_adjacency(topology).get(locus, [])
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

def _locus_key(rec: dict[str, Any], topology: dict[str, Any]) -> Any:
    """The key under which a locus is indexed and looked up as a neighbour.

    A lattice / sequence locus is positional, so its key is its coordinate; a
    graph locus is its ``node`` id. The key is exactly what :func:`neighbors`
    returns for that topology, so neighbour lookups in the grid line up.
    """
    if topology.get("kind") == TOPOLOGY_GRAPH:
        return rec["node"]
    return (rec["locus"][0], rec["locus"][1])


def _grid(core: dict[str, Any]) -> dict[Any, dict[str, Any]]:
    """Index the state's loci by their topology key for neighbor lookups."""
    topology = core["topology"]
    return {_locus_key(rec, topology): rec for rec in core["state"]["loci"]}


def _hash01(x: int, y: int, step: int, salt: int) -> float:
    """A deterministic pseudo-random value in [0, 1) keyed by (x, y, step, salt).

    The backbone of the stochastic :func:`chance` predicate. It must produce the
    same float in CPython and the JS port, so it is built entirely from exact
    32-bit integer arithmetic (a MurmurHash3-style mix and finalizer): every
    multiply is taken mod 2**32 (the JS port uses ``Math.imul`` / ``>>> 0`` to
    match), every shift is on a non-negative 32-bit word, and the final divide by
    2**32 is the one floating-point op -- exact and identical on both sides. No
    PRNG state lives anywhere; randomness is a pure function of the coordinates
    and time, which is exactly what keeps a stochastic trajectory reproducible.
    """
    mask = 0xFFFFFFFF
    h = (x & mask) * 0x9E3779B1 & mask
    h = (h ^ ((y + 0x85EBCA77) & mask)) & mask
    h = (h * 0xC2B2AE3D) & mask
    h = (h ^ ((step & mask) * 0x27D4EB2F & mask)) & mask
    h = (h ^ (salt & mask)) & mask
    # MurmurHash3 fmix32 finalizer -- avalanche the bits.
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & mask
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & mask
    h ^= h >> 16
    return h / 4294967296.0


def _clause_matches(
    rec: dict[str, Any],
    nbs: list[tuple[int, int]],
    grid: dict[tuple[int, int], dict[str, Any]],
    match: dict[str, Any],
    step_index: int = 0,
) -> bool:
    """Test one clause's ``match`` against a locus and its neighbours.

    ``step_index`` is the index of the step being computed; it feeds the
    optional stochastic ``chance`` predicate so randomness varies over time.
    """
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
    chance_spec = match.get("chance")
    if chance_spec is not None and "locus" in rec:
        roll = _hash01(rec["locus"][0], rec["locus"][1], step_index, chance_spec["salt"])
        if roll >= chance_spec["p"]:
            return False
    return True


def _produce_for(
    rec: dict[str, Any],
    nbs: list[tuple[int, int]],
    grid: dict[tuple[int, int], dict[str, Any]],
    clauses: list[dict[str, Any]],
    default: dict[str, Any] | None,
    step_index: int = 0,
) -> dict[str, Any] | None:
    """Return the produce dict for a locus: first matching clause, else default.

    ``default`` may be ``None`` (a rule with no ``fallback``), in which case a
    locus matching no clause produces ``None`` -- read by the steppers below as
    "leave this locus unchanged." That identity-on-no-match is what lets a rule
    rewrite only the loci it has something to say about (a cyclic ecology rule
    advances a cell only when its successor surrounds it; every other cell
    stays put), without inventing a catch-all state for the rest.
    """
    for rule_clause in clauses:
        if _clause_matches(rec, nbs, grid, rule_clause.get("match", {}), step_index):
            return rule_clause["produce"]
    return default


def _is_empty(rec: dict[str, Any], empty: dict[str, Any]) -> bool:
    """Whether a locus carries the empty state (so it does not exist)."""
    return all(rec.get(field) == value for field, value in empty.items())


def _step_fixed(
    core: dict[str, Any],
    topology: dict[str, Any],
    clauses: list[dict[str, Any]],
    default: dict[str, Any],
    step_index: int = 0,
) -> list[dict[str, Any]]:
    """Fixed population: every declared locus persists, only its state moves."""
    grid = _grid(core)
    is_lattice = topology.get("kind") == TOPOLOGY_LATTICE
    next_loci: list[dict[str, Any]] = []
    for rec in core["state"]["loci"]:
        key = _locus_key(rec, topology)
        nbs = neighbors(topology, key)
        next_rec = dict(rec)
        produce = _produce_for(rec, nbs, grid, clauses, default, step_index)
        if produce is not None:
            next_rec.update(produce)
        if is_lattice:
            # Normalize the coordinate to a list (a graph node keeps whatever
            # ``locus`` view hint it carried, untouched).
            next_rec["locus"] = [key[0], key[1]]
        next_loci.append(next_rec)
    return next_loci


def _step_async(
    core: dict[str, Any],
    topology: dict[str, Any],
    clauses: list[dict[str, Any]],
    default: dict[str, Any] | None,
    step_index: int = 0,
) -> list[dict[str, Any]]:
    """Asynchronous population: sequential in-place update in a fixed order.

    Loci are visited in sorted coordinate order; each is rewritten against the
    *current* grid, which already holds the new state of every locus visited
    earlier this sweep. The input records are never mutated -- an updated locus
    is a fresh dict written back into the working grid -- so neighbours see new
    values while ``core`` stays untouched. The emitted list keeps the original
    loci order so the manifest's ``loci`` sequence is stable frame to frame.
    """
    grid = _grid(core)
    is_lattice = topology.get("kind") == TOPOLOGY_LATTICE
    for key in sorted(grid):
        rec = grid[key]
        nbs = neighbors(topology, key)
        produce = _produce_for(rec, nbs, grid, clauses, default, step_index)
        if produce is None:
            continue
        updated = dict(rec)
        updated.update(produce)
        if is_lattice:
            updated["locus"] = [key[0], key[1]]
        grid[key] = updated
    # Fresh copies so an unchanged locus never aliases the input record.
    return [dict(grid[_locus_key(rec, topology)]) for rec in core["state"]["loci"]]


def _rate_for(
    rec: dict[str, Any],
    nbs: list[Any],
    grid: dict[Any, dict[str, Any]],
    rates: dict[str, Any],
) -> dict[str, float]:
    """Evaluate a rate rule at one locus: each field's time-derivative.

    A field's rate is the sum of four optional contributions, evaluated in this
    fixed order so the floating-point result is reproducible across ports:

    1. ``self``          -- ``sum(coeff * own_field)`` (linear, own values);
    2. ``neighbor_mean`` -- ``sum(coeff * mean_over_neighbours(field))``;
    3. ``constant``      -- a scalar source/sink term;
    4. ``products``      -- nonlinear monomials over the locus's own fields,
       each ``{"coeff": c, "factors": [f, ...]}`` contributing
       ``c * own[f0] * own[f1] * ...`` (factors repeat to raise a power).

    The neighbour mean is taken over the locus's *existing* neighbours (so it is
    well-defined at a bounded lattice's edge); with no neighbours that term is
    zero. Neighbours are summed in :func:`neighbors` order, which is identical in
    every runtime. ``constant`` and ``products`` are appended only when present,
    so a rule that uses neither integrates byte-identically to before they
    existed.
    """
    present = [grid[nb] for nb in nbs if nb in grid]
    count = len(present)
    out: dict[str, float] = {}
    for field, terms in rates.items():
        rate = 0.0
        for src, coeff in terms.get("self", {}).items():
            rate += coeff * rec.get(src, 0)
        neighbor_mean = terms.get("neighbor_mean")
        if neighbor_mean and count:
            for src, coeff in neighbor_mean.items():
                # An explicit left-fold, NOT the builtin ``sum`` -- CPython's
                # ``sum`` uses compensated (Neumaier) float summation, which
                # would diverge by ~1 ULP from the JS port's naive loop and
                # break the byte-identical cross-runtime guarantee.
                total = 0.0
                for p in present:
                    total += p.get(src, 0)
                rate += coeff * (total / count)
        # A constant source/sink (e.g. Gray-Scott's feed F). Only added when the
        # key is present so existing linear rules are bit-for-bit unchanged
        # (``rate + 0.0`` would flip a -0.0 result and drift a manifest).
        if "constant" in terms:
            rate += terms["constant"]
        # Nonlinear monomials over the locus's own fields -- the reaction terms
        # diffusion and decay cannot express (Gray-Scott's -u·v², predator-prey
        # coupling). Evaluated as a left-fold in factor order, identical in JS.
        for monomial in terms.get("products", ()):
            term = monomial.get("coeff", 1.0)
            for factor in monomial.get("factors", ()):
                term *= rec.get(factor, 0)
            rate += term
        out[field] = rate
    return out


def _step_continuous(
    core: dict[str, Any],
    topology: dict[str, Any],
    rates: dict[str, Any],
    dt: float,
) -> list[dict[str, Any]]:
    """Continuous dynamics: one explicit-Euler step ``next = current + dt*rate``.

    Synchronous reading -- every locus integrates from the *previous* frame, so
    a step is order-independent (a Jacobi sweep). The input is never mutated.
    """
    grid = _grid(core)
    is_lattice = topology.get("kind") == TOPOLOGY_LATTICE
    next_loci: list[dict[str, Any]] = []
    for rec in core["state"]["loci"]:
        key = _locus_key(rec, topology)
        nbs = neighbors(topology, key)
        rate = _rate_for(rec, nbs, grid, rates)
        next_rec = dict(rec)
        for field, value in rate.items():
            next_rec[field] = rec.get(field, 0) + dt * value
        if is_lattice:
            next_rec["locus"] = [key[0], key[1]]
        next_loci.append(next_rec)
    return next_loci


def _step_open(
    core: dict[str, Any],
    topology: dict[str, Any],
    clauses: list[dict[str, Any]],
    default: dict[str, Any],
    step_index: int = 0,
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
        produce = _produce_for(rec, nbs, grid, clauses, default, step_index)
        if produce is not None:
            produced.update(produce)
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
        for rule_clause in clauses:
            if _clause_matches(rec, [], {}, rule_clause.get("match", {})):
                production = rule_clause["produce"]
                break
        if production is None:
            next_sequence.append(dict(rec))
        else:
            next_sequence.extend(dict(symbol) for symbol in production)
    return next_sequence


def step(core: dict[str, Any], step_index: int = 0) -> dict[str, Any]:
    """Advance the process core by one step, returning a new core.

    Dispatches on the schedule, rule ``kind``, and population mode. The
    input core is never mutated; the topology, rule, and schedule pass
    through unchanged and only the state advances -- so a trajectory is a
    sequence of full, independently projectable manifests.

    ``step_index`` is the 0-based index of this step within a run; it is
    threaded to the stochastic ``chance`` predicate so a rule's randomness
    varies from one step to the next. A deterministic rule ignores it, so
    every existing program steps exactly as before.
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
    if schedule_kind == SCHEDULE_CONTINUOUS:
        # Continuous-time dynamics: integrate a rate rule one Euler step. A
        # different rule kind (rate, not rewrite) and a fixed population only.
        rule = core["rule"]
        if rule.get("kind") != RULE_RATE:
            raise NotImplementedError(
                f"continuous-dt schedule needs a rate rule, got {rule.get('kind')!r}"
            )
        population = core["state"].get("population", POPULATION_FIXED)
        if population != POPULATION_FIXED:
            raise NotImplementedError(
                f"continuous-dt schedule with population {population!r} not yet supported"
            )
        next_loci = _step_continuous(
            core, core["topology"], rule["rates"], core["schedule"]["dt"]
        )
        return {**core, "state": {**core["state"], "loci": next_loci}}
    if schedule_kind not in (SCHEDULE_SYNCHRONOUS, SCHEDULE_ASYNCHRONOUS):
        raise NotImplementedError(f"schedule kind {schedule_kind!r} not yet supported")

    rule = core["rule"]
    if rule.get("kind") != RULE_REWRITE:
        raise NotImplementedError(f"rule kind {rule.get('kind')!r} not yet supported")

    topology = core["topology"]
    clauses = rule["clauses"]
    default = rule["default"]
    population = core["state"].get("population", POPULATION_FIXED)

    if schedule_kind == SCHEDULE_ASYNCHRONOUS:
        # Sequential update is defined on a fixed population (the loci a sweep
        # walks); open-population async is not yet specified.
        if population != POPULATION_FIXED:
            raise NotImplementedError(
                f"asynchronous schedule with population {population!r} not yet supported"
            )
        next_loci = _step_async(core, topology, clauses, default, step_index)
    elif population == POPULATION_FIXED:
        next_loci = _step_fixed(core, topology, clauses, default, step_index)
    elif population == POPULATION_OPEN:
        # Open population grows and prunes loci by coordinate frontier, so it is
        # defined on a lattice; an open graph would mean creating and destroying
        # nodes and edges (full graph rewriting), which is not yet specified.
        if topology.get("kind") != TOPOLOGY_LATTICE:
            raise NotImplementedError(
                f"open population with topology {topology.get('kind')!r} not yet supported"
            )
        next_loci = _step_open(core, topology, clauses, default, step_index)
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
    for i in range(steps):
        current = step(current, i)
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


def field_cells(core: dict[str, Any], field: str = "state") -> list[tuple[int, int, Any]]:
    """Return sorted ``(x, y, value)`` triples of each locus's ``field``.

    Where :func:`active_cells` collapses a lattice to a boolean mask (a cell is
    on or off), this preserves the *value* each locus carries -- the readout a
    multi-state field (a several-species ecology, a reaction-diffusion lattice)
    needs to project losslessly. It still names no specific system: the caller
    chooses which field is the cell's value.
    """
    return sorted(
        (rec["locus"][0], rec["locus"][1], rec.get(field))
        for rec in core["state"]["loci"]
    )


def node_cells(core: dict[str, Any], field: str = "state") -> list[tuple[Any, Any]]:
    """Return sorted ``(node, value)`` pairs of a graph-topology core.

    The generic readout for a network program: each node's identity and the
    value its ``field`` carries, sorted by node so the readout is stable frame
    to frame. The graph analogue of :func:`field_cells` (which keys by lattice
    coordinate) -- a graph's fundamental index is the node, not a position, so a
    node's spatial ``locus`` (if any) is a projection hint, not part of this
    readout. Like the others it names no specific system: the caller chooses
    which field is the node's value.
    """
    return sorted(
        (rec["node"], rec.get(field))
        for rec in core["state"]["loci"]
    )


def sequence_symbols(core: dict[str, Any], field: str = "symbol") -> list[Any]:
    """Return the ordered ``field`` values of a sequence-topology core.

    The generic readout for a string-rewriting program: the produced word as
    a list of symbols. Like :func:`active_cells` it names no specific system
    -- the caller chooses which record field carries the symbol.
    """
    return [rec.get(field) for rec in core["state"]["sequence"]]

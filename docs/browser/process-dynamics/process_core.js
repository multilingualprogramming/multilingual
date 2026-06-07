// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// JS port of multilingualprogramming/codegen/process_core.py -- the
// modality-free stepper for semantic-core-v1.
//
// This is the load-bearing artifact of the polymodal dynamics layer: the
// engine that advances a (State, Topology, Rule, Schedule) tuple lives
// once and is shared by every modality runtime, so two surfaces cannot
// evolve the same program differently. This file is a faithful port of the
// Python core; tests/process_core_js_test.py runs it under Node and asserts
// its trajectory is byte-identical to Python's. The Python module stays the
// authority.
//
// Like its Python sibling, this is the *language*: it knows nothing about
// Game of Life or any specific system. Programs are data (program.v1.json),
// not branches in here.

export const CORE_KIND = "semantic-core-v1";
export const TOPOLOGY_LATTICE = "lattice";
export const TOPOLOGY_SEQUENCE = "sequence";
export const LATTICE_EXTENT_INFINITE = "infinite";
export const NEIGHBORHOOD_MOORE8 = "moore8";
export const NEIGHBORHOOD_VONNEUMANN4 = "von-neumann4";
export const RULE_REWRITE = "rewrite";
export const SCHEDULE_SYNCHRONOUS = "synchronous";
export const SCHEDULE_STATIC = "static";
export const SCHEDULE_GENERATIVE = "generative";
export const SCHEDULE_ASYNCHRONOUS = "asynchronous";
export const POPULATION_FIXED = "fixed";
export const POPULATION_OPEN = "open";

const MOORE8_OFFSETS = [
  [-1, -1], [0, -1], [1, -1],
  [-1, 0], [1, 0],
  [-1, 1], [0, 1], [1, 1],
];
const VONNEUMANN4_OFFSETS = [[0, -1], [-1, 0], [1, 0], [0, 1]];

// The one topology query: which loci are adjacent to this one?
export function neighbors(topology, locus) {
  if (topology.kind !== TOPOLOGY_LATTICE) {
    throw new Error(`topology kind ${topology.kind} not yet supported`);
  }
  const offsets =
    (topology.neighborhood ?? NEIGHBORHOOD_MOORE8) === NEIGHBORHOOD_MOORE8
      ? MOORE8_OFFSETS
      : VONNEUMANN4_OFFSETS;
  const [x, y] = locus;
  if (topology.extent === LATTICE_EXTENT_INFINITE) {
    // No walls: every adjacent coordinate is a neighbour.
    return offsets.map(([dx, dy]) => [x + dx, y + dy]);
  }
  const { width, height } = topology;
  const wrap = topology.wrap !== false;
  const result = [];
  for (const [dx, dy] of offsets) {
    let nx = x + dx;
    let ny = y + dy;
    if (wrap) {
      nx = ((nx % width) + width) % width;
      ny = ((ny % height) + height) % height;
      result.push([nx, ny]);
    } else if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
      result.push([nx, ny]);
    }
  }
  return result;
}

function gridOf(core) {
  const grid = new Map();
  for (const rec of core.state.loci) {
    grid.set(`${rec.locus[0]},${rec.locus[1]}`, rec);
  }
  return grid;
}

function clauseMatches(rec, nbs, grid, match) {
  const self = match.self ?? {};
  for (const field of Object.keys(self)) {
    if (rec[field] !== self[field]) {
      return false;
    }
  }
  for (const predicate of match.neighbor_count ?? []) {
    let tally = 0;
    for (const [nx, ny] of nbs) {
      const nb = grid.get(`${nx},${ny}`);
      if (nb && nb[predicate.field] === predicate.value) {
        tally += 1;
      }
    }
    if (!predicate.in.includes(tally)) {
      return false;
    }
  }
  return true;
}

function produceFor(rec, nbs, grid, clauses, fallback) {
  for (const clause of clauses) {
    if (clauseMatches(rec, nbs, grid, clause.match ?? {})) {
      return clause.produce;
    }
  }
  return fallback;
}

function isEmpty(rec, empty) {
  return Object.keys(empty).every((field) => rec[field] === empty[field]);
}

// Fixed population: every declared locus persists, only its state moves.
function stepFixed(core, topology, clauses, fallback) {
  const grid = gridOf(core);
  return core.state.loci.map((rec) => {
    const locus = [rec.locus[0], rec.locus[1]];
    const nbs = neighbors(topology, locus);
    return { ...rec, ...produceFor(rec, nbs, grid, clauses, fallback), locus };
  });
}

// Open population: rules may create and destroy loci. Only non-empty loci
// are stored; each step considers the frontier (existing loci plus their
// neighbours), since only those positions can change under a local rule.
function stepOpen(core, topology, clauses, fallback) {
  const empty = core.state.empty;
  const grid = gridOf(core);

  const candidates = new Map(); // key -> [x, y]
  for (const rec of core.state.loci) {
    const locus = [rec.locus[0], rec.locus[1]];
    candidates.set(`${locus[0]},${locus[1]}`, locus);
    for (const [nx, ny] of neighbors(topology, locus)) {
      candidates.set(`${nx},${ny}`, [nx, ny]);
    }
  }

  const next = [];
  const ordered = [...candidates.values()].sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
  for (const locus of ordered) {
    const rec = grid.get(`${locus[0]},${locus[1]}`) ?? { locus, ...empty };
    const nbs = neighbors(topology, locus);
    const produced = { ...rec, ...produceFor(rec, nbs, grid, clauses, fallback), locus };
    if (!isEmpty(produced, empty)) {
      next.push(produced);
    }
  }
  return next;
}

// Asynchronous population: sequential in-place update in a fixed scan order.
// Loci are visited in sorted coordinate order; each reads the *already-updated*
// grid (so it sees neighbours that have acted earlier this sweep) and writes a
// fresh record back. The input is never mutated. produceFor may return the
// rule's null default (no fallback), and spreading null is a no-op -- so a
// locus matching no clause is left unchanged, the identity-on-no-match a cyclic
// ecology rule relies on. The emitted list keeps the original loci order.
function stepAsync(core, topology, clauses, fallback) {
  const grid = gridOf(core);
  const keys = [...grid.keys()].sort((a, b) => {
    const [ax, ay] = a.split(",").map(Number);
    const [bx, by] = b.split(",").map(Number);
    return (ax - bx) || (ay - by);
  });
  for (const key of keys) {
    const rec = grid.get(key);
    const locus = [rec.locus[0], rec.locus[1]];
    const nbs = neighbors(topology, locus);
    grid.set(key, { ...rec, ...produceFor(rec, nbs, grid, clauses, fallback), locus });
  }
  return core.state.loci.map((rec) => {
    const updated = grid.get(`${rec.locus[0]},${rec.locus[1]}`);
    return { ...updated };
  });
}

// Generative rewriting: rewrite every symbol of a sequence in parallel and
// concatenate the productions. A clause's `produce` is a *list* of records
// that replaces the matched symbol, so a production longer than one symbol
// grows the sequence -- the "generativity for free" the rewrite primitive
// gives (L-systems, fractal strings). Matching is context-free (self fields
// only), so neighbours/grid are empty. A symbol matching no clause maps to
// itself. The same rewrite primitive as the lattice path; only the schedule's
// reading of `produce` (a sequence, not a single state) differs.
function stepGenerative(core, clauses) {
  const emptyGrid = new Map();
  const next = [];
  for (const rec of core.state.sequence) {
    let production = null;
    for (const clause of clauses) {
      if (clauseMatches(rec, [], emptyGrid, clause.match ?? {})) {
        production = clause.produce;
        break;
      }
    }
    if (production === null) {
      next.push({ ...rec });
    } else {
      for (const symbol of production) {
        next.push({ ...symbol });
      }
    }
  }
  return next;
}

// Advance the process core by one step, returning a new core. The input is
// never mutated; topology/rule/schedule pass through unchanged.
export function step(core) {
  if (core.schedule.kind === SCHEDULE_GENERATIVE) {
    if (core.rule.kind !== RULE_REWRITE) {
      throw new Error(`rule kind ${core.rule.kind} not yet supported`);
    }
    const nextSequence = stepGenerative(core, core.rule.clauses);
    return { ...core, state: { ...core.state, sequence: nextSequence } };
  }
  if (core.schedule.kind === SCHEDULE_STATIC) {
    // A static snapshot does not evolve; stepping is identity. Touches
    // neither topology nor loci shape, so a migrated v0 core steps cleanly.
    return { ...core, state: { ...core.state } };
  }
  if (
    core.schedule.kind !== SCHEDULE_SYNCHRONOUS &&
    core.schedule.kind !== SCHEDULE_ASYNCHRONOUS
  ) {
    throw new Error(`schedule kind ${core.schedule.kind} not yet supported`);
  }
  if (core.rule.kind !== RULE_REWRITE) {
    throw new Error(`rule kind ${core.rule.kind} not yet supported`);
  }
  const { topology } = core;
  const { clauses, default: fallback } = core.rule;
  const population = core.state.population ?? POPULATION_FIXED;

  let nextLoci;
  if (core.schedule.kind === SCHEDULE_ASYNCHRONOUS) {
    if (population !== POPULATION_FIXED) {
      throw new Error(
        `asynchronous schedule with population ${population} not yet supported`
      );
    }
    nextLoci = stepAsync(core, topology, clauses, fallback);
  } else if (population === POPULATION_FIXED) {
    nextLoci = stepFixed(core, topology, clauses, fallback);
  } else if (population === POPULATION_OPEN) {
    nextLoci = stepOpen(core, topology, clauses, fallback);
  } else {
    throw new Error(`population mode ${population} not yet supported`);
  }

  return { ...core, state: { ...core.state, loci: nextLoci } };
}

// Run the stepper `steps` times, returning the trajectory (steps + 1 frames).
export function run(core, steps) {
  if (steps < 0) {
    throw new Error("steps must be nonnegative");
  }
  const trajectory = [core];
  let current = core;
  for (let i = 0; i < steps; i += 1) {
    current = step(current);
    trajectory.push(current);
  }
  return trajectory;
}

// Sorted [x, y] of loci whose `field` is truthy -- the simplest projection.
export function activeCells(core, field = "alive") {
  return core.state.loci
    .filter((rec) => rec[field])
    .map((rec) => [rec.locus[0], rec.locus[1]])
    .sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
}

// Sorted [x, y, value] of each locus's `field` -- preserves the value a
// multi-state field carries (vs activeCells' boolean mask), the readout a
// several-species ecology projects from. Names no specific system.
export function fieldCells(core, field = "state") {
  return core.state.loci
    .map((rec) => [rec.locus[0], rec.locus[1], rec[field]])
    .sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
}

// Ordered `field` values of a sequence-topology core -- the produced word as
// a list of symbols. The generative analogue of activeCells; names no system.
export function sequenceSymbols(core, field = "symbol") {
  return core.state.sequence.map((rec) => rec[field]);
}

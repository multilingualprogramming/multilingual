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
export const NEIGHBORHOOD_MOORE8 = "moore8";
export const NEIGHBORHOOD_VONNEUMANN4 = "von-neumann4";
export const RULE_REWRITE = "rewrite";
export const SCHEDULE_SYNCHRONOUS = "synchronous";

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
  const { width, height } = topology;
  const wrap = topology.wrap !== false;
  const offsets =
    (topology.neighborhood ?? NEIGHBORHOOD_MOORE8) === NEIGHBORHOOD_MOORE8
      ? MOORE8_OFFSETS
      : VONNEUMANN4_OFFSETS;
  const [x, y] = locus;
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

// Advance the process core by one step, returning a new core. The input is
// never mutated; topology/rule/schedule pass through unchanged.
export function step(core) {
  if (core.schedule.kind !== SCHEDULE_SYNCHRONOUS) {
    throw new Error(`schedule kind ${core.schedule.kind} not yet supported`);
  }
  if (core.rule.kind !== RULE_REWRITE) {
    throw new Error(`rule kind ${core.rule.kind} not yet supported`);
  }
  const { topology } = core;
  const { clauses, default: fallback } = core.rule;
  const grid = gridOf(core);

  const nextLoci = core.state.loci.map((rec) => {
    const locus = [rec.locus[0], rec.locus[1]];
    const nbs = neighbors(topology, locus);
    let produce = fallback;
    for (const clause of clauses) {
      if (clauseMatches(rec, nbs, grid, clause.match ?? {})) {
        produce = clause.produce;
        break;
      }
    }
    return { ...rec, ...produce, locus };
  });

  return { ...core, state: { loci: nextLoci } };
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

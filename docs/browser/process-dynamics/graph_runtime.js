// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Browser runtime for an animated *graph* semantic-core-v1 process -- a
// network contagion (discrete SIR on a two-community contact graph).
//
// Same polymodal claim as process_runtime.js / sequence_runtime.js /
// ecosystem_runtime.js, on the axis those did not exercise: an arbitrary
// graph topology, where adjacency is the wiring (the edge set) and not the
// geometry. A single rule-bearing manifest (program.graph.v1.json) is advanced
// by the ONE shared stepper (process_core.js) and rendered into two peer
// surfaces -- a node-link diagram coloured by state, and a chord per frame.
// This mirrors process_graph_projection.py: each node maps to a placed,
// coloured mark and to a voice whose pitch row IS its state value -- exact
// bijections over the node set, so the picture and the sound are the same
// field. Neither surface steps the program. The status line shows the
// program's expressiveness tier, read straight from the manifest's axes by the
// shared classifier (tierOf) -- here Tier 4 (graph rewriting), yet the
// projection still round-trips exactly: tier (class ceiling) and invertibility
// (this instance) are orthogonal.

import { run, nodeCells, tierOf, TIER_NAMES, SCHEDULE_SYNCHRONOUS } from "./process_core.js";

const FIELD = "state";
const STEP_MS = 900;

// 0 susceptible, 1 infected, 2 recovered.
const STATE_LABEL = { 0: "susceptible", 1: "infected", 2: "recovered" };
const STATE_COLOUR = { 0: "#5ad1ff", 1: "#e0506a", 2: "#9be870" };

// --- Geometry -------------------------------------------------------------
// Node positions are the `locus` view hints the program carries (the engine
// never reads them). Fit the embedding to the canvas with a little padding.

function positionsOf(core) {
  const pos = new Map();
  for (const rec of core.state.loci) pos.set(rec.node, rec.locus);
  return pos;
}

function fitTransform(core, canvas, pad = 40) {
  const xs = core.state.loci.map((r) => r.locus[0]);
  const ys = core.state.loci.map((r) => r.locus[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const sx = (canvas.width - 2 * pad) / Math.max(1, maxX - minX);
  const sy = (canvas.height - 2 * pad) / Math.max(1, maxY - minY);
  return (x, y) => [pad + (x - minX) * sx, pad + (y - minY) * sy];
}

// --- Spatial surface: the node-link diagram --------------------------------

function drawGraph(canvas, core, frame, pos, project) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Edges first, so nodes sit on top. The wiring is what makes this a graph.
  ctx.strokeStyle = "rgba(232, 238, 252, 0.22)";
  ctx.lineWidth = 1.5;
  for (const [a, b] of core.topology.edges) {
    const [ax, ay] = project(...pos.get(a));
    const [bx, by] = project(...pos.get(b));
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.stroke();
  }

  for (const [node, value] of nodeCells(frame, FIELD)) {
    const [px, py] = project(...pos.get(node));
    ctx.beginPath();
    ctx.arc(px, py, 12, 0, Math.PI * 2);
    ctx.fillStyle = STATE_COLOUR[value] ?? "#888";
    ctx.fill();
    ctx.strokeStyle = "rgba(11, 16, 32, 0.9)";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

// --- Sonic surface ---------------------------------------------------------
// Each node maps to a voice whose pitch row IS its state value (each SIR state
// a distinct pitch), so the chord carries the field's values. Mirrors
// process_graph_projection.to_sonic_frame.

function makeSonic() {
  let audio = null;
  const ensure = () => {
    if (!audio) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      audio = new Ctx();
    }
    return audio;
  };
  const pitchHz = [220, 330, 440]; // susceptible / infected / recovered
  return {
    playFrame(frame) {
      const cells = nodeCells(frame, FIELD);
      if (!cells.length) return;
      const ctx = ensure();
      const now = ctx.currentTime;
      cells.forEach(([, value], i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const t = now + i * 0.04;
        osc.type = ["sine", "sawtooth", "triangle"][value] ?? "sine";
        osc.frequency.value = pitchHz[value] ?? 220;
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.05, t + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.24);
      });
    },
    resume() {
      ensure().resume();
    },
  };
}

// --- Orchestration ----------------------------------------------------------

export async function boot(opts = {}) {
  const {
    manifestUrl = "./program.graph.v1.json",
    steps = 12,
    canvas = document.getElementById("graph"),
    status = document.getElementById("status"),
    soundToggle = document.getElementById("sound"),
  } = opts;

  const core = await fetch(manifestUrl, { cache: "no-store" }).then((r) => r.json());
  if (core.kind !== "semantic-core-v1") {
    throw new Error(`expected semantic-core-v1, got ${core.kind}`);
  }
  if (core.schedule.kind !== SCHEDULE_SYNCHRONOUS) {
    throw new Error(`expected a synchronous program, got ${core.schedule.kind}`);
  }

  // The single source of motion: one stepper, one trajectory. Both surfaces
  // read each frame's nodes -- neither rewrites it.
  const trajectory = run(core, steps);
  const pos = positionsOf(core);
  const project = fitTransform(core, canvas);
  const tier = tierOf(core);

  const sonic = makeSonic();
  let soundOn = false;
  if (soundToggle) {
    soundToggle.addEventListener("click", () => {
      soundOn = !soundOn;
      if (soundOn) sonic.resume();
      soundToggle.textContent = soundOn ? "Sound: on" : "Sound: off";
    });
  }

  let i = 0;
  function tick() {
    const frame = trajectory[i % trajectory.length];
    drawGraph(canvas, core, frame, pos, project);
    if (soundOn) sonic.playFrame(frame);
    if (status) {
      const counts = { 0: 0, 1: 0, 2: 0 };
      for (const [, value] of nodeCells(frame, FIELD)) counts[value] += 1;
      const census = Object.keys(STATE_LABEL)
        .map((s) => `${STATE_LABEL[s]}:${counts[s]}`)
        .join("  ");
      status.textContent =
        `tick ${i % trajectory.length} / ${trajectory.length - 1} — ${census}` +
        ` — Tier ${tier} (${TIER_NAMES[tier]})`;
    }
    i += 1;
  }

  tick();
  setInterval(tick, STEP_MS);
}

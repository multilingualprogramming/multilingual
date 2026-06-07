// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Browser runtime for an animated *multi-state field* semantic-core-v1
// process -- a cyclic-dominance ecosystem (spatial rock-paper-scissors).
//
// Same polymodal claim as process_runtime.js / sequence_runtime.js, on the
// two axes those did not exercise: a heterogeneous per-locus value (a
// `species`, not a boolean) advanced under an *asynchronous* schedule
// (sequential in-place update). A single rule-bearing manifest
// (program.ecosystem.v1.json) is advanced by the ONE shared stepper
// (process_core.js) and rendered into two peer surfaces -- a coloured field
// and a chord per frame. This mirrors process_field_projection.py: every
// locus maps to a mark at (x, y) carrying its value, and to a voice whose
// column is the step, whose row is the pitch row, and whose value rides on
// the voice -- exact bijections, so the picture and the sound are the same
// field. Neither surface steps the program.

import { run, fieldCells, SCHEDULE_ASYNCHRONOUS } from "./process_core.js";

const FIELD = "species";
const STEP_MS = 700;

// Distinct hue per species value, assigned from the sorted set of values that
// actually appear across the run so colours are stable frame to frame.
const PALETTE = ["#e0506a", "#5ad1ff", "#9be870", "#f3c14b", "#c08bff", "#ff9b5a"];

function speciesValues(trajectory) {
  const values = new Set();
  for (const frame of trajectory) {
    for (const [, , value] of fieldCells(frame, FIELD)) values.add(value);
  }
  return [...values].sort((a, b) => a - b);
}

function extentOf(core) {
  const { width, height } = core.topology;
  return { width, height };
}

// --- Spatial surface: the coloured field -----------------------------------

function drawSpatial(canvas, frame, extent, colourOf) {
  const ctx = canvas.getContext("2d");
  const cell = Math.max(
    2,
    Math.floor(Math.min(canvas.width / extent.width, canvas.height / extent.height)),
  );
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (const [x, y, value] of fieldCells(frame, FIELD)) {
    ctx.fillStyle = colourOf(value);
    // Highest row drawn at the top, matching the sonic pitch axis.
    const drawY = extent.height - 1 - y;
    ctx.fillRect(x * cell, drawY * cell, cell - 1, cell - 1);
  }
}

// --- Sonic surface ----------------------------------------------------------
// Each locus maps to a voice (step = column, pitch row = row); the species
// value selects the timbre, so the chord carries the field's values, not just
// its shape. A dense field would overwhelm the ear, so playback samples one
// representative column -- the picture stays the faithful, exact surface; the
// sound is a sketch of the same data.

function makeSonic(values) {
  let audio = null;
  function ensure() {
    if (!audio) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      audio = new Ctx();
    }
    return audio;
  }
  const scale = [0, 2, 4, 7, 9];
  const timbre = new Map(values.map((v, i) => [v, ["sine", "triangle", "sawtooth", "square"][i % 4]]));
  function pitchToHz(pitchRow) {
    const octave = Math.floor(pitchRow / scale.length);
    const semitone = scale[pitchRow % scale.length] + 12 * octave;
    return 220 * Math.pow(2, semitone / 12);
  }
  return {
    playFrame(voices) {
      if (!voices.length) return;
      const ctx = ensure();
      const now = ctx.currentTime;
      for (const { step, pitchRow, value } of voices) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const t = now + step * 0.05;
        osc.type = timbre.get(value) ?? "sine";
        osc.frequency.value = pitchToHz(pitchRow);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.06, t + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.2);
      }
    },
    resume() {
      ensure().resume();
    },
  };
}

// One representative column of voices, so the chord is audible rather than a
// wall. Mirrors the field projection's voice shape (step, pitch row, value).
function sampleVoices(frame, extent) {
  const column = Math.floor(extent.width / 2);
  const top = extent.height - 1;
  return fieldCells(frame, FIELD)
    .filter(([x]) => x === column)
    .map(([, y, value]) => ({ step: y, pitchRow: top - y, value }));
}

// --- Orchestration ----------------------------------------------------------

export async function boot(opts = {}) {
  const {
    manifestUrl = "./program.ecosystem.v1.json",
    steps = 24,
    canvas = document.getElementById("spatial"),
    status = document.getElementById("status"),
    soundToggle = document.getElementById("sound"),
  } = opts;

  const core = await fetch(manifestUrl, { cache: "no-store" }).then((r) => r.json());
  if (core.kind !== "semantic-core-v1") {
    throw new Error(`expected semantic-core-v1, got ${core.kind}`);
  }
  if (core.schedule.kind !== SCHEDULE_ASYNCHRONOUS) {
    throw new Error(`expected an asynchronous program, got ${core.schedule.kind}`);
  }

  // The single source of motion: one stepper, one trajectory of fields. Both
  // surfaces read each frame's field -- neither rewrites it.
  const trajectory = run(core, steps);
  const extent = extentOf(core);
  const values = speciesValues(trajectory);
  const colourOf = (v) => PALETTE[values.indexOf(v) % PALETTE.length];

  const sonic = makeSonic(values);
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
    drawSpatial(canvas, frame, extent, colourOf);
    if (soundOn) sonic.playFrame(sampleVoices(frame, extent));
    if (status) {
      const counts = new Map(values.map((v) => [v, 0]));
      for (const [, , value] of fieldCells(frame, FIELD)) {
        counts.set(value, (counts.get(value) ?? 0) + 1);
      }
      const census = values.map((v) => `${v}:${counts.get(v)}`).join("  ");
      status.textContent =
        `tick ${i % trajectory.length} / ${trajectory.length - 1} — species ${census}`;
    }
    i += 1;
  }

  tick();
  setInterval(tick, STEP_MS);
}

// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Browser runtime for an animated semantic-core-v1 process.
//
// The polymodal claim, made visible and audible: a single rule-bearing
// manifest (program.v1.json) is advanced by ONE shared stepper
// (process_core.js, the modality-free engine) and rendered into two peer
// surfaces at once -- a spatial canvas and sonic voices. Neither modality
// steps the program; both project the same frame. If the spatial cells and
// the sounding voices ever disagreed, a modality would be evolving the
// program on its own -- exactly what the shared stepper forbids.

import { run, activeCells, tierOf, TIER_NAMES, LATTICE_EXTENT_INFINITE } from "./process_core.js";

const ACTIVE_FIELD = "alive";
const STEP_MS = 220;

// --- Viewport: a finite window into the lattice (mirror process_projection) -
// A bounded lattice shows its whole extent; an unbounded (infinite-topology,
// open-population) program can only be shown through a window, so we compute
// a box that holds the entire trajectory and keep it fixed -- the pattern
// travels across a stable frame instead of the camera chasing it.

function boundingBox(trajectory, margin = 1) {
  const cells = trajectory.flatMap((f) => activeCells(f, ACTIVE_FIELD));
  if (!cells.length) return { x0: 0, y0: 0, width: 1, height: 1 };
  const xs = cells.map(([x]) => x);
  const ys = cells.map(([, y]) => y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  return {
    x0: minX - margin,
    y0: minY - margin,
    width: Math.max(...xs) - minX + 1 + 2 * margin,
    height: Math.max(...ys) - minY + 1 + 2 * margin,
  };
}

function resolveViewport(trajectory) {
  const topology = trajectory[0].topology;
  if (topology.extent === LATTICE_EXTENT_INFINITE) {
    return boundingBox(trajectory);
  }
  return { x0: 0, y0: 0, width: topology.width, height: topology.height };
}

function inViewport(x, y, vp) {
  return x >= vp.x0 && x < vp.x0 + vp.width && y >= vp.y0 && y < vp.y0 + vp.height;
}

// --- Projections of one frame within the viewport --------------------------

function spatialMarks(frame, vp) {
  return activeCells(frame, ACTIVE_FIELD).filter(([x, y]) => inViewport(x, y, vp));
}

function sonicVoices(frame, vp) {
  const top = vp.y0 + vp.height - 1; // highest row -> highest pitch
  return spatialMarks(frame, vp).map(([x, y]) => ({
    step: x - vp.x0,
    pitchRow: top - y,
  }));
}

// --- Spatial surface --------------------------------------------------------

function drawSpatial(canvas, frame, vp) {
  const ctx = canvas.getContext("2d");
  const { width, height } = vp;
  const cell = Math.floor(Math.min(canvas.width / width, canvas.height / height));
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "rgba(255,255,255,0.06)";
  for (let x = 0; x <= width; x += 1) {
    ctx.beginPath();
    ctx.moveTo(x * cell, 0);
    ctx.lineTo(x * cell, height * cell);
    ctx.stroke();
  }
  for (let y = 0; y <= height; y += 1) {
    ctx.beginPath();
    ctx.moveTo(0, y * cell);
    ctx.lineTo(width * cell, y * cell);
    ctx.stroke();
  }
  ctx.fillStyle = "#5ad1ff";
  for (const [x, y] of spatialMarks(frame, vp)) {
    // Map global lattice coordinates into viewport-local cells.
    ctx.fillRect((x - vp.x0) * cell + 1, (y - vp.y0) * cell + 1, cell - 2, cell - 2);
  }
}

// --- Sonic surface ----------------------------------------------------------

function makeSonic() {
  let audio = null;
  function ensure() {
    if (!audio) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      audio = new Ctx();
    }
    return audio;
  }
  // Pentatonic-ish mapping so dense frames stay consonant.
  const scale = [0, 2, 4, 7, 9];
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
      for (const { step, pitchRow } of voices) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        // Column staggers onset within the step so rhythm is audible.
        const t = now + (step / Math.max(voices.length, 8)) * 0.05;
        osc.type = "triangle";
        osc.frequency.value = pitchToHz(pitchRow);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.12, t + 0.01);
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

// --- Orchestration ----------------------------------------------------------

export async function boot(opts = {}) {
  const params = new URLSearchParams(window.location.search);
  const {
    // ?manifest=program.open.v1.json switches to the unbounded program.
    manifestUrl = params.get("manifest")
      ? `./${params.get("manifest")}`
      : "./program.v1.json",
    steps = 60,
    canvas = document.getElementById("spatial"),
    status = document.getElementById("status"),
    soundToggle = document.getElementById("sound"),
  } = opts;

  const core = await fetch(manifestUrl, { cache: "no-store" }).then((r) => r.json());
  if (core.kind !== "semantic-core-v1") {
    throw new Error(`expected semantic-core-v1, got ${core.kind}`);
  }

  // The single source of motion: one stepper, one trajectory. Both
  // modalities below read frames out of this -- they never step. The
  // viewport is computed once from that trajectory (the full extent for a
  // bounded lattice, a stable bounding box for an unbounded one).
  const trajectory = run(core, steps);
  const viewport = resolveViewport(trajectory);
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
    drawSpatial(canvas, frame, viewport);
    const voices = sonicVoices(frame, viewport);
    if (soundOn) sonic.playFrame(voices);
    if (status) {
      status.textContent =
        `frame ${i % trajectory.length} / ${trajectory.length - 1} — ` +
        `${spatialMarks(frame, viewport).length} live cells (spatial) / ` +
        `${voices.length} voices (sonic)` +
        ` — Tier ${tier} (${TIER_NAMES[tier]})`;
    }
    i += 1;
  }

  tick();
  setInterval(tick, STEP_MS);
}

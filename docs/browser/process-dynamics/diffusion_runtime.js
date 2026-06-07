// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Browser runtime for an animated *continuous-time* semantic-core-v1 process
// -- a heat-diffusion field.
//
// Same polymodal claim as process_runtime.js / ecosystem_runtime.js, on the
// axis none of the others exercise: a *continuous* per-cell value advanced by a
// *rate* rule under a *continuous-dt* schedule (one explicit-Euler step from the
// previous frame). There is no pattern match here -- only du/dt integrated over
// time. A single rule-bearing manifest (program.diffusion.v1.json) is advanced
// by the ONE shared stepper (process_core.js) and rendered into two peer
// surfaces -- a heat field and a sampled chord. This mirrors
// process_field_projection.py: every locus maps to a mark at (x, y) carrying its
// value, and to a voice whose value rides on it -- exact bijections, so the
// picture and the sound are the same field. Neither surface steps the program.
// The status line shows the program's expressiveness tier, read straight from
// the manifest's axes by the shared classifier (tierOf) -- here Tier 1
// (fixed-population continuous dynamics).

import { run, fieldCells, tierOf, TIER_NAMES, SCHEDULE_CONTINUOUS } from "./process_core.js";

const FIELD = "u";
const STEP_MS = 500;

function extentOf(core) {
  const { width, height } = core.topology;
  return { width, height };
}

// The peak value across the whole run, so the colour ramp is stable frame to
// frame (a fixed scale, not a per-frame auto-gain that would hide the spread).
function peakValue(trajectory) {
  let peak = 0;
  for (const frame of trajectory) {
    for (const [, , value] of fieldCells(frame, FIELD)) {
      if (value > peak) peak = value;
    }
  }
  return peak || 1;
}

// --- Spatial surface: the heat field ---------------------------------------
// A blue-to-hot ramp by value. Hot is where u is large; the seed cell starts at
// the top of the ramp and fades as it diffuses.

function heatColour(t) {
  // t in [0, 1]: dark blue -> cyan -> warm white.
  const r = Math.round(255 * Math.min(1, Math.max(0, t * 1.6 - 0.4)));
  const g = Math.round(255 * Math.min(1, t * 1.3));
  const b = Math.round(255 * Math.min(1, 0.4 + t * 0.6));
  return `rgb(${r}, ${g}, ${b})`;
}

function drawSpatial(canvas, frame, extent, peak) {
  const ctx = canvas.getContext("2d");
  const cell = Math.max(
    2,
    Math.floor(Math.min(canvas.width / extent.width, canvas.height / extent.height)),
  );
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (const [x, y, value] of fieldCells(frame, FIELD)) {
    ctx.fillStyle = heatColour(value / peak);
    // Highest row drawn at the top, matching the sonic pitch axis.
    const drawY = extent.height - 1 - y;
    ctx.fillRect(x * cell, drawY * cell, cell - 1, cell - 1);
  }
}

// --- Sonic surface ----------------------------------------------------------
// A dense continuous field would overwhelm the ear, so playback samples one
// representative column (mirrors process_field_projection's voice shape: step,
// pitch row, value). The value modulates the voice's gain -- a hotter cell sings
// louder -- so the chord carries the field's magnitude, not just its shape.

function makeSonic() {
  let audio = null;
  function ensure() {
    if (!audio) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      audio = new Ctx();
    }
    return audio;
  }
  const scale = [0, 2, 4, 7, 9];
  function pitchToHz(pitchRow) {
    const octave = Math.floor(pitchRow / scale.length);
    const semitone = scale[pitchRow % scale.length] + 12 * octave;
    return 220 * Math.pow(2, semitone / 12);
  }
  return {
    playFrame(voices, peak) {
      if (!voices.length) return;
      const ctx = ensure();
      const now = ctx.currentTime;
      for (const { step, pitchRow, value } of voices) {
        const level = Math.min(0.18, (value / peak) * 0.18);
        if (level < 0.001) continue;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const t = now + step * 0.05;
        osc.type = "sine";
        osc.frequency.value = pitchToHz(pitchRow);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(level, t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.32);
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
    manifestUrl = "./program.diffusion.v1.json",
    steps = 40,
    canvas = document.getElementById("spatial"),
    status = document.getElementById("status"),
    soundToggle = document.getElementById("sound"),
  } = opts;

  const core = await fetch(manifestUrl, { cache: "no-store" }).then((r) => r.json());
  if (core.kind !== "semantic-core-v1") {
    throw new Error(`expected semantic-core-v1, got ${core.kind}`);
  }
  if (core.schedule.kind !== SCHEDULE_CONTINUOUS) {
    throw new Error(`expected a continuous-dt program, got ${core.schedule.kind}`);
  }

  // The single source of motion: one stepper, one trajectory of fields. Both
  // surfaces read each frame's field -- neither rewrites it.
  const trajectory = run(core, steps);
  const extent = extentOf(core);
  const peak = peakValue(trajectory);
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
    drawSpatial(canvas, frame, extent, peak);
    if (soundOn) sonic.playFrame(sampleVoices(frame, extent), peak);
    if (status) {
      let mass = 0;
      let hottest = 0;
      for (const [, , value] of fieldCells(frame, FIELD)) {
        mass += value;
        if (value > hottest) hottest = value;
      }
      status.textContent =
        `tick ${i % trajectory.length} / ${trajectory.length - 1} — ` +
        `mass ${mass.toFixed(3)} (conserved) · peak ${hottest.toFixed(3)}` +
        ` — Tier ${tier} (${TIER_NAMES[tier]})`;
    }
    i += 1;
  }

  tick();
  setInterval(tick, STEP_MS);
}

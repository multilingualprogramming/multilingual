// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Browser runtime for the *nonlinear* continuous-time axis -- Gray-Scott
// reaction-diffusion. Same polymodal claim as diffusion_runtime.js, but the
// rate rule now carries a `products` term (the autocatalytic reaction u·v²)
// that diffusion alone cannot express. One rule-bearing manifest
// (program.gray_scott.v1.json) is advanced by the ONE shared stepper
// (process_core.js) and projected into a field you see and a chord you hear --
// neither modality steps the program. Tier 1 (fixed-population continuous).

import { run, fieldCells, tierOf, TIER_NAMES, SCHEDULE_CONTINUOUS } from "./process_core.js";

const FIELD = "v"; // the inhibitor V -- where the pattern lives
const STEP_MS = 90;

function extentOf(core) {
  const { width, height } = core.topology;
  return { width, height };
}

// Peak of V across the run, so the colour ramp is stable frame to frame.
function peakValue(trajectory) {
  let peak = 0;
  for (const frame of trajectory) {
    for (const [, , value] of fieldCells(frame, FIELD)) {
      if (value > peak) peak = value;
    }
  }
  return peak || 1;
}

// A magma-like ramp: dark -> violet -> amber where V is concentrated.
function reactionColour(t) {
  const u = Math.min(1, Math.max(0, t));
  const r = Math.round(255 * Math.min(1, u * 1.8));
  const g = Math.round(255 * Math.min(1, Math.max(0, u * 1.4 - 0.5)));
  const b = Math.round(255 * Math.min(1, 0.25 + u * 0.5));
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
    ctx.fillStyle = reactionColour(value / peak);
    const drawY = extent.height - 1 - y;
    ctx.fillRect(x * cell, drawY * cell, cell - 1, cell - 1);
  }
}

function makeSonic() {
  let audio = null;
  function ensure() {
    if (!audio) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      audio = new Ctx();
    }
    return audio;
  }
  const scale = [0, 3, 5, 7, 10];
  function pitchToHz(pitchRow) {
    const octave = Math.floor(pitchRow / scale.length);
    const semitone = scale[pitchRow % scale.length] + 12 * octave;
    return 196 * Math.pow(2, semitone / 12);
  }
  return {
    playFrame(voices, peak) {
      if (!voices.length) return;
      const ctx = ensure();
      const now = ctx.currentTime;
      for (const { step, pitchRow, value } of voices) {
        const level = Math.min(0.16, (value / peak) * 0.16);
        if (level < 0.001) continue;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const t = now + step * 0.05;
        osc.type = "triangle";
        osc.frequency.value = pitchToHz(pitchRow);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(level, t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.32);
      }
    },
    resume() { ensure().resume(); },
  };
}

function sampleVoices(frame, extent) {
  const column = Math.floor(extent.width / 2);
  const top = extent.height - 1;
  return fieldCells(frame, FIELD)
    .filter(([x]) => x === column)
    .map(([, y, value]) => ({ step: y, pitchRow: top - y, value }));
}

export async function boot(opts = {}) {
  const {
    manifestUrl = "./program.gray_scott.v1.json",
    steps = 220,
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
      let totalV = 0;
      for (const [, , value] of fieldCells(frame, FIELD)) totalV += value;
      status.textContent =
        `tick ${i % trajectory.length} / ${trajectory.length - 1} — ` +
        `total V ${totalV.toFixed(2)} · peak ${peak.toFixed(3)}` +
        ` — Tier ${tier} (${TIER_NAMES[tier]})`;
    }
    i += 1;
  }

  tick();
  setInterval(tick, STEP_MS);
}

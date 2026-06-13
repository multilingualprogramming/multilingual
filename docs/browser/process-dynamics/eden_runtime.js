// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Browser runtime for the *stochastic* axis -- Eden growth. The same shared
// stepper (process_core.js) advances a rewrite rule whose clause carries the
// new `chance` predicate: a cell joins the cluster only a fraction of the time,
// the fraction set by a deterministic hash of (locus, step, salt). So the
// cluster you see grows with a rough, fractal boundary, yet the trajectory is
// reproducible -- reloading the page yields the identical cluster. One manifest,
// two senses (a field and a chord); neither modality steps the program.
// Tier 2 (synchronous lattice rule).

import { run, fieldCells, tierOf, TIER_NAMES, SCHEDULE_SYNCHRONOUS } from "./process_core.js";

const FIELD = "alive";
const STEP_MS = 220;

function extentOf(core) {
  const { width, height } = core.topology;
  return { width, height };
}

function drawSpatial(canvas, frame, extent) {
  const ctx = canvas.getContext("2d");
  const cell = Math.max(
    2,
    Math.floor(Math.min(canvas.width / extent.width, canvas.height / extent.height)),
  );
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (const [x, y, value] of fieldCells(frame, FIELD)) {
    if (!value) continue;
    // Cluster cells in warm ink; the centre seed brighter than the frontier.
    ctx.fillStyle = "#f4c267";
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
        const t = now + step * 0.04;
        osc.type = "sine";
        osc.frequency.value = pitchToHz(pitchRow);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.12, t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.27);
      }
    },
    resume() { ensure().resume(); },
  };
}

// Voices from the cluster cells in one central column -- a sparse chord that
// thickens as the cluster grows through that column.
function sampleVoices(frame, extent) {
  const column = Math.floor(extent.width / 2);
  const top = extent.height - 1;
  return fieldCells(frame, FIELD)
    .filter(([x, , value]) => x === column && value)
    .map(([, y]) => ({ step: y, pitchRow: top - y }));
}

export async function boot(opts = {}) {
  const {
    manifestUrl = "./program.eden.v1.json",
    steps = 38,
    canvas = document.getElementById("spatial"),
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

  const trajectory = run(core, steps);
  const extent = extentOf(core);
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
    drawSpatial(canvas, frame, extent);
    if (soundOn) sonic.playFrame(sampleVoices(frame, extent));
    if (status) {
      let pop = 0;
      for (const [, , value] of fieldCells(frame, FIELD)) if (value) pop += 1;
      status.textContent =
        `tick ${i % trajectory.length} / ${trajectory.length - 1} — ` +
        `cluster ${pop} cells (grows, reproducible)` +
        ` — Tier ${tier} (${TIER_NAMES[tier]})`;
    }
    i += 1;
  }

  tick();
  setInterval(tick, STEP_MS);
}

// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Browser runtime for an animated *generative* semantic-core-v1 process
// (an L-system / string rewriting program).
//
// Same polymodal claim as process_runtime.js, on the other half of the
// rewrite primitive: a single rule-bearing manifest (program.lsystem.v1.json)
// is advanced by the ONE shared stepper (process_core.js) and rendered into
// two peer surfaces at once -- a spatial piano-roll and a sonic melody. The
// generative schedule grows the word each generation; both modalities read the
// same word, neither rewrites it. This mirrors process_sequence_projection.py:
// the pitch axis is the alphabet (distinct symbols), each symbol at position i
// maps to a mark/voice at (i, alphabet-row) -- an exact bijection, so the grid
// and the melody represent the identical string.

import { run, sequenceSymbols, SCHEDULE_GENERATIVE } from "./process_core.js";

const SYMBOL_FIELD = "symbol";
const STEP_MS = 900;

// --- Alphabet: the pitch axis (mirror process_sequence_projection) ----------
// A generative sequence has no fixed length, but its set of distinct symbols
// is small and stable; it plays the role the viewport plays for a lattice.

function sequenceAlphabet(trajectory) {
  const symbols = new Set();
  for (const frame of trajectory) {
    for (const s of sequenceSymbols(frame, SYMBOL_FIELD)) symbols.add(s);
  }
  return [...symbols].sort();
}

// --- Projections of one frame against the alphabet --------------------------

function spatialMarks(frame, alphabet) {
  const row = new Map(alphabet.map((s, i) => [s, i]));
  return sequenceSymbols(frame, SYMBOL_FIELD)
    .map((s, x) => ({ x, y: row.get(s) }))
    .filter((m) => m.y !== undefined);
}

function sonicVoices(frame, alphabet) {
  return spatialMarks(frame, alphabet).map((m) => ({ step: m.x, pitchRow: m.y }));
}

// --- Spatial surface: a piano-roll of position x symbol ----------------------

function drawSpatial(canvas, frame, alphabet, maxLength) {
  const ctx = canvas.getContext("2d");
  const rows = Math.max(alphabet.length, 1);
  const cols = Math.max(maxLength, 1);
  const cell = Math.max(
    2,
    Math.floor(Math.min(canvas.width / cols, canvas.height / rows)),
  );
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "rgba(255,255,255,0.06)";
  for (let r = 0; r <= rows; r += 1) {
    ctx.beginPath();
    ctx.moveTo(0, r * cell);
    ctx.lineTo(cols * cell, r * cell);
    ctx.stroke();
  }
  ctx.fillStyle = "#5ad1ff";
  for (const { x, y } of spatialMarks(frame, alphabet)) {
    // Highest alphabet row drawn at the top, like the sonic pitch axis.
    const drawY = alphabet.length - 1 - y;
    ctx.fillRect(x * cell + 1, drawY * cell + 1, cell - 2, cell - 2);
  }
  // Label the pitch rows with their symbol.
  ctx.fillStyle = "rgba(232,238,252,0.55)";
  ctx.font = "12px system-ui, sans-serif";
  alphabet.forEach((symbol, i) => {
    ctx.fillText(String(symbol), 4, (alphabet.length - 1 - i) * cell + cell - 4);
  });
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
      const span = Math.min(0.7, voices.length * 0.06);
      for (const { step, pitchRow } of voices) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        // Read the word left to right as a melody over the frame's duration.
        const t = now + (step / Math.max(voices.length, 1)) * span;
        osc.type = "triangle";
        osc.frequency.value = pitchToHz(pitchRow);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.12, t + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.14);
      }
    },
    resume() {
      ensure().resume();
    },
  };
}

// --- Orchestration ----------------------------------------------------------

export async function boot(opts = {}) {
  const {
    manifestUrl = "./program.lsystem.v1.json",
    steps = 5,
    canvas = document.getElementById("spatial"),
    status = document.getElementById("status"),
    soundToggle = document.getElementById("sound"),
  } = opts;

  const core = await fetch(manifestUrl, { cache: "no-store" }).then((r) => r.json());
  if (core.kind !== "semantic-core-v1") {
    throw new Error(`expected semantic-core-v1, got ${core.kind}`);
  }
  if (core.schedule.kind !== SCHEDULE_GENERATIVE) {
    throw new Error(`expected a generative program, got ${core.schedule.kind}`);
  }

  // The single source of motion: one stepper, one trajectory of words. Both
  // modalities read the word out of each frame -- neither rewrites it. The
  // alphabet (pitch axis) is computed once from the whole trajectory so a
  // symbol's row never moves as the string grows.
  const trajectory = run(core, steps);
  const alphabet = sequenceAlphabet(trajectory);
  const maxLength = Math.max(
    ...trajectory.map((f) => sequenceSymbols(f, SYMBOL_FIELD).length),
    1,
  );
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
    drawSpatial(canvas, frame, alphabet, maxLength);
    const voices = sonicVoices(frame, alphabet);
    if (soundOn) sonic.playFrame(voices);
    if (status) {
      const word = sequenceSymbols(frame, SYMBOL_FIELD).join("");
      status.textContent =
        `generation ${i % trajectory.length} / ${trajectory.length - 1} — ` +
        `${word.length} symbols: ${word}`;
    }
    i += 1;
  }

  tick();
  setInterval(tick, STEP_MS);
}

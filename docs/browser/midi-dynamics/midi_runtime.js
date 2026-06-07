// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// MIDI browser runtime.
//
// Peer of the linear/spatial/volumetric/sonic runtimes. Consumes a
// midi-seed-v0 manifest and renders events as a piano-roll-style
// visualization on canvas. The "Out" button optionally enables Web
// MIDI output -- when on, the runtime sends note-on/note-off, control
// change, and program change messages to the first available MIDI
// output port so users with a connected synth can hear the program.
// Without a MIDI output, the runtime falls back to a tiny WebAudio
// synth so the page is audible on localhost with no external hardware.
//
// The "In" button captures incoming MIDI from the first available
// MIDI input device for one bar, runs the inverse projection from
// sonic_capture's MIDI peer (midi_capture.js), and renders the
// recovered semantic-core manifest in a DOM panel. This makes the
// MIDI round-trip claim user-visible.

import {
  loadOntology,
  observeEvent,
  captureSemanticCore,
} from "./midi_capture.js";

const MANIFEST_KIND = "midi-seed-v0";
const DEFAULT_BAR_SECONDS = 4.0;

const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const midiOutButton = document.getElementById("midiout");
const midiInButton = document.getElementById("midiin");
const recoveredPanel = document.getElementById("recovered");
const roll = document.getElementById("roll");
const ctx = roll.getContext("2d");
const palette = document.querySelector(".palette");

let manifest = null;
let running = false;
let cursor = 0;
let lastTick = performance.now();
let midiAccess = null;
let midiOutput = null;
let activeNotes = new Set(); // pitch|channel keys for note-offs
let audioContext = null;
let masterGain = null;
let capturing = false;

async function loadMidiManifest() {
  const response = await fetch("./program.midi.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`program.midi.json ${response.status}`);
  }
  const data = await response.json();
  if (data.kind !== MANIFEST_KIND || !Array.isArray(data.events)) {
    throw new Error("invalid midi manifest");
  }
  manifest = data;
}

function resizeRoll() {
  const scale = window.devicePixelRatio || 1;
  roll.width = Math.floor(window.innerWidth * scale);
  roll.height = Math.floor(window.innerHeight * scale);
  roll.style.width = `${window.innerWidth}px`;
  roll.style.height = `${window.innerHeight}px`;
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
}

async function start() {
  if (running || !manifest) return;
  await ensureAudio();
  running = true;
  cursor = 0;
  lastTick = performance.now();
  startButton.setAttribute("aria-pressed", "true");
  stopButton.setAttribute("aria-pressed", "false");
}

function stop() {
  if (!running) return;
  running = false;
  cursor = 0;
  startButton.setAttribute("aria-pressed", "false");
  stopButton.setAttribute("aria-pressed", "true");
  releaseAllNotes();
}

async function toggleMidiOut() {
  const wantOn = midiOutButton.getAttribute("aria-pressed") !== "true";
  if (!wantOn) {
    releaseAllNotes();
    midiOutput = null;
    midiOutButton.setAttribute("aria-pressed", "false");
    return;
  }
  if (!navigator.requestMIDIAccess) {
    midiOutButton.setAttribute("aria-pressed", "false");
    return;
  }
  try {
    if (!midiAccess) {
      midiAccess = await navigator.requestMIDIAccess({ sysex: false });
    }
    const outputs = Array.from(midiAccess.outputs.values());
    midiOutput = outputs[0] || null;
    midiOutButton.setAttribute("aria-pressed", midiOutput ? "true" : "false");
  } catch (_err) {
    midiOutButton.setAttribute("aria-pressed", "false");
  }
}

function sendEvent(event) {
  const ch = Math.max(0, Math.min(15, event.channel)) & 0x0f;
  if (midiOutput) {
    if (event.role === "note") {
      midiOutput.send([0x90 | ch, event.pitch & 0x7f, event.velocity & 0x7f]);
      activeNotes.add(`${event.pitch}|${ch}`);
    } else if (event.role === "drum") {
      midiOutput.send([0x99, event.pitch & 0x7f, event.velocity & 0x7f]); // channel 10
      activeNotes.add(`${event.pitch}|9`);
    } else if (event.role === "cc") {
      midiOutput.send([0xb0 | ch, event.pitch & 0x7f, event.velocity & 0x7f]);
    } else if (event.role === "program") {
      midiOutput.send([0xc0 | ch, event.pitch & 0x7f]);
    }
  } else {
    playWebAudioEvent(event);
  }
}

function releaseAllNotes() {
  if (!midiOutput) {
    activeNotes.clear();
    return;
  }
  for (const key of activeNotes) {
    const [pitch, ch] = key.split("|").map((s) => parseInt(s, 10));
    midiOutput.send([0x80 | (ch & 0x0f), pitch & 0x7f, 0]);
  }
  activeNotes.clear();
}

function eventFill(event) {
  if (event.role === "note") return "#3a86ff";
  if (event.role === "drum") return "#fb5607";
  if (event.role === "cc") return "#8338ec";
  if (event.role === "program") return "#ffbe0b";
  return "rgba(241, 239, 228, 0.18)"; // bus
}

async function ensureAudio() {
  if (!audioContext) {
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtor) return;
    audioContext = new AudioCtor();
    masterGain = audioContext.createGain();
    masterGain.gain.value = 0.22;
    masterGain.connect(audioContext.destination);
  }
  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }
}

function midiToFrequency(pitch) {
  return 440 * Math.pow(2, (pitch - 69) / 12);
}

function playWebAudioEvent(event) {
  if (!audioContext || !masterGain || event.role === "bus") return;
  if (event.role === "drum") {
    playNoiseHit(event);
    return;
  }

  const now = audioContext.currentTime;
  const osc = audioContext.createOscillator();
  const gain = audioContext.createGain();
  const velocity = Math.max(0.05, Math.min(1, event.velocity / 127));
  const duration = event.role === "cc" ? 0.16 : 0.32;

  osc.type = event.role === "program" ? "triangle" : "sine";
  osc.frequency.value = event.role === "cc"
    ? midiToFrequency(48 + (event.pitch % 24))
    : midiToFrequency(event.pitch);

  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.28 * velocity, now + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(now);
  osc.stop(now + duration + 0.02);
}

function playNoiseHit(event) {
  const now = audioContext.currentTime;
  const length = Math.max(1, Math.floor(audioContext.sampleRate * 0.12));
  const buffer = audioContext.createBuffer(1, length, audioContext.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < length; i += 1) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / length);
  }
  const source = audioContext.createBufferSource();
  const gain = audioContext.createGain();
  const velocity = Math.max(0.05, Math.min(1, event.velocity / 127));
  source.buffer = buffer;
  gain.gain.setValueAtTime(0.3 * velocity, now);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
  source.connect(gain);
  gain.connect(masterGain);
  source.start(now);
  source.stop(now + 0.14);
}

function draw() {
  const now = performance.now();
  const dt = (now - lastTick) / 1000;
  lastTick = now;

  const width = window.innerWidth;
  const height = window.innerHeight;
  ctx.clearRect(0, 0, width, height);

  // Pitch axis baseline gridlines (octaves of C).
  ctx.strokeStyle = "rgba(241, 239, 228, 0.08)";
  ctx.lineWidth = 1;
  const minPitch = 24;
  const maxPitch = 96;
  const pitchToY = (p) =>
    height - 60 - ((p - minPitch) / (maxPitch - minPitch)) * (height - 120);
  for (let p = minPitch; p <= maxPitch; p += 12) {
    const y = pitchToY(p);
    ctx.beginPath();
    ctx.moveTo(40, y);
    ctx.lineTo(width - 40, y);
    ctx.stroke();
  }

  if (!manifest) {
    requestAnimationFrame(draw);
    return;
  }

  const usableWidth = width - 80;
  const noteWidth = Math.max(12, usableWidth / 16);
  const eventHeight = Math.max(8, (height - 120) / (maxPitch - minPitch));

  for (const event of manifest.events) {
    const x = 40 + event.start_offset * usableWidth;
    const pitch = Math.max(minPitch, Math.min(maxPitch, event.pitch));
    const y = pitchToY(pitch);
    ctx.fillStyle = eventFill(event);
    const alpha = event.role === "bus"
      ? 0.4
      : 0.35 + 0.55 * (event.velocity / 127);
    ctx.globalAlpha = alpha;
    if (event.role === "program") {
      ctx.fillRect(x - 2, 24, 4, height - 144);
    } else if (event.role === "cc") {
      ctx.fillRect(x, y - 2, noteWidth, 4);
    } else {
      ctx.fillRect(x, y - eventHeight / 2, noteWidth, eventHeight);
    }
    ctx.globalAlpha = 1;
  }

  if (running) {
    const bar = manifest.bar_seconds || 4;
    const previousCursor = cursor;
    cursor = (cursor + dt / bar) % 1;
    // Fire events whose start_offset falls within [previousCursor, cursor).
    // Treat cursor wrap as an interval ending at 1 then 0..cursor.
    // sendEvent chooses Web MIDI when available, otherwise WebAudio fallback.
    for (const event of manifest.events) {
      const sent = previousCursor <= cursor
        ? event.start_offset >= previousCursor && event.start_offset < cursor
        : event.start_offset >= previousCursor || event.start_offset < cursor;
      if (sent) sendEvent(event);
    }
    const cx = 40 + cursor * usableWidth;
    ctx.strokeStyle = "rgba(247, 201, 72, 0.7)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx, 24);
    ctx.lineTo(cx, height - 40);
    ctx.stroke();
  }

  requestAnimationFrame(draw);
}

async function captureFromMidiIn() {
  if (capturing) return;
  capturing = true;
  midiInButton.setAttribute("aria-pressed", "true");
  const cleanup = [];
  try {
    if (!navigator.requestMIDIAccess) {
      throw new Error("Web MIDI not available in this browser");
    }
    if (!midiAccess) {
      midiAccess = await navigator.requestMIDIAccess({ sysex: false });
    }
    const inputs = Array.from(midiAccess.inputs.values());
    if (inputs.length === 0) {
      throw new Error("No Web MIDI input ports available");
    }
    const ontology = await loadOntology();
    const events = [];
    const startedAt = performance.now();
    const barSeconds = (manifest && manifest.bar_seconds) || DEFAULT_BAR_SECONDS;

    const onMessage = (message) => {
      const [status, data1, data2 = 0] = message.data;
      const elapsed = (performance.now() - startedAt) / 1000;
      if (elapsed > barSeconds) return;
      const startOffset = Math.max(0, Math.min(0.9999, elapsed / barSeconds));
      const event = decodeStatus(status, data1, data2, events.length, startOffset);
      if (event) events.push(event);
    };
    for (const port of inputs) {
      port.addEventListener("midimessage", onMessage);
      cleanup.push(() => port.removeEventListener("midimessage", onMessage));
    }

    await new Promise((resolve) => setTimeout(resolve, barSeconds * 1000));

    const observed = events.map((event) => observeEvent(event));
    const core = captureSemanticCore(observed, ontology, {
      sourceLanguage: "en",
      sourcePath: "<web-midi-in>",
    });
    renderRecovered(core);
  } catch (err) {
    renderRecovered({ error: String(err && err.message ? err.message : err) });
  } finally {
    for (const fn of cleanup) {
      try { fn(); } catch (_e) { /* ignore */ }
    }
    capturing = false;
    midiInButton.setAttribute("aria-pressed", "false");
  }
}

function decodeStatus(status, data1, data2, index, startOffset) {
  // Strip channel bits to identify the message kind, then derive an
  // ObservedMidiEvent compatible with midi_capture.observeEvent. The
  // role assignments mirror the forward MidiHint taxonomy.
  const type = status & 0xf0;
  const channel = status & 0x0f;
  if (type === 0x90 && data2 > 0) {
    return {
      index,
      role: channel === 9 ? "drum" : "note",
      pitch: data1,
      velocity: data2,
      channel,
      start_offset: startOffset,
    };
  }
  if (type === 0xb0) {
    return {
      index,
      role: "cc",
      pitch: data1,
      velocity: data2,
      channel,
      start_offset: startOffset,
    };
  }
  if (type === 0xc0) {
    return {
      index,
      role: "program",
      pitch: data1,
      velocity: 0,
      channel,
      start_offset: startOffset,
    };
  }
  return null;
}

function renderRecovered(payload) {
  if (!recoveredPanel) return;
  recoveredPanel.hidden = false;
  recoveredPanel.textContent = JSON.stringify(payload, null, 2);
}

palette.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "start") {
    start();
  } else if (button.dataset.action === "stop") {
    stop();
  } else if (button.dataset.action === "midiout") {
    toggleMidiOut();
  } else if (button.dataset.action === "midiin") {
    captureFromMidiIn();
  }
});

window.addEventListener("resize", resizeRoll);

loadMidiManifest()
  .catch(() => {
    manifest = null;
  })
  .finally(() => {
    resizeRoll();
    requestAnimationFrame(draw);
  });

// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Linear (1D timeline) browser runtime.
//
// Peer of sonic_runtime.js and spatial_runtime.js. Consumes a
// linear-seed-v0 manifest and renders each mark at its position along
// a single horizontal axis. Channel drives the vertical lane so
// multi-channel programs don't pile up at the same point.

const MANIFEST_KIND = "linear-seed-v0";

const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const strip = document.getElementById("strip");
const stripCtx = strip.getContext("2d");
const palette = document.querySelector(".palette");

let manifest = null;
let running = false;
let cursor = 0; // [0..1] sweep position
let lastTick = performance.now();

async function loadLinearManifest() {
  const response = await fetch("./program.linear.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`program.linear.json ${response.status}`);
  }
  const data = await response.json();
  if (data.kind !== MANIFEST_KIND || !Array.isArray(data.marks)) {
    throw new Error("invalid linear manifest");
  }
  manifest = data;
}

function resizeStrip() {
  const scale = window.devicePixelRatio || 1;
  strip.width = Math.floor(window.innerWidth * scale);
  strip.height = Math.floor(window.innerHeight * scale);
  strip.style.width = `${window.innerWidth}px`;
  strip.style.height = `${window.innerHeight}px`;
  stripCtx.setTransform(scale, 0, 0, scale, 0, 0);
}

function start() {
  if (running || !manifest) return;
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
}

function laneFor(channel, lanes) {
  const total = Math.max(1, lanes);
  return (channel + 0.5) / total;
}

function drawGlyph(glyph, x, y, size, intensity, color) {
  const alpha = Math.max(0.25, Math.min(1, intensity));
  stripCtx.strokeStyle = color;
  stripCtx.fillStyle = color;
  stripCtx.globalAlpha = alpha;
  stripCtx.lineWidth = 2;

  switch (glyph) {
    case "dot":
      stripCtx.beginPath();
      stripCtx.arc(x, y, size * 0.35, 0, Math.PI * 2);
      stripCtx.fill();
      break;
    case "segment":
      stripCtx.fillRect(x - size * 0.6, y - size * 0.18, size * 1.2, size * 0.36);
      break;
    case "pulse":
      stripCtx.fillRect(x - size * 0.12, y - size * 0.6, size * 0.24, size * 1.2);
      break;
    case "ramp":
      stripCtx.beginPath();
      stripCtx.moveTo(x - size * 0.6, y + size * 0.45);
      stripCtx.lineTo(x + size * 0.6, y - size * 0.45);
      stripCtx.lineTo(x + size * 0.6, y + size * 0.45);
      stripCtx.closePath();
      stripCtx.fill();
      break;
    case "fall":
      stripCtx.beginPath();
      stripCtx.moveTo(x - size * 0.6, y - size * 0.45);
      stripCtx.lineTo(x + size * 0.6, y + size * 0.45);
      stripCtx.lineTo(x - size * 0.6, y + size * 0.45);
      stripCtx.closePath();
      stripCtx.fill();
      break;
    case "wave":
      stripCtx.beginPath();
      for (let i = 0; i <= 12; i += 1) {
        const t = i / 12;
        const wx = x + (t - 0.5) * size * 1.2;
        const wy = y + Math.sin(t * Math.PI * 4) * size * 0.35;
        if (i === 0) stripCtx.moveTo(wx, wy); else stripCtx.lineTo(wx, wy);
      }
      stripCtx.stroke();
      break;
    case "double":
      stripCtx.beginPath();
      stripCtx.arc(x - size * 0.25, y, size * 0.22, 0, Math.PI * 2);
      stripCtx.arc(x + size * 0.25, y, size * 0.22, 0, Math.PI * 2);
      stripCtx.fill();
      break;
    case "fork":
      stripCtx.beginPath();
      stripCtx.moveTo(x - size * 0.5, y);
      stripCtx.lineTo(x, y);
      stripCtx.lineTo(x + size * 0.45, y - size * 0.4);
      stripCtx.moveTo(x, y);
      stripCtx.lineTo(x + size * 0.45, y + size * 0.4);
      stripCtx.stroke();
      break;
    case "join":
      stripCtx.beginPath();
      stripCtx.moveTo(x - size * 0.45, y - size * 0.4);
      stripCtx.lineTo(x, y);
      stripCtx.lineTo(x - size * 0.45, y + size * 0.4);
      stripCtx.moveTo(x, y);
      stripCtx.lineTo(x + size * 0.5, y);
      stripCtx.stroke();
      break;
    case "band": {
      const previousAlpha = stripCtx.globalAlpha;
      stripCtx.globalAlpha = alpha * 0.35;
      stripCtx.fillRect(x - size * 0.9, y - size * 0.45, size * 1.8, size * 0.9);
      stripCtx.globalAlpha = previousAlpha;
      break;
    }
    case "shift":
      stripCtx.beginPath();
      stripCtx.moveTo(x - size * 0.55, y - size * 0.35);
      stripCtx.lineTo(x + size * 0.55, y);
      stripCtx.lineTo(x - size * 0.55, y + size * 0.35);
      stripCtx.closePath();
      stripCtx.fill();
      break;
    default:
      stripCtx.beginPath();
      stripCtx.arc(x, y, size * 0.3, 0, Math.PI * 2);
      stripCtx.fill();
  }
  stripCtx.globalAlpha = 1;
}

function draw() {
  const now = performance.now();
  const dt = (now - lastTick) / 1000;
  lastTick = now;

  const width = window.innerWidth;
  const height = window.innerHeight;
  stripCtx.clearRect(0, 0, width, height);

  // Time-axis baseline.
  stripCtx.strokeStyle = "rgba(241, 239, 228, 0.12)";
  stripCtx.lineWidth = 1;
  stripCtx.beginPath();
  stripCtx.moveTo(40, height / 2);
  stripCtx.lineTo(width - 40, height / 2);
  stripCtx.stroke();

  if (!manifest) {
    requestAnimationFrame(draw);
    return;
  }

  const channelCount = Math.max(
    1,
    ...manifest.marks.map((m) => m.channel + 1),
  );
  const usableWidth = width - 80;
  const size = Math.min(48, Math.max(18, height / (channelCount + 4)));

  for (const mark of manifest.marks) {
    const x = 40 + mark.position * usableWidth;
    const y = laneFor(mark.channel, channelCount) * height;
    drawGlyph(mark.glyph, x, y, size, mark.intensity, mark.color);
  }

  if (running) {
    const bar = manifest.bar_seconds || 4;
    cursor = (cursor + dt / bar) % 1;
    const cx = 40 + cursor * usableWidth;
    stripCtx.strokeStyle = "rgba(247, 201, 72, 0.7)";
    stripCtx.lineWidth = 2;
    stripCtx.beginPath();
    stripCtx.moveTo(cx, 16);
    stripCtx.lineTo(cx, height - 16);
    stripCtx.stroke();
  }

  requestAnimationFrame(draw);
}

palette.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "start") {
    start();
  } else if (button.dataset.action === "stop") {
    stop();
  }
});

window.addEventListener("resize", resizeStrip);

loadLinearManifest()
  .catch(() => {
    manifest = null;
  })
  .finally(() => {
    resizeStrip();
    requestAnimationFrame(draw);
  });

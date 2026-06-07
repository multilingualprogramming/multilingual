// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Volumetric (3D) browser runtime.
//
// Peer of linear_runtime.js, spatial_runtime.js, and sonic_runtime.js.
// Consumes a volumetric-seed-v0 manifest and renders each mark as a
// 3D primitive positioned in a rotating scene. The 3D math is hand-
// rolled (single Y-axis rotation, orthographic + light perspective);
// no WebGL or library deps, matching the existing runtimes' stance.
//
// x is derived from index (horizontal axis), y from channel (vertical
// axis), z from the manifest field (depth = phase). The whole scene
// rotates around the Y axis when playing so depth and primitive shape
// become visually apparent.

const MANIFEST_KIND = "volumetric-seed-v0";

const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const volume = document.getElementById("volume");
const ctx = volume.getContext("2d");
const palette = document.querySelector(".palette");

let manifest = null;
let running = false;
let theta = 0.4;
let lastTick = performance.now();

async function loadVolumetricManifest() {
  const response = await fetch("./program.volumetric.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`program.volumetric.json ${response.status}`);
  }
  const data = await response.json();
  if (data.kind !== MANIFEST_KIND || !Array.isArray(data.marks)) {
    throw new Error("invalid volumetric manifest");
  }
  manifest = data;
}

function resizeVolume() {
  const scale = window.devicePixelRatio || 1;
  volume.width = Math.floor(window.innerWidth * scale);
  volume.height = Math.floor(window.innerHeight * scale);
  volume.style.width = `${window.innerWidth}px`;
  volume.style.height = `${window.innerHeight}px`;
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
}

function start() {
  if (running || !manifest) return;
  running = true;
  lastTick = performance.now();
  startButton.setAttribute("aria-pressed", "true");
  stopButton.setAttribute("aria-pressed", "false");
}

function stop() {
  if (!running) return;
  running = false;
  startButton.setAttribute("aria-pressed", "false");
  stopButton.setAttribute("aria-pressed", "true");
}

function project(x, y, z, width, height) {
  // x, y, z are in scene-space roughly [-1, 1]. Rotate around Y axis
  // then apply a mild perspective so depth is readable.
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);
  const rx = x * cos - z * sin;
  const rz = x * sin + z * cos;
  const persp = 1 / (1.8 - rz * 0.5);
  return {
    sx: width / 2 + rx * width * 0.3 * persp,
    sy: height / 2 + y * height * 0.35 * persp,
    scale: persp,
    depth: rz,
  };
}

function drawPrimitive(primitive, p, size, intensity, color) {
  const baseSize = size * p.scale * Math.max(0.4, Math.min(1, intensity));
  const alpha = Math.max(0.3, Math.min(1, intensity * (0.5 + p.depth * 0.5)));
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.globalAlpha = alpha;
  ctx.lineWidth = 1.5;
  const { sx, sy } = p;

  switch (primitive) {
    case "point":
      ctx.beginPath();
      ctx.arc(sx, sy, baseSize * 0.25, 0, Math.PI * 2);
      ctx.fill();
      break;
    case "cloud":
      for (let i = 0; i < 7; i += 1) {
        const a = (i / 7) * Math.PI * 2;
        const r = baseSize * (0.3 + 0.4 * Math.sin(i * 2.13));
        ctx.beginPath();
        ctx.arc(sx + Math.cos(a) * r, sy + Math.sin(a) * r * 0.6,
                baseSize * 0.12, 0, Math.PI * 2);
        ctx.fill();
      }
      break;
    case "cone":
      ctx.beginPath();
      ctx.moveTo(sx, sy - baseSize * 0.55);
      ctx.lineTo(sx - baseSize * 0.45, sy + baseSize * 0.45);
      ctx.lineTo(sx + baseSize * 0.45, sy + baseSize * 0.45);
      ctx.closePath();
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(sx, sy + baseSize * 0.45, baseSize * 0.45,
                  baseSize * 0.12, 0, 0, Math.PI * 2);
      ctx.stroke();
      break;
    case "burst":
      for (let i = 0; i < 8; i += 1) {
        const a = (i / 8) * Math.PI * 2;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + Math.cos(a) * baseSize * 0.6,
                   sy + Math.sin(a) * baseSize * 0.6);
        ctx.stroke();
      }
      break;
    case "cube": {
      const s = baseSize * 0.4;
      // Front face
      ctx.strokeRect(sx - s, sy - s, s * 2, s * 2);
      // Back face offset
      const o = s * 0.4;
      ctx.strokeRect(sx - s + o, sy - s - o, s * 2, s * 2);
      // Connecting edges
      ctx.beginPath();
      ctx.moveTo(sx - s, sy - s); ctx.lineTo(sx - s + o, sy - s - o);
      ctx.moveTo(sx + s, sy - s); ctx.lineTo(sx + s + o, sy - s - o);
      ctx.moveTo(sx - s, sy + s); ctx.lineTo(sx - s + o, sy + s - o);
      ctx.moveTo(sx + s, sy + s); ctx.lineTo(sx + s + o, sy + s - o);
      ctx.stroke();
      break;
    }
    case "helix":
      ctx.beginPath();
      for (let i = 0; i <= 24; i += 1) {
        const t = i / 24;
        const hx = sx + Math.cos(t * Math.PI * 4) * baseSize * 0.4;
        const hy = sy - baseSize * 0.55 + t * baseSize * 1.1;
        if (i === 0) ctx.moveTo(hx, hy); else ctx.lineTo(hx, hy);
      }
      ctx.stroke();
      break;
    case "twist":
      ctx.beginPath();
      for (let i = 0; i <= 30; i += 1) {
        const t = i / 30;
        const r = baseSize * 0.5 * (1 - t);
        const a = t * Math.PI * 4;
        const tx = sx + Math.cos(a) * r;
        const ty = sy + Math.sin(a) * r;
        if (i === 0) ctx.moveTo(tx, ty); else ctx.lineTo(tx, ty);
      }
      ctx.stroke();
      break;
    case "shell":
      for (let i = 1; i <= 3; i += 1) {
        ctx.beginPath();
        ctx.ellipse(sx, sy, baseSize * 0.15 * i, baseSize * 0.45 * i / 3,
                    0, 0, Math.PI * 2);
        ctx.stroke();
      }
      break;
    case "branch": {
      ctx.beginPath();
      ctx.moveTo(sx, sy + baseSize * 0.55);
      ctx.lineTo(sx, sy);
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx - baseSize * 0.5, sy - baseSize * 0.45);
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx + baseSize * 0.5, sy - baseSize * 0.45);
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx, sy - baseSize * 0.5);
      ctx.stroke();
      break;
    }
    case "funnel":
      ctx.beginPath();
      ctx.moveTo(sx - baseSize * 0.55, sy - baseSize * 0.45);
      ctx.lineTo(sx + baseSize * 0.55, sy - baseSize * 0.45);
      ctx.lineTo(sx + baseSize * 0.12, sy + baseSize * 0.45);
      ctx.lineTo(sx - baseSize * 0.12, sy + baseSize * 0.45);
      ctx.closePath();
      ctx.fill();
      break;
    case "cell": {
      ctx.beginPath();
      const previousAlpha = ctx.globalAlpha;
      ctx.globalAlpha = alpha * 0.35;
      for (let i = 0; i <= 6; i += 1) {
        const a = (i / 6) * Math.PI * 2;
        const cx = sx + Math.cos(a) * baseSize * 0.6;
        const cy = sy + Math.sin(a) * baseSize * 0.6;
        if (i === 0) ctx.moveTo(cx, cy); else ctx.lineTo(cx, cy);
      }
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = previousAlpha;
      ctx.stroke();
      break;
    }
    case "flow": {
      ctx.beginPath();
      ctx.moveTo(sx - baseSize * 0.55, sy);
      ctx.lineTo(sx + baseSize * 0.35, sy);
      ctx.moveTo(sx + baseSize * 0.55, sy);
      ctx.lineTo(sx + baseSize * 0.25, sy - baseSize * 0.25);
      ctx.moveTo(sx + baseSize * 0.55, sy);
      ctx.lineTo(sx + baseSize * 0.25, sy + baseSize * 0.25);
      ctx.stroke();
      break;
    }
    default:
      ctx.beginPath();
      ctx.arc(sx, sy, baseSize * 0.3, 0, Math.PI * 2);
      ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function draw() {
  const now = performance.now();
  const dt = (now - lastTick) / 1000;
  lastTick = now;

  const width = window.innerWidth;
  const height = window.innerHeight;
  ctx.clearRect(0, 0, width, height);

  // Subtle reference axes through the origin so depth is readable.
  drawReferenceAxes(width, height);

  if (!manifest) {
    requestAnimationFrame(draw);
    return;
  }

  if (running) {
    theta += dt * 0.4;
  }

  const total = manifest.marks.length || 1;
  const channelCount = Math.max(
    1,
    ...manifest.marks.map((m) => m.channel + 1),
  );
  const baseSize = Math.min(120, Math.max(40, Math.min(width, height) / 8));

  // Sort by depth so far primitives draw behind near ones.
  const projected = manifest.marks.map((mark, i) => {
    const x = ((mark.index + 0.5) / total) * 2 - 1;
    const y = ((mark.channel + 0.5) / channelCount) * 2 - 1;
    const z = mark.z * 2 - 1;
    return { mark, point: project(x, y, z, width, height) };
  });
  projected.sort((a, b) => a.point.depth - b.point.depth);

  for (const { mark, point } of projected) {
    drawPrimitive(mark.primitive, point, baseSize, mark.intensity, mark.color);
  }

  requestAnimationFrame(draw);
}

function drawReferenceAxes(width, height) {
  ctx.strokeStyle = "rgba(241, 239, 228, 0.08)";
  ctx.lineWidth = 1;
  for (const [ax, ay, az] of [
    [-1, 0, 0], [1, 0, 0],
    [0, -1, 0], [0, 1, 0],
    [0, 0, -1], [0, 0, 1],
  ]) {
    const a = project(0, 0, 0, width, height);
    const b = project(ax, ay, az, width, height);
    ctx.beginPath();
    ctx.moveTo(a.sx, a.sy);
    ctx.lineTo(b.sx, b.sy);
    ctx.stroke();
  }
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

window.addEventListener("resize", resizeVolume);

loadVolumetricManifest()
  .catch(() => {
    manifest = null;
  })
  .finally(() => {
    resizeVolume();
    requestAnimationFrame(draw);
  });

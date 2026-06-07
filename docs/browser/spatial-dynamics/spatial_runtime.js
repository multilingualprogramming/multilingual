import {
  loadOntology,
  observeMark,
  captureSemanticCore,
} from "./spatial_capture.js";

const BEHAVIOR = Object.freeze({
  EMIT: 1,
  DIFFUSE: 2,
  ATTRACT: 3,
  REPEL: 4,
  STABILIZE: 5,
  OSCILLATE: 6,
  TRANSFORM: 7,
  RESONATE: 8,
  SPLIT: 9,
  MERGE: 10,
  CONTAIN: 11,
  PROPAGATE: 12,
});

const VISUAL = Object.freeze({
  1: { color: "#de3c4b", shape: "source" },
  2: { color: "#3a86ff", shape: "ring" },
  3: { color: "#2d6a4f", shape: "up" },
  4: { color: "#f77f00", shape: "down" },
  5: { color: "#6c757d", shape: "square" },
  6: { color: "#8338ec", shape: "phase" },
  7: { color: "#00a896", shape: "diamond" },
  8: { color: "#ffbe0b", shape: "double" },
  9: { color: "#fb5607", shape: "split" },
  10: { color: "#7209b7", shape: "merge" },
  11: { color: "#252422", shape: "membrane" },
  12: { color: "#0077b6", shape: "arrow" },
});

const EDIT_SOURCE_PATH = "<spatial-edit>";
let entitySequence = 0;

// Mirrors semantic_core.stable_entity_id: SHA-256 of `source_path|seq`,
// first 8 hex chars, "ent_" prefix. Used for entities created by the
// editor (palette add, simulation-spawned children) that need a stable
// identifier before capture serializes them.
async function makeAuthoredId() {
  const seq = entitySequence;
  entitySequence += 1;
  const data = new TextEncoder().encode(`${EDIT_SOURCE_PATH}|${seq}`);
  const digest = await crypto.subtle.digest("SHA-256", data);
  const bytes = new Uint8Array(digest);
  let hex = "";
  for (let i = 0; i < 4; i += 1) {
    hex += bytes[i].toString(16).padStart(2, "0");
  }
  return `ent_${hex}`;
}

class Entity {
  constructor(behavior, x, y, options = {}) {
    this.behavior = behavior;
    this.x = x;
    this.y = y;
    this.radius = options.radius ?? 28;
    this.intensity = options.intensity ?? 1;
    this.signal = options.signal ?? 0;
    this.vx = options.vx ?? 0;
    this.vy = options.vy ?? 0;
    this.phase = options.phase ?? 0;
    this.channel = options.channel ?? 0;
    this.id = options.id ?? null;
  }

  clone(overrides = {}) {
    return Object.assign(new Entity(this.behavior, this.x, this.y), this, overrides);
  }
}

class World {
  constructor(width, height) {
    this.width = width;
    this.height = height;
    this.entities = [];
    this.time = 0;
  }

  seed() {
    this.entities = [
      new Entity(BEHAVIOR.CONTAIN, this.width * 0.5, this.height * 0.5, { radius: 230 }),
      new Entity(BEHAVIOR.EMIT, this.width * 0.32, this.height * 0.5, {
        radius: 70,
        intensity: 0.42,
      }),
      new Entity(BEHAVIOR.DIFFUSE, this.width * 0.43, this.height * 0.48, {
        radius: 92,
      }),
      new Entity(BEHAVIOR.TRANSFORM, this.width * 0.54, this.height * 0.5, {
        radius: 86,
        intensity: 0.08,
      }),
      new Entity(BEHAVIOR.SPLIT, this.width * 0.64, this.height * 0.5, {
        radius: 80,
        intensity: 1.4,
      }),
      new Entity(BEHAVIOR.OSCILLATE, this.width * 0.5, this.height * 0.36, {
        radius: 80,
        intensity: 0.16,
      }),
      new Entity(BEHAVIOR.RESONATE, this.width * 0.5, this.height * 0.64, {
        radius: 94,
      }),
      new Entity(BEHAVIOR.ATTRACT, this.width * 0.74, this.height * 0.42, {
        radius: 150,
        intensity: 0.08,
      }),
      new Entity(BEHAVIOR.REPEL, this.width * 0.74, this.height * 0.58, {
        radius: 130,
        intensity: 0.06,
      }),
    ];
  }

  seedFromRows(entities) {
    this.entities = entities.map((row) => new Entity(
      row.opcode,
      row.x_ratio * this.width,
      row.y_ratio * this.height,
      {
        radius: row.radius,
        intensity: row.intensity,
        signal: row.signal,
        vx: row.vx,
        vy: row.vy,
        phase: row.phase,
        channel: row.channel,
        id: row.id,
      },
    ));
  }

  async add(behavior, x, y) {
    const radius = behavior === BEHAVIOR.CONTAIN ? 120 : 56;
    const intensity = behavior === BEHAVIOR.PROPAGATE ? 2.6 : 1;
    const options = { radius, intensity, id: await makeAuthoredId() };
    if (behavior === BEHAVIOR.PROPAGATE) {
      options.signal = 1;
      options.vx = 1.6;
      options.vy = 0;
    }
    this.entities.push(new Entity(behavior, x, y, options));
  }

  step(dt) {
    const additions = [];
    const containers = this.entities.filter((entity) => entity.behavior === BEHAVIOR.CONTAIN);
    const next = this.entities.map((entity) => {
      let updated = entity;
      if (entity.behavior === BEHAVIOR.EMIT) {
        updated = entity.clone({ signal: entity.signal + entity.intensity * dt });
      } else if (entity.behavior === BEHAVIOR.DIFFUSE) {
        updated = this.diffuse(entity, dt);
      } else if (entity.behavior === BEHAVIOR.ATTRACT) {
        updated = this.moveByField(entity, BEHAVIOR.ATTRACT, dt);
      } else if (entity.behavior === BEHAVIOR.REPEL) {
        updated = this.moveByField(entity, BEHAVIOR.REPEL, dt);
      } else if (entity.behavior === BEHAVIOR.STABILIZE) {
        updated = entity.clone({ signal: entity.signal * Math.max(0, 1 - 0.25 * dt) });
      } else if (entity.behavior === BEHAVIOR.OSCILLATE) {
        updated = this.oscillate(entity, dt);
      } else if (entity.behavior === BEHAVIOR.TRANSFORM) {
        updated = this.transform(entity, dt);
      } else if (entity.behavior === BEHAVIOR.RESONATE) {
        updated = this.resonate(entity, dt);
      } else if (entity.behavior === BEHAVIOR.SPLIT) {
        const result = this.split(entity);
        updated = result.entity;
        additions.push(...result.additions);
      } else if (entity.behavior === BEHAVIOR.MERGE) {
        updated = this.merge(entity);
      } else if (entity.behavior === BEHAVIOR.PROPAGATE) {
        updated = entity.clone({ x: entity.x + entity.vx * dt * 40, y: entity.y + entity.vy * dt * 40 });
      }
      return this.applyContainment(updated, containers);
    });

    this.entities = next.concat(additions).slice(-180);
    this.time += dt;
  }

  neighbors(entity) {
    return this.entities.filter((other) => (
      other !== entity
      && other.channel === entity.channel
      && distance(entity, other) <= entity.radius + other.radius
    ));
  }

  diffuse(entity, dt) {
    const neighbors = this.neighbors(entity);
    if (!neighbors.length) {
      return entity.clone({ signal: entity.signal * Math.max(0, 1 - 0.05 * dt) });
    }
    const average = neighbors.reduce((sum, other) => sum + other.signal, 0) / neighbors.length;
    return entity.clone({ signal: clampSignal(entity.signal + (average - entity.signal) * Math.min(1, 0.5 * dt)) });
  }

  moveByField(entity, fieldBehavior, dt) {
    let dx = 0;
    let dy = 0;
    for (const field of this.entities) {
      if (field === entity || field.behavior !== fieldBehavior) {
        continue;
      }
      const d = Math.max(0.001, distance(entity, field));
      if (d > entity.radius + field.radius) {
        continue;
      }
      let strength = field.intensity / d;
      if (fieldBehavior === BEHAVIOR.REPEL) {
        strength = -strength;
      }
      dx += ((field.x - entity.x) / d) * strength * dt * 100;
      dy += ((field.y - entity.y) / d) * strength * dt * 100;
    }
    return entity.clone({ x: entity.x + dx, y: entity.y + dy });
  }

  oscillate(entity, dt) {
    const phase = (entity.phase + dt * entity.intensity) % 1;
    return entity.clone({
      phase,
      signal: (Math.sin(phase * Math.PI * 2) + 1) / 2,
    });
  }

  transform(entity, dt) {
    const incoming = this.neighbors(entity).reduce((sum, other) => sum + other.signal, 0);
    return entity.clone({ signal: clampSignal(entity.signal + incoming * entity.intensity * dt) });
  }

  resonate(entity, dt) {
    const peers = this.neighbors(entity).filter((other) => other.behavior === BEHAVIOR.OSCILLATE);
    if (!peers.length) {
      return entity;
    }
    const pull = peers.reduce((sum, other) => (
      sum + Math.cos((other.phase - entity.phase) * Math.PI * 2)
    ), 0);
    return entity.clone({ signal: clampSignal(entity.signal + Math.max(0, pull) * 0.1 * dt) });
  }

  split(entity) {
    if (entity.signal < 1) {
      return { entity, additions: [] };
    }
    const signal = entity.signal / 2;
    // Simulation-spawned propagate children: leave id null so capture
    // assigns deterministic IDs at serialization time rather than
    // burning async work into the simulation step.
    return {
      entity: entity.clone({ signal: 0 }),
      additions: [
        entity.clone({ behavior: BEHAVIOR.PROPAGATE, signal, vx: -entity.intensity, vy: 0, id: null }),
        entity.clone({ behavior: BEHAVIOR.PROPAGATE, signal, vx: entity.intensity, vy: 0, id: null }),
      ],
    };
  }

  merge(entity) {
    const signal = this.neighbors(entity).reduce((sum, other) => sum + other.signal, entity.signal);
    return entity.clone({ signal: clampSignal(signal) });
  }

  applyContainment(entity, containers) {
    let x = Math.min(Math.max(entity.x, 0), this.width);
    let y = Math.min(Math.max(entity.y, 0), this.height);
    for (const container of containers) {
      if (container === entity) {
        continue;
      }
      const dx = x - container.x;
      const dy = y - container.y;
      const d = Math.hypot(dx, dy);
      const limit = Math.max(0, container.radius - entity.radius);
      if (d <= container.radius || limit === 0) {
        continue;
      }
      x = container.x + (dx / d) * limit;
      y = container.y + (dy / d) * limit;
    }
    return entity.clone({ x, y });
  }

  entityAt(x, y) {
    // Hit-test from topmost (last drawn) down so newer entities win.
    for (let i = this.entities.length - 1; i >= 0; i -= 1) {
      const entity = this.entities[i];
      if (entity.behavior === BEHAVIOR.CONTAIN) {
        // Containers wrap everything; treat them as draggable only via
        // their border, not their full interior, so they don't hijack
        // every click in the canvas.
        const d = Math.hypot(x - entity.x, y - entity.y);
        if (Math.abs(d - entity.radius) <= 12) {
          return entity;
        }
        continue;
      }
      if (Math.hypot(x - entity.x, y - entity.y) <= Math.max(20, entity.radius * 0.35)) {
        return entity;
      }
    }
    return null;
  }

  moveEntity(entity, x, y) {
    entity.x = x;
    entity.y = y;
  }

  observeAll() {
    // Produce ObservedSpatialMark-shaped records straight from the live
    // world. Index is reassigned to the current array position so the
    // recovered manifest is well-formed even after additions/deletions.
    return this.entities.map((entity, index) => {
      const visual = VISUAL[entity.behavior];
      return observeMark({
        index,
        shape: visual.shape,
        color: visual.color,
        intensity: entity.intensity,
        signal: entity.signal,
        phase: entity.phase,
        channel: entity.channel,
        id: entity.id,
      });
    });
  }
}

const canvas = document.getElementById("world");
const ctx = canvas.getContext("2d");
const toggle = document.getElementById("toggle");
const reset = document.getElementById("reset");
const captureButton = document.getElementById("capture");
const recoveredPanel = document.getElementById("recovered");
const palette = document.querySelector(".palette");
let world = new World(1, 1);
let sourceRows = null;
let selected = BEHAVIOR.EMIT;
let running = true;
let last = performance.now();
let dragging = null;

function resize() {
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.floor(window.innerWidth * scale);
  canvas.height = Math.floor(window.innerHeight * scale);
  canvas.style.width = `${window.innerWidth}px`;
  canvas.style.height = `${window.innerHeight}px`;
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  world.width = window.innerWidth;
  world.height = window.innerHeight;
}

async function loadSpatialManifest() {
  const response = await fetch("./program.spatial.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`program.spatial.json ${response.status}`);
  }
  const manifest = await response.json();
  if (manifest.kind !== "spatial-seed-v0" || !Array.isArray(manifest.entities)) {
    throw new Error("invalid spatial manifest");
  }
  sourceRows = manifest.entities;
}

function restart() {
  resize();
  world = new World(window.innerWidth, window.innerHeight);
  if (sourceRows) {
    world.seedFromRows(sourceRows);
  } else {
    world.seed();
  }
}

function draw() {
  ctx.clearRect(0, 0, world.width, world.height);
  drawFields();
  for (const entity of world.entities) {
    drawEntity(entity);
  }
}

function drawFields() {
  for (const entity of world.entities) {
    if (entity.signal <= 0 && entity.behavior !== BEHAVIOR.CONTAIN) {
      continue;
    }
    const visual = VISUAL[entity.behavior];
    const radius = entity.radius * (0.9 + Math.min(entity.signal, 2) * 0.18);
    const gradient = ctx.createRadialGradient(entity.x, entity.y, 0, entity.x, entity.y, radius);
    gradient.addColorStop(0, hexAlpha(visual.color, 0.26));
    gradient.addColorStop(1, hexAlpha(visual.color, 0));
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(entity.x, entity.y, radius, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawEntity(entity) {
  const visual = VISUAL[entity.behavior];
  const pulse = 1 + Math.min(entity.signal, 2) * 0.12;
  ctx.save();
  ctx.translate(entity.x, entity.y);
  ctx.scale(pulse, pulse);
  ctx.lineWidth = 3;
  ctx.strokeStyle = visual.color;
  ctx.fillStyle = visual.color;
  ctx.globalAlpha = 0.92;

  if (visual.shape === "source") {
    ctx.beginPath();
    ctx.arc(0, 0, 10, 0, Math.PI * 2);
    ctx.fill();
  } else if (visual.shape === "ring") {
    ctx.beginPath();
    ctx.arc(0, 0, 15, 0, Math.PI * 2);
    ctx.stroke();
  } else if (visual.shape === "up") {
    polygon([[0, -17], [16, 14], [-16, 14]], true);
  } else if (visual.shape === "down") {
    polygon([[-16, -14], [16, -14], [0, 17]], true);
  } else if (visual.shape === "square") {
    ctx.strokeRect(-13, -13, 26, 26);
    ctx.strokeRect(-8, -8, 16, 16);
  } else if (visual.shape === "phase") {
    ctx.beginPath();
    ctx.arc(0, 0, 16, -Math.PI / 2, Math.PI * (1.5 + entity.phase * 2));
    ctx.stroke();
  } else if (visual.shape === "diamond") {
    polygon([[0, -17], [17, 0], [0, 17], [-17, 0]], true);
  } else if (visual.shape === "double") {
    ctx.beginPath();
    ctx.arc(0, 0, 17, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, 8, 0, Math.PI * 2);
    ctx.stroke();
  } else if (visual.shape === "split") {
    polygon([[-20, -13], [0, 0], [-20, 13], [-12, 0]], true);
    polygon([[20, -13], [0, 0], [20, 13], [12, 0]], true);
  } else if (visual.shape === "merge") {
    polygon([[-20, -13], [0, 0], [-20, 13]], true);
    polygon([[20, -13], [0, 0], [20, 13]], true);
  } else if (visual.shape === "membrane") {
    ctx.globalAlpha = 0.38;
    ctx.beginPath();
    ctx.arc(0, 0, entity.radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.globalAlpha = 0.92;
    ctx.beginPath();
    ctx.arc(0, 0, 15, 0, Math.PI * 2);
    ctx.stroke();
  } else if (visual.shape === "arrow") {
    ctx.beginPath();
    ctx.moveTo(-18, 0);
    ctx.lineTo(12, 0);
    ctx.moveTo(3, -9);
    ctx.lineTo(13, 0);
    ctx.lineTo(3, 9);
    ctx.stroke();
  }

  ctx.restore();
}

function polygon(points, fill) {
  ctx.beginPath();
  ctx.moveTo(points[0][0], points[0][1]);
  for (let i = 1; i < points.length; i += 1) {
    ctx.lineTo(points[i][0], points[i][1]);
  }
  ctx.closePath();
  if (fill) {
    ctx.fill();
  } else {
    ctx.stroke();
  }
}

function animate(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  if (running) {
    world.step(dt);
  }
  draw();
  requestAnimationFrame(animate);
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function clampSignal(value) {
  return Math.max(0, value);
}

function hexAlpha(hex, alpha) {
  const value = Number.parseInt(hex.slice(1), 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

async function captureFromWorld() {
  if (!captureButton) return;
  captureButton.setAttribute("aria-pressed", "true");
  try {
    const opcodes = await loadOntology();
    const observed = world.observeAll();
    const core = await captureSemanticCore(observed, opcodes, {
      sourceLanguage: "en",
      sourcePath: "<spatial-edit>",
    });
    renderRecovered(core);
  } catch (err) {
    renderRecovered({ error: String(err && err.message ? err.message : err) });
  } finally {
    captureButton.setAttribute("aria-pressed", "false");
  }
}

function renderRecovered(payload) {
  if (!recoveredPanel) return;
  recoveredPanel.hidden = false;
  recoveredPanel.textContent = JSON.stringify(payload, null, 2);
}

palette.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-behavior]");
  if (!button) {
    return;
  }
  selected = Number.parseInt(button.dataset.behavior, 10);
  for (const item of palette.querySelectorAll("button")) {
    item.classList.toggle("selected", item === button);
  }
});

canvas.addEventListener("pointerdown", (event) => {
  const hit = world.entityAt(event.clientX, event.clientY);
  if (hit) {
    dragging = hit;
    canvas.setPointerCapture(event.pointerId);
    return;
  }
  world.add(selected, event.clientX, event.clientY);
});

canvas.addEventListener("pointermove", (event) => {
  if (!dragging) return;
  world.moveEntity(dragging, event.clientX, event.clientY);
});

canvas.addEventListener("pointerup", (event) => {
  if (!dragging) return;
  try {
    canvas.releasePointerCapture(event.pointerId);
  } catch (_err) {
    // ignore -- some browsers throw if capture was already released
  }
  dragging = null;
});

toggle.addEventListener("click", () => {
  running = !running;
  toggle.classList.toggle("icon-play", !running);
  toggle.classList.toggle("icon-pause", running);
  toggle.setAttribute("aria-pressed", String(running));
  toggle.setAttribute("aria-label", running ? "pause" : "play");
});

reset.addEventListener("click", restart);
if (captureButton) {
  captureButton.addEventListener("click", captureFromWorld);
}
window.addEventListener("resize", restart);

loadSpatialManifest()
  .catch(() => {
    sourceRows = null;
  })
  .finally(() => {
    restart();
    requestAnimationFrame(animate);
  });

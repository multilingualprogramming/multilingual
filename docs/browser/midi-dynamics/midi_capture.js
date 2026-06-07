// SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Inverse MIDI projection in the browser: observation -> semantic core.
//
// JS peer of multilingualprogramming/codegen/midi_capture.py. Takes
// MIDI events as they would be observed at the modality boundary
// (role, pitch, velocity, channel, start offset -- no opcode/name) and
// reconstructs a semantic-core-v0 manifest for the invertible subset.

const ONTOLOGY_KIND = "opcode-ontology-v0";
const CORE_KIND = "semantic-core-v0";

let ontologyPromise = null;

export function loadOntology(url = "./ontology.json") {
  if (!ontologyPromise) {
    ontologyPromise = fetch(url, { cache: "no-store" }).then((response) => {
      if (!response.ok) {
        throw new Error(`ontology.json ${response.status}`);
      }
      return response.json().then((data) => {
        if (data.kind !== ONTOLOGY_KIND || !Array.isArray(data.opcodes)) {
          throw new Error("invalid ontology manifest");
        }
        return data.opcodes;
      });
    });
  }
  return ontologyPromise;
}

export function _resetOntologyForTesting() {
  ontologyPromise = null;
}

function signatureOf(op) {
  return `${op.midi.role}|${op.midi.pitch}`;
}

export function invertibleOpcodes(opcodes) {
  const counts = new Map();
  for (const op of opcodes) {
    const sig = signatureOf(op);
    counts.set(sig, (counts.get(sig) || 0) + 1);
  }
  const invertible = new Set();
  for (const op of opcodes) {
    if (op.midi.role === "bus") continue;
    if (op.midi.velocity <= 0) continue;
    if (counts.get(signatureOf(op)) !== 1) continue;
    invertible.add(op.code);
  }
  return invertible;
}

function opcodeFromObservation(opcodes, observed) {
  const sig = `${observed.role}|${observed.pitch}`;
  const matches = opcodes.filter((op) => signatureOf(op) === sig);
  if (matches.length === 0) {
    throw new Error(
      `No ontology opcode matches MIDI observation ${sig} on event index ${observed.index}`,
    );
  }
  if (matches.length > 1) {
    const names = matches.map((op) => op.name).join(", ");
    throw new Error(
      `MIDI observation ${sig} on event index ${observed.index} is ambiguous: matches ${names}.`,
    );
  }
  const op = matches[0];
  if (op.midi.role === "bus") {
    throw new Error(
      `MIDI event index ${observed.index} resolves to bus opcode ${op.name}.`,
    );
  }
  if (op.midi.velocity <= 0) {
    throw new Error(
      `MIDI event index ${observed.index} resolves to opcode ${op.name} with zero base velocity.`,
    );
  }
  return op;
}

function intensityFromVelocity(op, observed) {
  if (observed.velocity < 0 || observed.velocity > 127) {
    throw new Error(`MIDI event index ${observed.index} velocity must be in 0..127`);
  }
  if (observed.velocity === 127) {
    throw new Error(
      `MIDI event index ${observed.index} is clipped at velocity 127.`,
    );
  }
  return observed.velocity / op.midi.velocity;
}

export function observeEvent(event) {
  return Object.freeze({
    index: Number(event.index),
    role: String(event.role),
    pitch: Number(event.pitch),
    velocity: Number(event.velocity),
    channel: Number(event.channel),
    start_offset: Number(event.start_offset),
  });
}

export function captureSemanticCore(
  observed,
  opcodes,
  { sourceLanguage = "en", sourcePath = "" } = {},
) {
  const entities = [];
  for (const event of observed) {
    const op = opcodeFromObservation(opcodes, event);
    entities.push({
      index: event.index,
      opcode: op.code,
      name: op.name,
      intensity: intensityFromVelocity(op, event),
      signal: 0.0,
      phase: event.start_offset,
      channel: event.channel,
    });
  }
  return {
    kind: CORE_KIND,
    version: 0,
    source_language: sourceLanguage,
    source: sourcePath,
    ontology: opcodes.map(({ code, name }) => ({ code, name })),
    entities,
    relations: [],
  };
}
